# Architectural Decisions

Last verified: 2026-10-24

These ADRs describe decisions evidenced by the implementation and project context. Historical rationale is marked as inferred where it is not recorded elsewhere.

## ADR-001: React, TypeScript, and Vite

- Status: Accepted
- Context: The frontend is a lightweight hackathon dashboard.
- Decision: Use React functional components, TypeScript, Vite, and plain CSS.
- Rationale: Project context explicitly selected this stack; the implementation has no UI framework dependency.
- Tradeoffs: Fast iteration and small dependency surface, but fewer prebuilt components.
- Consequences: UI state and presentation currently center on `App.tsx` and `styles.css`.

## ADR-002: FastAPI and Pydantic

- Status: Accepted
- Context: The service needs typed JSON APIs and Python data tooling.
- Decision: Use FastAPI routes and Pydantic request/response models.
- Rationale: Recorded project architecture and current schemas.
- Tradeoffs: Simple synchronous API, without built-in job orchestration.
- Consequences: Invalid requests receive validation errors and response contracts are explicit.

## ADR-003: UCI as the initial repository

- Status: Accepted
- Context: The MVP needs a real public repository.
- Decision: Use UCI's structured catalog/metadata APIs and `fetch_ucirepo`.
- Rationale: Explicit project requirement; avoids parsing `list_available_datasets()` terminal output.
- Tradeoffs: Coverage and availability depend on UCI.
- Consequences: IDs use verified `uci:<integer>` format and the adapter can later be replaced.

## ADR-004: Deterministic statistics, AI interpretation

- Status: Accepted
- Context: Scientific statistics must be reproducible.
- Decision: Pandas/NumPy calculate profiles and grouped summaries; Gemini interprets language and evidence.
- Rationale: Explicit scientific-integrity requirement.
- Tradeoffs: AI cannot compensate for missing data, and profile scope is deliberately conservative.
- Consequences: AI output never supplies numeric dataset facts.

## ADR-005: Separate relevance and suitability

- Status: Accepted
- Context: Discovery metadata cannot establish data usability.
- Decision: Preliminary relevance is metadata-based; research suitability requires a profile and may include a Python-recomputed heuristic score.
- Rationale: Explicit product requirement.
- Tradeoffs: Users see multiple signals that require explanation.
- Consequences: API and UI label the two concepts separately.

## ADR-006: No persistent database for the MVP

- Status: Accepted
- Context: The hackathon MVP prioritizes understandable local operation.
- Decision: Use process-local caches and explicit demo fixtures.
- Rationale: Project scope and current implementation.
- Tradeoffs: Results and caches disappear on restart; no shared history.
- Consequences: A future persistence layer would be an explicit architectural change.

## ADR-007: Explicit DEMO_MODE

- Status: Accepted
- Context: Presentations must survive network and quota instability.
- Decision: Offline cached behavior is enabled only by `DEMO_MODE=true` and is labeled.
- Rationale: Explicit reliability requirement.
- Tradeoffs: Demo coverage is limited to verified fixtures.
- Consequences: Live mode remains the default and does not silently use demo records.
