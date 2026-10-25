# DataOPedia Static UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reviewable, responsive static DataOPedia frontend for the landing page, research interpretation, dataset results, knowledge graph shell, and dataset analysis view.

**Architecture:** Keep the existing React/Vite app and replace its entry view with a local, five-stage preview driven by one typed fixture. Components receive fixture data through props; only stage navigation and disclosure controls use local state. The fixture copies repository-cached UCI example facts and is labeled on every view as a static preview. There are no network requests, backend changes, chart calculations, graph physics, or animations in Phase 1.

**Tech Stack:** React 18, TypeScript, Vite 5, CSS, inline SVG, Vitest, React Testing Library, jsdom.

**Spec:** [DESIGN.md](../../../DESIGN.md); product constraints in [docs/PRODUCT.md](../../PRODUCT.md), [docs/API.md](../../API.md), and `backend/app/demo.py`.

## Global Constraints

- Preserve the approved **Research Instrument** direction: Ice Silver `#DDE3E8`, Deep Aubergine `#3A0F34`, Marigold `#EAAA00`, editorial serif display, Geist interface text, monospaced data labels, fine rules, coordinate marks, and data-first composition.
- The five requested views are **Question**, **Interpretation**, **Datasets**, **Graph**, and **Analysis**. Comparison, live search, direct interpretation editing, graph pan/zoom, AI generation, and motion are later phases.
- Every view displays `Static preview · cached UCI example`. The landing example is explicitly illustrative; the other views use the exact cached UCI content documented in `backend/app/demo.py`. Do not invent publications, dataset IDs, metadata, links, statistics, scores, or claims.
- Display preliminary relevance as **metadata-based**. Display suitability as **Unavailable** for the cached example; `backend/app/demo.py` has no authentic cached AI assessment or suitability score. Distinguish `UCI metadata`, `Computed profile`, `Keyword fallback interpretation`, and `Cached demo` in text, not color alone.
- The graph may show question, concepts, UCI datasets, and supported variable relations only. Its publication layer states `No verified publication links are available.` Never render a publication node or inferred citation.
- Counts describe **observed records**, never participants. `studytime` is ordinal or encoded numeric; show category frequencies rather than treating its numeric codes as an exact continuous unit. Descriptive summaries do not establish causation or significance.
- Use local navigation only. The research-question textarea may accept text, but its button must explain that live search is unavailable; a separate `Explore the example` action opens the fixed example. No request to `/api` or any other endpoint is allowed in the shipped Phase 1 bundle.
- Keep existing user changes intact. `frontend/package.json`, lockfile, Vite config, TypeScript config, and `frontend/src/styles.css` are already modified in the workspace. Review their diffs before editing; stage only files changed for this plan. Do not import the old stylesheet into the new UI, but do not delete it as a side effect.
- Commit after each task only when this task's hunks can be isolated. For files that already contain user changes, use `git add -p` and inspect `git diff --cached` before committing; if the lockfile cannot be separated safely, leave that task uncommitted and report it rather than including someone else's changes.
- Semantic headings, labeled inputs, visible keyboard focus, accessible graph list, chart data table, and usable layouts at 1440, 768, and 390 px are acceptance requirements. No CSS transitions, keyframe animations, GSAP, or animated SVG.

## Review Focus

1. **A visitor types a different question:** the app must not show the fixed study-time results as if they answer that text. Task 3 tests the explicit static-preview response.
2. **A result has missing metadata or a null score:** the row must say `Not documented` or `Unavailable`, and must not render `0` or an invented value. Task 5 tests these values.
3. **Graph evidence is incomplete:** no publication node or unsupported link is drawn; the text list still explains every displayed edge. Task 6 tests both conditions.
4. **AI assessment is unavailable:** analysis must show verified computed values and an unavailable suitability score, without a fabricated score breakdown. Task 7 tests this state.
5. **Long variable names and narrow screens:** metadata, graph list, and profile table remain readable without clipped facts or page-level horizontal overflow. Task 9 verifies 390 px and 200% zoom captures.

## File map

| File | Responsibility |
| --- | --- |
| `frontend/src/App.tsx` | Local stage state, persistent preview banner, navigation, and view composition; replaces current API-driven root view. |
| `frontend/src/demo/researchExample.ts` | One typed fixture using values from `backend/app/demo.py`, plus explicit static-preview labels. |
| `frontend/src/types.ts` | Add missing result fields present in the API schema (`variable_descriptions`, matched and missing research variables, classification) if used by the preview. Preserve current API types for later integration. |
| `frontend/src/components/EvidenceTag.tsx` | Shared text provenance label with explanation. |
| `frontend/src/components/ResearchQuestion.tsx` | Landing input and honest static-preview submit behavior. |
| `frontend/src/components/InterpretationSheet.tsx` | Extracted subject, variables, outcome, population, terms, and fallback label. |
| `frontend/src/components/DatasetLedger.tsx` | Metadata-rich dataset rows and details disclosure. |
| `frontend/src/components/KnowledgeGraphShell.tsx` | Static SVG evidence topology, publication empty state, and equivalent relation list. |
| `frontend/src/components/AnalysisView.tsx` | Profile masthead, variable table, quality and evidence sections, and unavailable assessment. |
| `frontend/src/components/DescriptiveFigure.tsx` | Static grouped-descriptive figure with caption and equivalent data table. |
| `frontend/src/styles/foundation.css` | Tokens, type, grid, shared controls, focus, responsive shell. |
| `frontend/src/styles/landing.css` | Landing composition and question-to-evidence schematic. |
| `frontend/src/styles/workspace.css` | Interpretation and dataset ledger layouts. |
| `frontend/src/styles/graph.css` | Graph shell, inspector, and relation-list layouts. |
| `frontend/src/styles/analysis.css` | Analysis and figure layouts. |
| `frontend/src/main.tsx` | Imports the new CSS files in order; keeps React root. |
| `frontend/src/test/setup.ts`, `frontend/vitest.config.ts` | Test environment and accessible DOM matchers. |
| `frontend/src/**/*.test.tsx`, `frontend/src/demo/researchExample.test.ts` | Behavior and evidence-integrity tests at each surface boundary. |
| `frontend/index.html` | DataOPedia page title and document metadata. |

### Task 1: Test harness and evidence fixture

**Files:** Modify `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/types.ts`; create `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/demo/researchExample.ts`, `frontend/src/demo/researchExample.test.ts`.

**Interfaces:** Export `EXAMPLE_QUESTION: string`, `EXAMPLE_INTERPRETATION: ResearchInterpretation`, `EXAMPLE_DATASETS: DatasetCardData[]`, `EXAMPLE_ANALYSIS: DatasetAnalysisResponse`, and `EXAMPLE_EXPLORATION: ExploratoryAnalysisResponse`. The fixture is the only preview-data source for later tasks.

- [ ] **Step 1: Review existing diffs** with `git diff -- frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts frontend/src/styles.css`; preserve unrelated edits.
- [ ] **Step 2: Add test dependencies and script**: install Vitest, jsdom, React Testing Library, jest-dom, and user-event as dev dependencies; add `"test": "vitest run"`. Configure jsdom and `src/test/setup.ts` in `frontend/vitest.config.ts` without changing existing Vite plugins or aliases.
- [ ] **Step 3: Write the failing fixture test** in `researchExample.test.ts`: assert UCI `uci:320` / `uci:856`, 649 / 145 metadata instances, preliminary relevance 92 / 48, 649 observed analysis rows, `assessment.final_score === null`, and no publication property. Assert the example question is the noncausal study-time wording from `DESIGN.md`.
- [ ] **Step 4: Run `cd frontend && npm test -- src/demo/researchExample.test.ts`**; expect failure because fixture exports do not exist.
- [ ] **Step 5: Create the typed fixture** from `backend/app/demo.py`, copying only fields required for these five views; include the cached category counts and grouped statistics when `EXAMPLE_EXPLORATION` is built. Keep the exact source URL and caveat strings. Extend `DatasetCardData` only for actual API fields used by the ledger.
- [ ] **Step 6: Run `cd frontend && npm test -- src/demo/researchExample.test.ts && npm run build`**; expect passing assertions and TypeScript/Vite success. Inspect `git diff --cached`, stage only this task's hunks, and commit them as `test: add typed DataOPedia example fixture` if safely isolated.

### Task 2: Visual foundation and local stage shell

**Files:** Modify `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/index.html`; create `frontend/src/styles/foundation.css`, `frontend/src/App.test.tsx`.

**Interfaces:** Export `type PreviewStage = "question" | "interpretation" | "datasets" | "graph" | "analysis"` from `App.tsx`. `App` owns `stage` and renders one surface at a time; all data comes from Task 1 fixture. Until later tasks land, each stage has a named placeholder heading and no false findings.

- [ ] **Step 1: Write a failing shell test**: `DataOPedia` and `Static preview · cached UCI example` are visible; navigation exposes five named buttons; choosing `Graph` shows only the graph stage heading; no network function is called.
- [ ] **Step 2: Run `cd frontend && npm test -- src/App.test.tsx`**; expect failure against the current API-driven app.
- [ ] **Step 3: Replace the root view** with a semantic header, stage navigation, main region, and static-preview banner. Use buttons with `aria-current="page"` for the active stage; retain native keyboard behavior. Set the document title in `index.html`.
- [ ] **Step 4: Add foundation tokens and layout** using exact palette values, 8 px spacing base, 12-column desktop rhythm, visible rules and focus indicators, Georgia for display text, the already installed Geist for interface text, and monospace data labels. Import the new CSS from `main.tsx`; remove the old `styles.css` import without deleting or rewriting that file.
- [ ] **Step 5: Run `cd frontend && npm test -- src/App.test.tsx && npm run build`**; expect pass. Commit only the task files.

### Task 3: Landing page and research input

**Files:** Create `frontend/src/components/ResearchQuestion.tsx`, `frontend/src/components/ResearchQuestion.test.tsx`, `frontend/src/styles/landing.css`; modify `frontend/src/App.tsx`, `frontend/src/main.tsx`.

**Interfaces:** `ResearchQuestion({ exampleQuestion, onExploreExample }: { exampleQuestion: string; onExploreExample: () => void })`. The component owns editable textarea text and a status message; `onExploreExample` moves to `interpretation` but always uses the fixed example fixture.

- [ ] **Step 1: Write failing tests**: the textarea has label `Research question` and supports typing; submitting it shows `Static preview: live search is not connected` and does not open results; `Explore the example` calls `onExploreExample`; the schematic is labeled `Illustrative workflow` and contains no invented numeric result.
- [ ] **Step 2: Run `cd frontend && npm test -- src/components/ResearchQuestion.test.tsx`**; expect failure because the component is absent.
- [ ] **Step 3: Implement the landing composition**: editorial left column with the title and input, right column with a semantic question→interpretation→UCI datasets→profile SVG/CSS schematic, and a bottom provenance strip. Keep the complete question control and action in the desktop first viewport; use no animation.
- [ ] **Step 4: Run `cd frontend && npm test -- src/components/ResearchQuestion.test.tsx && npm run build`**; expect pass. Commit only this task's files.

### Task 4: Research interpretation sheet

**Files:** Create `frontend/src/components/EvidenceTag.tsx`, `frontend/src/components/InterpretationSheet.tsx`, `frontend/src/components/InterpretationSheet.test.tsx`, `frontend/src/styles/workspace.css`; modify `frontend/src/App.tsx`, `frontend/src/main.tsx`.

**Interfaces:** `EvidenceTag({ label, explanation }: { label: string; explanation: string })`; `InterpretationSheet({ interpretation, processingMode }: { interpretation: ResearchInterpretation; processingMode: DiscoveryResponse["processing_mode"] })`.

- [ ] **Step 1: Write failing tests**: subject, independent variable, outcome, population, synonym, and three search terms render from props; `keyword_fallback` displays `Keyword fallback interpretation`; the page never calls extracted terms verified dataset columns.
- [ ] **Step 2: Run `cd frontend && npm test -- src/components/InterpretationSheet.test.tsx`**; expect missing-component failure.
- [ ] **Step 3: Implement a four-column ruled sheet** with a compact terms/method rail. Use `EvidenceTag` to explain that these are interpreted concepts, then add a link/button back to `Question` to revise the query. Read values from the fixture in `App`.
- [ ] **Step 4: Run `cd frontend && npm test -- src/components/InterpretationSheet.test.tsx && npm run build`**; expect pass. Commit only this task's files.

### Task 5: Metadata-rich dataset ledger

**Files:** Create `frontend/src/components/DatasetLedger.tsx`, `frontend/src/components/DatasetLedger.test.tsx`; modify `frontend/src/styles/workspace.css`, `frontend/src/App.tsx`.

**Interfaces:** `DatasetLedger({ datasets, onOpenAnalysis }: { datasets: DatasetCardData[]; onOpenAnalysis: (datasetId: string) => void })`. Only `uci:320` can open the fixture analysis; `uci:856` remains a metadata-only preview. `EvidenceTag` marks UCI metadata and metadata-based relevance.

- [ ] **Step 1: Write failing tests**: both cached UCI records show title, ID, source link, counts, relevance label, confidence, matched and missing terms; an expanded row exposes descriptions and original URL; a null score displays `Unavailable`; null metadata displays `Not documented`; only the analyzed example opens `Analysis`.
- [ ] **Step 2: Run `cd frontend && npm test -- src/components/DatasetLedger.test.tsx`**; expect missing-component failure.
- [ ] **Step 3: Build the broad ruled ledger** and narrow context rail. Keep source and match explanation next to each result. Use semantic disclosure buttons with `aria-expanded`; render a clearly disabled `Analysis preview unavailable` action for the second record rather than implying an analysis exists. Do not add compare selection in Phase 1.
- [ ] **Step 4: Run `cd frontend && npm test -- src/components/DatasetLedger.test.tsx && npm run build`**; expect pass. Commit only this task's files.

### Task 6: Knowledge graph shell and equivalent evidence list

**Files:** Create `frontend/src/components/KnowledgeGraphShell.tsx`, `frontend/src/components/KnowledgeGraphShell.test.tsx`, `frontend/src/styles/graph.css`; modify `frontend/src/App.tsx`, `frontend/src/main.tsx`.

**Interfaces:** `KnowledgeGraphShell({ interpretation, datasets, analysis }: { interpretation: ResearchInterpretation; datasets: DatasetCardData[]; analysis: DatasetAnalysisResponse })`. The static graph is derived only from fixture-supported question/concept, UCI dataset, and `research_variable_evidence` links; no graph library or layout engine is introduced.

- [ ] **Step 1: Write failing tests**: graph and relation list show a question→concept interpretation link and `study time`→`studytime` verified mapping with source text; UCI dataset links are named; `No verified publication links are available.` is visible; there are zero publication nodes or citation URLs; every SVG edge has a corresponding list item.
- [ ] **Step 2: Run `cd frontend && npm test -- src/components/KnowledgeGraphShell.test.tsx`**; expect failure.
- [ ] **Step 3: Implement a fixed SVG topology** on a measured grid, a visible legend, a static inspector explaining the selected example link, and an ordered relation list. Expose the list as the primary accessible version. Do not implement panning, zooming, force layout, hover-only content, or motion.
- [ ] **Step 4: Run `cd frontend && npm test -- src/components/KnowledgeGraphShell.test.tsx && npm run build`**; expect pass. Commit only this task's files.

### Task 7: Dataset analysis and suitability state

**Files:** Create `frontend/src/components/AnalysisView.tsx`, `frontend/src/components/AnalysisView.test.tsx`, `frontend/src/styles/analysis.css`; modify `frontend/src/App.tsx`, `frontend/src/main.tsx`.

**Interfaces:** `AnalysisView({ analysis }: { analysis: DatasetAnalysisResponse })`. It reads `profile` and `assessment` but never computes statistics or suitability.

- [ ] **Step 1: Write failing tests**: `649 observed records`, `33 columns`, and `0 duplicate rows` appear with `Computed profile`; the table says it displays two cached variable profiles of 33 total columns; `studytime` is labeled ordinal/encoded and shows categories `1: 212`, `2: 305`, `3: 97`, `4: 35`; `G3` displays mean `11.91` (rounded from the fixture's `11.906009244992296`) and median `12`; the six assessment criteria show `Unavailable` with no numeric suitability total; limitations say the data does not establish causation.
- [ ] **Step 2: Run `cd frontend && npm test -- src/components/AnalysisView.test.tsx`**; expect failure.
- [ ] **Step 3: Implement the report masthead, profile metrics, evidence mapping, variable table, quality notes, and unavailable AI assessment**. Give every statistic a label and denominator or context. Do not turn ordinal codes into a continuous chart or show a fabricated score.
- [ ] **Step 4: Run `cd frontend && npm test -- src/components/AnalysisView.test.tsx && npm run build`**; expect pass. Commit only this task's files.

### Task 8: Descriptive figure with data equivalent

**Files:** Create `frontend/src/components/DescriptiveFigure.tsx`, `frontend/src/components/DescriptiveFigure.test.tsx`; modify `frontend/src/components/AnalysisView.tsx`, `frontend/src/styles/analysis.css`.

**Interfaces:** `DescriptiveFigure({ exploration }: { exploration: ExploratoryAnalysisResponse })`. Use provided grouped means/counts only; it performs formatting and positioning, not statistical recomputation.

- [ ] **Step 1: Write failing tests**: four studytime categories and their observed `n` values appear in an HTML data table; the SVG has a descriptive title and caption; `649 analyzed observations`, `0 excluded`, and the noncausal/non-significance limitation are present; no p-value or significance label is present.
- [ ] **Step 2: Run `cd frontend && npm test -- src/components/DescriptiveFigure.test.tsx`**; expect failure.
- [ ] **Step 3: Build a static, ruled SVG figure** using the fixture's grouped mean outcome values, plain axes and `n` labels, with an adjacent accessible table. Add the figure below the profile, never above the variable evidence.
- [ ] **Step 4: Run `cd frontend && npm test -- src/components/DescriptiveFigure.test.tsx && npm run build`**; expect pass. Commit only this task's files.

### Task 9: Responsive integration and final verification

**Files:** Modify `frontend/src/styles/foundation.css`, `frontend/src/styles/landing.css`, `frontend/src/styles/workspace.css`, `frontend/src/styles/graph.css`, `frontend/src/styles/analysis.css`, `frontend/src/App.test.tsx`; no backend files.

**Interfaces:** No new API. All five views remain reachable through `App` local navigation and retain their evidence labels.

- [ ] **Step 1: Add an integration test** that navigates Question→Interpretation→Datasets→Graph→Analysis with the example fixture, checking each stage heading, persistent static-preview banner, and absence of API calls. Add a test that the edited question stays visibly separate from the fixed example.
- [ ] **Step 2: Run `cd frontend && npm test -- src/App.test.tsx`**; expect failure until integration behavior is complete.
- [ ] **Step 3: Resolve any integration gaps** in `App` and responsive CSS. At ≤768 px move the context rail above content; at ≤640 px stack landing and result fields; at ≤390 px use the graph relation list as the default visible content. Keep table data accessible via deliberate internal scroll or stacked rows, with no document-level horizontal overflow.
- [ ] **Step 4: Run `cd frontend && npm test && npm run build`**; expect all tests and TypeScript/Vite build to pass.
- [ ] **Step 5: Start `cd frontend && npm run dev -- --host 127.0.0.1`**, inspect all five views at 1440×900, 768×1024, 390×844, and 200% zoom. Verify palette, first-viewport input prominence, focus order, readable source/limitation labels, no clipped long variable name, no page-level horizontal scrolling, no motion, and a visible `Static preview` label on every view. Fix only observed defects, then repeat the full test/build commands once.
- [ ] **Step 6: Search the shipping source** with `rg -n 'fetch\(|/api/|animation:|transition:|@keyframes' frontend/src/App.tsx frontend/src/components frontend/src/styles`; expect no API calls or motion declarations in new UI files. Commit only this task's changes.

## Phase 1 exit criteria

- All five named views render from one clearly labeled cached example with no backend traffic.
- The ice silver, aubergine, and marigold system is consistent across landing and workspaces; scientific content remains the focal point.
- Dataset relevance, computed profile, AI interpretation, and unavailable AI suitability remain distinct in labels and layout.
- Graph publications are explicitly unavailable, and every visible graph relation has a readable evidence-list counterpart.
- `npm test` and `npm run build` pass; desktop, tablet, phone, and 200% zoom have been inspected.

**Deferred:** backend API integration, live question search, comparison, graph interaction, motion, generated AI assessment, and publication ingestion.
