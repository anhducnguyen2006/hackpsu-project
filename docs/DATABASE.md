# Data Storage and Persistence

Last verified: 2026-10-25

TigerData stores research history in the five tables defined by `backend/database/schema.sql`. The application does not connect at import time and does not migrate itself. `DATABASE_URL` is optional at startup. Public health stays available when it is missing. Authenticated research routes return `503` until the pool can open.

Migration `004_research_query_owner.sql` adds nullable `research_queries.user_sub` and the partial index `idx_queries_owner_created`. It does not change primary keys, `(repository, external_id)`, `vector(384)`, profile uniqueness, assessment cache keys, foreign keys, or existing rows. Historical rows stay `NULL` and are not visible to ordinary users. Do not guess an owner for them.

Apply it manually to the shared database. Do not run it from the test suite:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/database/migrations/004_research_query_owner.sql
```

Then verify, without printing row contents:

```sql
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'research_queries' AND column_name = 'user_sub';

SELECT indexname FROM pg_indexes WHERE indexname = 'idx_queries_owner_created';

SELECT COUNT(*) FILTER (WHERE user_sub IS NULL) AS unowned_rows,
       COUNT(*) FILTER (WHERE user_sub IS NOT NULL) AS owned_rows
FROM research_queries;
```

If the column is missing, history and similarity return `503` and name the migration. They do not fall back to a global query. New discovery rows are written only with the verified access-token subject. Dataset metadata and data-derived profiles remain reusable. Research sessions and assessments are read through the owning query. The in-memory analysis cache and the assessment fingerprint include that subject. Discovery's question cache stores repository search results, not another user's saved history.

The limits in `AUTH_DISCOVERY_LIMIT`, `AUTH_ANALYSIS_LIMIT`, and `AUTH_SIMILARITY_LIMIT` are per worker process, not a shared quota.

## Data sources and lifecycle

Dataset metadata originates from the UCI catalog and dataset metadata APIs. Tabular data is retrieved by `ucimlrepo.fetch_ucirepo`, and the adapter uses the repository object's original Pandas DataFrame. The DataFrame is profiled in memory and is not written to disk by the application.

`DiscoveryService` keeps a process-local cache keyed by normalized question and result limit. Successful Gemini results live for 300 seconds; fallback and partial results live for 30 seconds. `UCIRepositoryService` caches the catalog for `UCI_CATALOG_TTL_SECONDS`, default 900 seconds.

`DatasetAnalysisService` keeps process-local analysis results keyed by verified subject, dataset ID, and normalized question, plus an in-memory DataFrame cache keyed by UCI integer ID. The DataFrame cache holds public source data. These caches disappear when the backend restarts.

## DEMO_MODE

Demo values are explicit Python fixtures in `backend/app/demo.py`. They contain verified UCI metadata and cached statistical results for the supported Student Performance demonstration, plus comparison metadata for #856. Demo mode never silently substitutes into live mode and labels cached provenance in responses.

## Privacy and retention

Research questions are stored only for the verified Auth0 subject. External dataset contents are processed in memory. Avoid logging raw DataFrames, access tokens, credentials, or unnecessary research-question content. Gemini prompts include verified metadata/profile evidence and may be subject to the provider's policies.

## Future consideration

Saved history still needs an explicit retention and deletion policy. Request limits are process-local until the API runs more than one worker.
