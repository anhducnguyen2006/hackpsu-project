# DataOPedia Phase 2: Live question-to-discovery workflow

## Goal

Connect the existing Phase 1 Research Instrument UI to the implemented discovery API so a submitted research question produces a real interpretation and real repository metadata results, while preserving the existing visual system, provenance labels, and cached example walkthrough.

## Current findings

- `POST /api/v1/discovery/search` exists at `backend/app/api/routes/discovery.py:25` and accepts `{ research_question, limit }`. It orchestrates Gemini interpretation, deterministic fallback, UCI catalog filtering/enrichment, configured Dataverse/Zenodo searches, deduplication, and local semantic ranking. The response includes `interpretation`, `datasets`, `warnings`, `processing_mode`, and `ranking_status`.
- Gemini interpretation is implemented in `backend/app/assessment/gemini.py:44-96`. Missing or failed Gemini does not block discovery: `backend/app/discovery/search.py:105-120` creates a labeled deterministic fallback.
- UCI discovery is implemented through `UCIRepositoryService` and `DiscoveryService`; external adapters are also enabled by default. Service-level tests cover fallback, repository failures, caching, multi-concept ranking, and provider mapping. Tests do not prove live credentials, network reachability, or embedding-model availability.
- `GET /api/v1/health` is implemented and route-tested.
- `POST /api/v1/datasets/{dataset_id}/analyze` and `/explore` are implemented for the later analysis workflow. They are not required for the smallest question → interpretation → discovery slice, but `/explore` is currently not called by the frontend.
- `frontend/src/App.tsx:30-35` already posts to `/api/v1/discovery/search` and stores the response. `frontend/src/App.tsx:40-42` already posts live UCI analysis requests.
- The live response is not propagated through all views: `App.tsx:51` always passes `EXAMPLE_INTERPRETATION` and `processingMode="keyword_fallback"` to `InterpretationSheet`, and always passes example interpretation/datasets/analysis to `KnowledgeGraphShell`.
- The frontend remains fixture-backed for initial state and non-live stages. `frontend/src/demo/researchExample.ts` supplies the example question, interpretation, two datasets, profile, assessment, and exploration. This is intentional for the `Explore the example` path and must remain available.
- The frontend has no `/explore` request. Live analysis clears exploration, so the descriptive exploration view is absent after a live analysis.
- Existing tests are fixture-oriented and include the no-network Phase 1 contract. Phase 2 must update only the tests whose contract intentionally changes; retain fixture tests for the static example path.
- `DESIGN.md` defines the visual authority: Research Instrument direction, ice silver / aubergine / marigold palette, editorial landing, ruled workspaces, explicit provenance, and honest `Unavailable` / fallback states. No visual redesign is needed for this integration.

## Recommended implementation sequence

### 1. Lock the Phase 2 boundary and state contract

Modify the frontend state contract in `frontend/src/App.tsx` so one state tree distinguishes:

- preview mode with the existing fixture;
- live mode before a response;
- live discovery response with nullable interpretation and warnings;
- request failure with the question preserved and a retry path.

Keep `EXAMPLE_*` values as the initial data for the explicit example action. Do not silently use example interpretation or datasets after a live response.

### 2. Render the live interpretation

Use `discovery?.interpretation` and `discovery?.processing_mode` when the app is in live mode. Render the interpretation stage from those values, with an honest empty/unavailable state if the backend returns no interpretation. Preserve the existing `EvidenceTag` distinction between `AI interpretation` and `Keyword fallback interpretation`.

Pass the live interpretation to the interpretation sheet when a user navigates there, and make the successful search land on the interpretation stage first. From there, provide the existing visual path to the dataset ledger; do not change the layout or introduce a new page shell.

### 3. Make the live dataset ledger the discovery result

Continue using `DatasetLedger` with `discovery.datasets`, but ensure its empty, partial, warning, source, score, and provenance states are driven by the response. Keep semantic similarity / metadata relevance clearly separate from suitability. Preserve the current UCI-only analysis affordance for non-UCI records.

Update the live header/context labels so they reflect the response mode and source scope without removing the cached-example disclosure from preview mode.

### 4. Keep graph integration truthful and minimal

For the Phase 2 discovery slice, pass live interpretation and live datasets into `KnowledgeGraphShell` only if its current props can represent them without inventing analysis evidence. Otherwise keep the graph explicitly preview-only and label that boundary. Do not create publication nodes or inferred variable links. Every live relation must remain backed by `concept_matches` or verified metadata, consistent with `DESIGN.md`.

### 5. Defer analysis exploration wiring unless it is needed for the acceptance path

The complete Phase 2 acceptance path ends at live interpretation + live discovery. Do not expand scope into a new analysis interaction yet. Record `/datasets/{dataset_id}/explore` as the next slice: add a typed request helper, invoke it only after a live analyzed UCI dataset has verified independent/outcome columns, preserve loading/errors, and keep non-UCI records metadata-only.

### 6. Add narrow contract and integration coverage

Backend:

- Add `TestClient` route tests for valid discovery response serialization, invalid question/limit (`422`), and demo-mode response labeling.
- Add route tests for repository/provider failure behavior returning a usable response with warnings rather than fabricated records.
- Keep existing service tests unchanged unless a contract mismatch is found.

Frontend:

- Add an `App` test with a mocked successful discovery response asserting the submitted question, live interpretation, processing-mode label, and live dataset title are rendered.
- Add tests for Gemini fallback labeling and warning visibility.
- Add a failed-request test asserting the question remains available and the user receives a retryable status.
- Preserve the existing example/fixture tests and no-network test behavior where `import.meta.env.MODE === "test"` disables live search.

### 7. Verify against real local services

Run:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/pytest -q
../.venv/bin/python -m compileall -q app tests

cd ../frontend
npm test
npm run build
```

For an integration smoke test, start the backend and frontend, check `GET /api/v1/health`, submit a 10–2000 character question, and verify the browser receives `200` JSON from `/api/v1/discovery/search`. Test both `DEMO_MODE=true` and live configuration. If live Gemini, repository, or embedding dependencies are unavailable, verify the labeled fallback/partial response instead of treating that as a frontend failure.

## Explicitly deferred

- New backend endpoints for interpretation or UCI search; they already exist behind `POST /api/v1/discovery/search`.
- Frontend visual redesign, new chart/graph styling, animation, or changes to the Impeccable design system.
- `/explore` UI integration, comparison, publication ingestion, authentication, persistence, background jobs, and streaming.
- Replacing the cached example; it remains the honest offline demonstration path.

