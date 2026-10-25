"""Safely rebuild all semantic and shared-dataset research connections.

Run from backend with:
    PYTHONPATH=. ../.venv/bin/python scripts/rebuild_research_connections.py

For missing embeddings, run backfill_research_embeddings.py first. This command
uses idempotent upserts and never calls Gemini or downloads raw datasets.
"""

from __future__ import annotations

from app.research.semantic_connections import generate_semantic_connections
from app.research.shared_dataset_connections import generate_shared_dataset_connections
from database.connection import close_database, open_database


def main() -> int:
    open_database()
    try:
        semantic = generate_semantic_connections()
        shared = generate_shared_dataset_connections()
    finally:
        close_database()
    print(
        "research connections rebuild complete "
        f"semantic_generated={semantic.connections_generated} "
        f"shared_generated={shared.connections_generated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
