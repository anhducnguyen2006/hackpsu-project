# Data Storage and Persistence

Last verified: 2026-10-25

TigerData stores research history, verified dataset metadata, matches, profiles,
assessments, and research connections in the configured PostgreSQL database.
The application does not connect at import time and does not migrate itself.
`DATABASE_URL` is optional at startup. Public health stays available when it is
missing. Authenticated research routes return `503` until the pool can open.

## Additive migrations (manual)

Do not run migrations from the ordinary test suite. Do not apply them to shared TigerData without an explicit backup and approval.

### `004_research_query_owner.sql`

Adds nullable `research_queries.user_sub` and the partial index `idx_queries_owner_created`. It does not change primary keys, `(repository, external_id)`, `vector(384)`, profile uniqueness, assessment cache keys, foreign keys, or existing rows. Historical rows stay `NULL` and are not visible to ordinary users. Do not guess an owner for them.

### `005_profile_resource_key.sql`

Adds `dataset_profiles.resource_key` (default `''`) and replaces the three-column profile uniqueness with `(dataset_id, resource_key, source_version, profiler_version)`. Existing UCI profiles keep `resource_key = ''`. The migration is idempotent. Apply it only after 004.

### Apply order on an existing database at migration 003

```bash
# Preflight: confirm extensions and current columns without printing secrets.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'research_queries' AND column_name IN ('user_sub','embedding');"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'dataset_profiles' AND column_name = 'resource_key';"

# Backup first (provider-specific). Then apply in order:
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/database/migrations/004_research_query_owner.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/database/migrations/005_profile_resource_key.sql
```

### Post-migration checks (read-only)

```sql
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'research_queries' AND column_name = 'user_sub';

SELECT indexname FROM pg_indexes WHERE indexname = 'idx_queries_owner_created';

SELECT column_name, column_default
FROM information_schema.columns
WHERE table_name = 'dataset_profiles' AND column_name = 'resource_key';

SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'dataset_profiles'::regclass AND contype = 'u';

SELECT COUNT(*) FILTER (WHERE user_sub IS NULL) AS unowned_rows,
       COUNT(*) FILTER (WHERE user_sub IS NOT NULL) AS owned_rows
FROM research_queries;
```

Partial state: if `user_sub` exists but `resource_key` does not, 004 succeeded and 005 is still required. If the unique constraint still lacks `resource_key`, stop and re-run 005 after investigating. Rollback is restore-from-backup; these migrations do not ship automatic down scripts.

Fresh installs may load `backend/database/schema.sql` (already includes ownership and `resource_key`). Re-applying 004 and 005 afterward is safe and idempotent.

If `user_sub` is missing, history and similarity return `503` and name migration 004. They do not fall back to a global query. New discovery rows are written only with the verified access-token subject. Dataset metadata and data-derived profiles remain reusable. Research sessions and assessments are read through the owning query. The in-memory analysis cache and the assessment fingerprint include that subject. Discovery's question cache stores repository search results, not another user's saved history.

The limits in `AUTH_DISCOVERY_LIMIT`, `AUTH_ANALYSIS_LIMIT`, and `AUTH_SIMILARITY_LIMIT` are per worker process, not a shared quota.

## Data sources and lifecycle

Dataset metadata originates from the UCI catalog and dataset metadata APIs. Tabular data is retrieved by `ucimlrepo.fetch_ucirepo`, and the adapter uses the repository object's original Pandas DataFrame. The DataFrame is profiled in memory and is not written to disk by the application.

`DiscoveryService` keeps a process-local cache keyed by normalized question and result limit. Successful Gemini results live for 300 seconds; fallback and partial results live for 30 seconds. `UCIRepositoryService` caches the catalog for `UCI_CATALOG_TTL_SECONDS`, default 900 seconds.

`DatasetAnalysisService` keeps process-local analysis results keyed by verified subject, dataset ID, and normalized question, plus an in-memory DataFrame cache keyed by UCI integer ID. The DataFrame cache holds public source data. These caches disappear when the backend restarts.

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

The application has no local user accounts; research questions are stored only
for the verified Auth0 subject. External dataset contents are processed in
memory. Avoid logging raw DataFrames, access tokens, credentials, or
unnecessary research-question content. Gemini prompts include verified
metadata/profile evidence and may be subject to the provider's policies.

## Future consideration

Additional saved-research features would need explicit retention, deletion,
access control, and source-version policies. Request limits are process-local
until the API runs more than one worker.
