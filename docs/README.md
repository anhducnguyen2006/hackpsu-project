# ResearchLens Documentation

Last verified: 2026-10-24

ResearchLens is an AI-assisted scientific dataset discovery and evaluation prototype. This index describes the implementation in the repository, not hypothetical production infrastructure.

## Documents

- [API reference](./API.md)
- [Authentication](./AUTHENTICATION.md)
- [Architecture](./ARCHITECTURE.md)
- [Engineering conventions](./CONVENTIONS.md)
- [Data storage and persistence](./DATABASE.md)
- [Architectural decisions](./DECISIONS.md)
- [Observability and diagnostics](./OBSERVABILITY.md)
- [Product definition](./PRODUCT.md)
- [Request lifecycle and real-time behavior](./REALTIME.md)
- [Testing and validation](./TESTING.md)
- [UI/UX design system](./design/README.md)

## Quick start

Backend:

```bash
cd backend
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Copy `backend/.env.example` to `backend/.env` and provide credentials only for live Gemini use. Set `DEMO_MODE=true` for the offline cached presentation.
