# Data Storage and Persistence

Last verified: 2026-10-24

**ResearchLens does not currently use a persistent application database.**

## Data sources and lifecycle

Dataset metadata originates from the UCI catalog and dataset metadata APIs. Tabular data is retrieved by `ucimlrepo.fetch_ucirepo`, and the adapter uses the repository object's original Pandas DataFrame. The DataFrame is profiled in memory and is not written to disk by the application.

`DiscoveryService` keeps a process-local cache keyed by normalized question and result limit. Successful Gemini results live for 300 seconds; fallback and partial results live for 30 seconds. `UCIRepositoryService` caches the catalog for `UCI_CATALOG_TTL_SECONDS`, default 900 seconds.

`DatasetAnalysisService` keeps process-local analysis results keyed by dataset ID and normalized question, plus an in-memory DataFrame cache keyed by UCI integer ID. These caches disappear when the backend restarts.

## DEMO_MODE

Demo values are explicit Python fixtures in `backend/app/demo.py`. They contain verified UCI metadata and cached statistical results for the supported Student Performance demonstration, plus comparison metadata for #856. Demo mode never silently substitutes into live mode and labels cached provenance in responses.

## Privacy and retention

The application has no user accounts or persistent user data. External dataset contents are processed in memory. Avoid logging raw DataFrames, credentials, or unnecessary research-question content. Gemini prompts include verified metadata/profile evidence and may be subject to the provider's policies.

## Future consideration

A database could become useful for durable provenance, shared caches, saved research projects, and audit history. Any such design would need explicit retention, deletion, access control, and source-version policies; none is implemented today.
