# Research Dataset Discovery

An MVP monorepo for discovering and evaluating scientific research datasets.

## Project layout

- `backend/`: FastAPI service and the initial UCI dataset adapter
- `frontend/`: React + TypeScript + Vite interface

The development-only `GET /api/v1/dev/dataset-test` endpoint fetches UCI
Student Performance (dataset ID 320) through `ucimlrepo`, profiles its original
DataFrame with Pandas, and returns verified metadata and statistics.

