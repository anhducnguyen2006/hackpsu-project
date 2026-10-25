# Observability and Diagnostics

Last verified: 2026-10-24

## Implemented

The backend uses Python logging for discovery stage timings, including interpretation, catalog retrieval, candidate filtering, metadata enrichment, vector embedding/cosine similarity, reranking, response fallback, serialization, and cache hits. Research persistence logs connection acquisition, embedding generation, research-question insert, dataset metadata upserts, relationship inserts, transaction commit, and total persistence time. Gemini logs aggregate prompt/output/total token counts when usage metadata is exposed. It does not log API keys.

Discovery history persistence is scheduled with FastAPI `BackgroundTasks` because it is nonessential to the live result. The task receives detached scalar/JSON dataset data, opens its own pooled connection, and commits the question, dataset upserts, and relationships in one transaction. Only after that commit, it runs bounded semantic and shared-dataset graph updates scoped to the new query, using fresh pooled connections rather than a request-scoped session. Background tasks are best-effort rather than durable jobs: work may be lost if the process or server terminates before the task completes. Persistence and graph-update failures are logged with task type and error type, without exception text or credentials, and do not change a successful discovery response.

External calls have bounded timeouts. Gemini uses the configured request timeout and bounded retries for selected transient statuses; 429 is not automatically retried. Gemini errors are classified as quota/rate limit, model unavailable, temporary service unavailability, request timeout, or generic request failure. Analysis sanitizes known credential-like error fragments.

The frontend exposes loading, empty, error, retry, timeout, and cached/fallback labels. Search requests use an `AbortController` and sequence protection so stale responses cannot replace a newer search.

## Troubleshooting

| Symptom | Evidence to inspect | Likely action |
|---|---|---|
| Gemini 429 | Backend warning/error classification | Stop retrying; check quota and model/project access. |
| Gemini 503 | Timed stage log and sanitized warning | Try a permitted model later; use keyword fallback or DEMO_MODE. |
| Gemini 504 | Request duration versus `GEMINI_REQUEST_TIMEOUT_MS` | Check provider latency and timeout budget; do not assume the data path failed. |
| Invalid JSON/schema | Gemini operation error and Pydantic validation | Inspect finish reason and schema-compatible response; do not accept fabricated fallback data. |
| UCI failure | Catalog/metadata/fetch warning | Check network, UCI availability, dataset ID, and supported size limits. |
| CORS failure | Browser console and request origin | Include the frontend origin in `BACKEND_CORS_ORIGINS`; restart backend. |
| Stuck search | Frontend timeout/error state and discovery stage logs | Confirm the request completed or was aborted; use Retry. |

Run the backend with normal Uvicorn logging and inspect the browser console. There is no external monitoring, tracing platform, metrics service, or centralized log collector installed.

## Security

Never log credentials, raw API keys, raw datasets, or unnecessary personal information. Keep `backend/.env` ignored. External error text must remain sanitized before being returned to users.

## Future improvements

Structured request IDs, privacy-reviewed metrics, OpenTelemetry tracing, and a centralized error event model could improve production diagnosis. They are not implemented.
