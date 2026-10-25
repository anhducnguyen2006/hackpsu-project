"""Idempotently fill missing research question embeddings.

Run from backend with:
    PYTHONPATH=. ../.venv/bin/python scripts/backfill_research_embeddings.py
"""

from __future__ import annotations

import argparse

from app.discovery.embeddings import EmbeddingService
from app.research.repository import _vector_literal
from database.connection import close_database, get_connection, open_database


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=0, help="Maximum rows; 0 means all"
    )
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be non-negative")

    embedder = EmbeddingService()
    open_database()
    updated = 0
    failed = 0
    try:
        with get_connection() as connection:
            query = """
                SELECT id, normalized_question
                FROM research_queries
                WHERE embedding IS NULL
                ORDER BY id
            """
            params: tuple[int, ...] = ()
            if args.limit:
                query += " LIMIT %s"
                params = (args.limit,)
            rows = connection.execute(query, params).fetchall()
            for query_id, question in rows:
                try:
                    embedding = embedder.embed_text(question)
                    connection.execute(
                        """
                        UPDATE research_queries
                        SET embedding = %s::vector, embedding_model = %s
                        WHERE id = %s AND embedding IS NULL
                        """,
                        (
                            _vector_literal(embedding),
                            embedder.model_identifier,
                            query_id,
                        ),
                    )
                    updated += 1
                except Exception:
                    failed += 1
            connection.commit()
    finally:
        close_database()
    print(f"backfill complete updated={updated} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
