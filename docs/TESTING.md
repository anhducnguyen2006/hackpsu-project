# Testing and Validation

Last verified: 2026-10-24

## Backend

The backend uses pytest with focused unit/service tests under `backend/tests`:

- `test_health.py`: health route
- `test_discovery.py`: filtering, candidate validation, fallback, repository failure, cache, demo labels, and candidate bounds
- `test_analysis.py`: profiling, ordinal evidence, analysis caching, score recomputation, failures, demo statistics, and exploration
- `test_gemini.py`: structured Gemini parsing, maximum-size output, and truncation rejection

Run:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/pytest -q
```

Compile:

```bash
cd backend
../.venv/bin/python -m compileall -q app tests
```

The repository has no committed coverage threshold. Tests use fakes/mocks for Gemini and repositories to avoid consuming quota.

## Frontend

The frontend has no configured unit-test runner. The production build performs TypeScript project compilation and Vite bundling:

```bash
cd frontend
npm run build
```

Browser checks have been performed manually and through temporary browser automation for search, analysis, exploration, comparison, cached demo labels, responsive charts, and nested controls. They are not a permanently configured automated browser suite.

## Change checklist

- Discovery: test real-record provenance, empty results, repository failure, fallback labels, and cache TTL behavior.
- Gemini: use mocked structured responses; test invalid schema, truncation, 429/503/504 classification, and no-secret logging. Use at most one bounded live smoke test.
- Profiling: verify counts, missingness, dtypes, ordinal categories, evidence mappings, and exact numerical values.
- Scoring: test available and unknown criteria; confirm Python, not Gemini, computes the total.
- Frontend: test loading, retry, stale requests, keyboard controls, mobile layout, and independent state.
- Exploration: verify grouped means/counts, missing exclusions, scale metadata, and causal limitations.
- Comparison: verify metadata-only labels and changing questions.
- DEMO_MODE: verify provenance labels and that unrelated questions do not receive cached results.

## Known limitations

Live Gemini and UCI tests depend on network, provider availability, quota, and account/model access. Browser CORS configuration must include the actual frontend origin. The frontend lacks a dedicated component test suite.
