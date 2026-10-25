from __future__ import annotations

from typing import Any

from database.connection import get_connection


ResearchQuery = dict[str, Any]


def _row_to_query(row: tuple[Any, ...]) -> ResearchQuery:
    return {
        "id": int(row[0]),
        "question": row[1],
        "normalized_question": row[2],
        "created_at": row[3],
    }


def save_research_question(
    question: str, normalized_question: str | None = None
) -> ResearchQuery:
    """Persist one research question using the shared database connection pool."""
    # The existing schema requires normalized_question. When no normalized form is
    # available, retaining the original question is the lossless fallback.
    stored_normalized_question = normalized_question or question

    connection = None
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                INSERT INTO research_queries (question, normalized_question)
                VALUES (%s, %s)
                RETURNING id, question, normalized_question, created_at
                """,
                (question, stored_normalized_question),
            ).fetchone()
            if row is None:
                raise RuntimeError("The research query insert returned no row")
            connection.commit()
            return _row_to_query(row)
    except Exception:
        # Explicit rollback makes the transaction boundary clear and protects
        # pooled connections if the database driver does not auto-rollback.
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise


def list_recent_research_questions(limit: int = 20) -> list[ResearchQuery]:
    """Return the newest persisted research questions first."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, question, normalized_question, created_at
            FROM research_queries
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
        return [_row_to_query(row) for row in rows]


def get_research_question(query_id: int) -> ResearchQuery | None:
    """Return a persisted research question by ID, if it exists."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, question, normalized_question, created_at
            FROM research_queries
            WHERE id = %s
            """,
            (query_id,),
        ).fetchone()
        return None if row is None else _row_to_query(row)
