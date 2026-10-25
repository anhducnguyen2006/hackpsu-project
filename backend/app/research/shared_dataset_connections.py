from __future__ import annotations

from dataclasses import dataclass

from app.research.repository import (
    SHARED_DATASET,
    _upsert_research_connection_with_connection,
)
from database.connection import get_connection


@dataclass(frozen=True)
class SharedDatasetConnectionRun:
    query_pairs_considered: int
    connections_generated: int


def generate_shared_dataset_connections(
    research_id: int | None = None,
) -> SharedDatasetConnectionRun:
    """Persist one edge per query pair sharing one or more exact datasets.

    The grouped join counts distinct dataset IDs, so duplicate match rows or
    multiple match records cannot inflate the stored shared-dataset count.
    """
    if research_id is not None and (not isinstance(research_id, int) or research_id <= 0):
        raise ValueError("research_id must be a positive integer")
    connection = None
    try:
        with get_connection() as connection:
            pair_query = """
                SELECT matches_a.query_id AS research_a_id,
                       matches_b.query_id AS research_b_id,
                       count(DISTINCT matches_a.dataset_id) AS shared_dataset_count
                FROM query_dataset_matches AS matches_a
                JOIN query_dataset_matches AS matches_b
                  ON matches_b.dataset_id = matches_a.dataset_id
                 AND matches_a.query_id < matches_b.query_id
            """
            pair_params: tuple[int, ...] = ()
            if research_id is not None:
                pair_query += " WHERE matches_a.query_id = %s OR matches_b.query_id = %s"
                pair_params = (research_id, research_id)
            pair_query += """
                GROUP BY matches_a.query_id, matches_b.query_id
                ORDER BY matches_a.query_id, matches_b.query_id
            """
            pair_rows = connection.execute(pair_query, pair_params).fetchall()
            for research_a_id, research_b_id, shared_dataset_count in pair_rows:
                _upsert_research_connection_with_connection(
                    connection,
                    int(research_a_id),
                    int(research_b_id),
                    SHARED_DATASET,
                    similarity_score=None,
                    shared_dataset_count=int(shared_dataset_count),
                )
            connection.commit()
            return SharedDatasetConnectionRun(
                query_pairs_considered=len(pair_rows),
                connections_generated=len(pair_rows),
            )
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise
