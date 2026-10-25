# Repository Guidelines

## Project Structure & Module Organization

This is a small monorepo for research dataset discovery. The repository structure is:

```text
.
├── AGENTS.md, README.md, .env.example, .gitignore
├── backend/
│   ├── .env.example, requirements.txt
│   ├── app/                 # FastAPI application
│   │   ├── main.py, config.py, demo.py, __init__.py
│   │   ├── api/__init__.py, schemas.py
│   │   │   └── routes/__init__.py, discovery.py, datasets.py, health.py
│   │   ├── assessment/__init__.py, gemini.py, suitability.py
│   │   ├── analysis/__init__.py, service.py, exploratory.py
│   │   ├── discovery/__init__.py, search.py, uci.py
│   │   └── profiling/__init__.py, profiler.py
│   └── tests/test_health.py, test_discovery.py, test_gemini.py, test_analysis.py
├── frontend/
│   ├── index.html, package.json, package-lock.json
│   ├── tsconfig.json, vite.config.ts, .env.example
│   └── src/                 # App.tsx, main.tsx, types.ts, styles.css, vite-env.d.ts
└── docs/                    # API, architecture, decisions, testing, and design docs
    ├── API.md, ARCHITECTURE.md, CONVENTIONS.md, DATABASE.md
    ├── DECISIONS.md, OBSERVABILITY.md, PRODUCT.md, README.md
    ├── REALTIME.md, TESTING.md
    └── design/README.md
```

Generated or local-only directories such as `.venv/`, `frontend/node_modules/`, caches, and build output are intentionally excluded.

## Overall Application Workflow

The frontend submits a research question to `POST /api/v1/discovery/search`. The backend first asks Gemini to extract the subject, variables, population, synonyms, and search terms. It loads the UCI catalog, performs an initial keyword filter, enriches a bounded set of candidates with verified UCI metadata, and asks Gemini to rerank those candidates. If interpretation times out or fails, deterministic keyword matching returns `keyword_fallback`; if reranking fails, the response is `partial_gemini`. Results are cached in process memory.

Selecting a dataset starts a separate analysis request. The backend retrieves the UCI data, computes profiles and evidence with Pandas/NumPy, then optionally asks Gemini to interpret the verified profile for suitability. Exploration reuses cached data for grouped summaries. `DEMO_MODE=true` uses labeled cached fixtures without live UCI or Gemini calls.

## Build, Test, and Development Commands

Install backend dependencies in the repository virtual environment, then run:

```bash
cd backend
../.venv/bin/pip install -r requirements.txt
PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --reload
```

Run backend tests and compilation checks with `PYTHONPATH=. ../.venv/bin/pytest -q` and `../.venv/bin/python -m compileall -q app tests`. For the frontend, run `cd frontend && npm install`, use `npm run dev` for local development, and `npm run build` for TypeScript compilation plus the Vite production build.

## Coding Style & Naming Conventions

Use PEP 8 and type public Python interfaces. Keep FastAPI routes thin, isolate external services, validate API data with Pydantic, and use Pandas/NumPy for statistics. React code uses functional components, typed props/API models, semantic controls, and strict TypeScript (`frontend/tsconfig.json`). Keep Gemini output validated, preserve source provenance, and do not invent metadata or statistics.

## Testing Guidelines

Backend tests use pytest and follow `test_*.py` naming. Use fakes/mocks for Gemini and UCI integrations; live tests depend on network, quota, and provider access. The frontend has no configured unit-test runner, so `npm run build` is its automated validation command.

## Commit & Pull Request Guidelines

Recent history uses concise conventional prefixes such as `feat:` and `fix:` (for example, `feat: Add response validation for Gemini service`). Follow that pattern with an imperative, focused subject. Pull requests should explain behavior changes, identify relevant tests and commands run, and include screenshots for visible frontend changes.

## Security & Configuration

Copy `backend/.env.example` to `backend/.env` for live Gemini use, or set `DEMO_MODE=true` for the cached offline workflow. Never commit credentials, raw API keys, datasets, or unnecessary sensitive logs; keep external error messages sanitized.
