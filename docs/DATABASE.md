# Data Storage and Persistence

Last verified: 2026-10-24

Research history, verified dataset metadata, matches, profiles, assessments, and
research connections are persisted in the configured TigerData PostgreSQL
database. Raw tabular dataset contents remain process-local.

## Data sources and lifecycle

Dataset metadata originates from the UCI catalog and dataset metadata APIs. Tabular data is retrieved by `ucimlrepo.fetch_ucirepo`, and the adapter uses the repository object's original Pandas DataFrame. The DataFrame is profiled in memory and is not written to disk by the application.

`DiscoveryService` keeps a process-local cache keyed by normalized question and result limit. Successful Gemini results live for 300 seconds; fallback and partial results live for 30 seconds. `UCIRepositoryService` caches the catalog for `UCI_CATALOG_TTL_SECONDS`, default 900 seconds.

`DatasetAnalysisService` keeps process-local analysis results keyed by dataset ID and normalized question, plus an in-memory DataFrame cache keyed by UCI integer ID. These caches disappear when the backend restarts.

## Research semantic connections

`BAAI/bge-small-en-v1.5` produces 384-dimensional normalized embeddings and is
identified in `research_queries.embedding_model` as `BAAI/bge-small-en-v1.5@1`.
The semantic connection generator compares only rows with that exact model
identifier using pgvector cosine distance. It uses a starting threshold of
`0.75` and at most five nearest neighbors per question. The threshold is a
heuristic and requires calibration against representative research questions;
it is not a claim that two questions are scientifically equivalent.

Questions without embeddings can be safely filled with:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python scripts/backfill_research_embeddings.py
```

Connections can then be generated with:

```bash
PYTHONPATH=. ../.venv/bin/python scripts/build_research_connections.py
```

Exact shared-dataset links are generated separately from persisted
`query_dataset_matches` rows:

```bash
PYTHONPATH=. ../.venv/bin/python scripts/build_shared_dataset_connections.py
```

This uses one grouped self-join on `query_dataset_matches`, counts distinct
database dataset IDs, and upserts `SHARED_DATASET` edges. Explanations can use
`get_shared_datasets(...)` to retrieve the matching dataset IDs, titles,
repositories, and external IDs.

After a successful discovery persistence commit, FastAPI schedules bounded
connection updates for only the newly saved research query. Existing history
can be repaired with the full rebuild command:

```bash
PYTHONPATH=. ../.venv/bin/python scripts/rebuild_research_connections.py
```

The backfill and semantic commands use the local embedding model only and do
not call Gemini. The shared-dataset command uses only database relationships.
The embedding backfill updates only rows whose embedding is `NULL`; embeddings
tagged with a different model are preserved and excluded from semantic
comparisons.

## DEMO_MODE

Demo values are explicit Python fixtures in `backend/app/demo.py`. They contain verified UCI metadata and cached statistical results for the supported Student Performance demonstration, plus comparison metadata for #856. Demo mode never silently substitutes into live mode and labels cached provenance in responses.

## Privacy and retention

The application has no user accounts. External dataset contents are processed
in memory. Avoid logging raw DataFrames, credentials, or unnecessary
research-question content. Gemini prompts include verified metadata/profile
evidence and may be subject to the provider's policies.

## Future consideration

Additional saved-research features would need explicit retention, deletion,
access control, and source-version policies.
