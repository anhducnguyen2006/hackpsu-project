from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
from psycopg.types.json import Jsonb

from app.api.schemas import DataProfile, DatasetRecord, DatasetResult, ResearchAssessment
from database.connection import get_connection

logger = logging.getLogger(__name__)

ResearchQuery = dict[str, Any]
ResearchConnection = dict[str, Any]

SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
SHARED_DATASET = "SHARED_DATASET"
_RESEARCH_CONNECTION_TYPES = {SEMANTIC_SIMILARITY, SHARED_DATASET}


def _vector_literal(embedding: Any) -> str:
    values = np.asarray(embedding, dtype=np.float32)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("Embedding must be a finite one-dimensional vector")
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


def _question_embedding(
    normalized_question: str, embedding_service: Any | None
) -> tuple[str | None, str | None]:
    if embedding_service is None:
        return None, None
    try:
        embedding = embedding_service.embed_text(normalized_question)
        values = np.asarray(embedding, dtype=np.float32)
        expected_dimensions = getattr(
            embedding_service, "EMBEDDING_DIMENSIONS", values.size
        )
        if values.size != expected_dimensions:
            raise ValueError(
                f"Embedding dimension {values.size} does not match {expected_dimensions}"
            )
        return _vector_literal(values), str(embedding_service.model_identifier)
    except Exception:
        # Research persistence remains available when the optional local model
        # cannot be loaded; the row can be filled by the idempotent backfill.
        return None, None


def _row_to_query(row: tuple[Any, ...]) -> ResearchQuery:
    return {
        "id": int(row[0]),
        "question": row[1],
        "normalized_question": row[2],
        "created_at": row[3],
    }


class ResearchQueryAccessError(LookupError):
    """The query is missing or belongs to a different authenticated subject."""


class HistoryStorageError(RuntimeError):
    """TigerData could not be used to verify or save a research query."""


def _require_owner(user_sub: str) -> str:
    """Use only a verified subject. Client-supplied ids never reach this helper."""
    if not isinstance(user_sub, str) or not user_sub.strip():
        raise ValueError("A verified research owner is required.")
    return user_sub.strip()


def create_owned_query(
    question: str, normalized_question: str | None, user_sub: str
) -> int:
    """Insert one query owned by the verified subject and return its id."""
    owner = _require_owner(user_sub)
    stored_normalized_question = normalized_question or question
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO research_queries
                (question, normalized_question, user_sub)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (question, stored_normalized_question, owner),
        ).fetchone()
        if row is None:
            raise RuntimeError("The research query insert returned no ID")
        connection.commit()
        return int(row[0])


def require_owned_query(query_id: int, user_sub: str) -> int:
    """Confirm a query id belongs to this subject. Missing and foreign ids match."""
    try:
        found = get_research_question(query_id, user_sub)
    except ValueError:
        raise
    except Exception as error:
        raise HistoryStorageError(
            "Research storage could not verify this query."
        ) from error
    if found is None:
        raise ResearchQueryAccessError("Research query was not found.")
    return query_id


def _normalize_connection_pair(
    research_a_id: int, research_b_id: int
) -> tuple[int, int]:
    if not isinstance(research_a_id, int) or not isinstance(research_b_id, int):
        raise ValueError("Research IDs must be integers")
    if research_a_id <= 0 or research_b_id <= 0:
        raise ValueError("Research IDs must be positive")
    if research_a_id == research_b_id:
        raise ValueError("A research connection requires two different research IDs")
    return min(research_a_id, research_b_id), max(research_a_id, research_b_id)


def _row_to_research_connection(row: tuple[Any, ...]) -> ResearchConnection:
    return {
        "id": int(row[0]),
        "research_a_id": int(row[1]),
        "research_b_id": int(row[2]),
        "relationship_type": row[3],
        "similarity_score": row[4],
        "shared_dataset_count": int(row[5]),
        "created_at": row[6],
    }


def save_research_question(
    question: str,
    normalized_question: str | None = None,
    embedding_service: Any | None = None,
    *,
    user_sub: str,
) -> ResearchQuery:
    """Persist one research question using the shared database connection pool."""
    # The existing schema requires normalized_question. When no normalized form is
    # available, retaining the original question is the lossless fallback.
    owner = _require_owner(user_sub)
    stored_normalized_question = normalized_question or question
    embedding, embedding_model = _question_embedding(
        stored_normalized_question, embedding_service
    )

    connection = None
    try:
        with get_connection() as connection:
            if embedding is None:
                row = connection.execute(
                    """
                    INSERT INTO research_queries
                        (question, normalized_question, user_sub)
                    VALUES (%s, %s, %s)
                    RETURNING id, question, normalized_question, created_at
                    """,
                    (question, stored_normalized_question, owner),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    INSERT INTO research_queries
                        (question, normalized_question, embedding, embedding_model, user_sub)
                    VALUES (%s, %s, %s::vector, %s, %s)
                    RETURNING id, question, normalized_question, created_at
                    """,
                    (
                        question,
                        stored_normalized_question,
                        embedding,
                        embedding_model,
                        owner,
                    ),
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


def list_recent_research_questions(user_sub: str, limit: int = 20) -> list[ResearchQuery]:
    """Return the newest questions owned by this verified subject."""
    owner = _require_owner(user_sub)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, question, normalized_question, created_at
            FROM research_queries
            WHERE user_sub = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (owner, limit),
        ).fetchall()
        return [_row_to_query(row) for row in rows]


def get_research_question(query_id: int, user_sub: str) -> ResearchQuery | None:
    """Return one owned question. Missing and unauthorized ids both return None."""
    owner = _require_owner(user_sub)
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, question, normalized_question, created_at
            FROM research_queries
            WHERE id = %s
              AND user_sub = %s
            """,
            (query_id, owner),
        ).fetchone()
        return None if row is None else _row_to_query(row)


def get_research_session(query_id: int, user_sub: str) -> ResearchQuery | None:
    """Return a saved query with only persisted matches and linked assessments."""
    owner = _require_owner(user_sub)
    with get_connection() as connection:
        query_row = connection.execute(
            """
            SELECT id, question, normalized_question, created_at
            FROM research_queries
            WHERE id = %s
              AND user_sub = %s
            """,
            (query_id, owner),
        ).fetchone()
        if query_row is None:
            return None
        match_rows = connection.execute(
            """
            SELECT d.metadata, m.rank, m.relevance_score, m.explanation
            FROM query_dataset_matches AS m
            JOIN datasets AS d ON d.id = m.dataset_id
            JOIN research_queries AS q ON q.id = m.query_id
            WHERE m.query_id = %s
              AND q.user_sub = %s
            ORDER BY m.rank NULLS LAST, d.id
            """,
            (query_id, owner),
        ).fetchall()
        assessment_rows = connection.execute(
            """
            SELECT a.dataset_id, a.model, a.assessment_version, a.assessment,
                   a.suitability_score, a.created_at
            FROM research_assessments AS a
            JOIN research_queries AS q ON q.id = a.query_id
            WHERE a.query_id = %s
              AND q.user_sub = %s
            ORDER BY a.created_at DESC, a.id DESC
            """,
            (query_id, owner),
        ).fetchall()
        result = _row_to_query(query_row)
        result["datasets"] = [
            {
                "metadata": row[0],
                "rank": row[1],
                "relevance_score": row[2],
                "explanation": row[3],
            }
            for row in match_rows
        ]
        result["assessments"] = [
            {
                "dataset_id": row[0],
                "model": row[1],
                "assessment_version": row[2],
                "assessment": row[3],
                "suitability_score": row[4],
                "created_at": row[5],
            }
            for row in assessment_rows
        ]
        return result


PersistableDataset = DatasetRecord | DatasetResult


def _dataset_metadata(dataset: PersistableDataset) -> dict[str, Any]:
    """Return only verified, JSON-compatible metadata from a discovery record."""
    if not dataset.source_id or not dataset.source_id.strip():
        raise ValueError(
            "Cannot persist a dataset without a verified external dataset ID"
        )
    return dataset.model_dump(mode="json")


def upsert_dataset(dataset: PersistableDataset) -> int:
    """Insert or update a discovered dataset and return its database ID.

    Dataset identity is the source repository plus its verified external ID. The
    full normalized discovery record is retained in the existing JSONB metadata
    column for provenance and future fields.
    """
    metadata = _dataset_metadata(dataset)
    source_url_value = getattr(dataset, "landing_page_url", None)
    if source_url_value is None:
        source_url_value = getattr(dataset, "repository_url", None)
    source_url = str(source_url_value) if source_url_value else None
    connection = None
    try:
        with get_connection() as connection:
            row = _upsert_dataset_with_connection(connection, dataset)
            if row is None:
                raise RuntimeError("The dataset upsert returned no database ID")
            connection.commit()
            return int(row[0])
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise


def _upsert_dataset_with_connection(
    connection: Any, dataset: PersistableDataset
) -> tuple[Any, ...] | None:
    metadata = _dataset_metadata(dataset)
    source_url_value = getattr(dataset, "landing_page_url", None)
    if source_url_value is None:
        source_url_value = getattr(dataset, "repository_url", None)
    source_url = str(source_url_value) if source_url_value else None
    return connection.execute(
        """
        INSERT INTO datasets
            (repository, external_id, title, source_url, description, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (repository, external_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            source_url = EXCLUDED.source_url,
            description = EXCLUDED.description,
            metadata = EXCLUDED.metadata
        RETURNING id
        """,
        (
            dataset.source,
            dataset.source_id,
            dataset.title,
            source_url,
            dataset.description,
            Jsonb(metadata),
        ),
    ).fetchone()


def save_query_dataset_match(
    query_id: int,
    dataset_id: int,
    rank: int | None = None,
    relevance_score: float | None = None,
    explanation: str | None = None,
) -> None:
    """Insert or update one query-to-dataset relationship.

    Score and explanation remain NULL when the discovery pipeline did not provide
    them; this function never creates a value for either field.
    """
    connection = None
    try:
        with get_connection() as connection:
            _save_query_dataset_match_with_connection(
                connection, query_id, dataset_id, rank, relevance_score, explanation
            )
            connection.commit()
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise


def _save_query_dataset_match_with_connection(
    connection: Any,
    query_id: int,
    dataset_id: int,
    rank: int | None,
    relevance_score: float | None,
    explanation: str | None,
) -> None:
    connection.execute(
        """
        INSERT INTO query_dataset_matches
            (query_id, dataset_id, rank, relevance_score, explanation)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (query_id, dataset_id)
        DO UPDATE SET
            rank = EXCLUDED.rank,
            relevance_score = EXCLUDED.relevance_score,
            explanation = EXCLUDED.explanation
        """,
        (query_id, dataset_id, rank, relevance_score, explanation),
    )


def upsert_research_connection(
    research_a_id: int,
    research_b_id: int,
    relationship_type: str,
    similarity_score: float | None = None,
    shared_dataset_count: int = 0,
) -> ResearchConnection:
    """Insert or update one normalized edge between saved research questions."""
    research_a_id, research_b_id = _normalize_connection_pair(
        research_a_id, research_b_id
    )
    if relationship_type not in _RESEARCH_CONNECTION_TYPES:
        raise ValueError(
            "relationship_type must be SEMANTIC_SIMILARITY or SHARED_DATASET"
        )
    if shared_dataset_count < 0:
        raise ValueError("shared_dataset_count must not be negative")

    connection = None
    try:
        with get_connection() as connection:
            row = _upsert_research_connection_with_connection(
                connection,
                research_a_id,
                research_b_id,
                relationship_type,
                similarity_score,
                shared_dataset_count,
            )
            if row is None:
                raise RuntimeError("The research connection upsert returned no row")
            connection.commit()
            return row
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise


def _upsert_research_connection_with_connection(
    connection: Any,
    research_a_id: int,
    research_b_id: int,
    relationship_type: str,
    similarity_score: float | None = None,
    shared_dataset_count: int = 0,
) -> ResearchConnection:
    """Upsert an edge inside a caller-owned transaction."""
    research_a_id, research_b_id = _normalize_connection_pair(
        research_a_id, research_b_id
    )
    if relationship_type not in _RESEARCH_CONNECTION_TYPES:
        raise ValueError(
            "relationship_type must be SEMANTIC_SIMILARITY or SHARED_DATASET"
        )
    if shared_dataset_count < 0:
        raise ValueError("shared_dataset_count must not be negative")
    row = connection.execute(
        """
        INSERT INTO research_connections
            (research_a_id, research_b_id, relationship_type,
             similarity_score, shared_dataset_count)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (research_a_id, research_b_id, relationship_type)
        DO UPDATE SET
            similarity_score = EXCLUDED.similarity_score,
            shared_dataset_count = EXCLUDED.shared_dataset_count
        RETURNING id, research_a_id, research_b_id, relationship_type,
                  similarity_score, shared_dataset_count, created_at
        """,
        (
            research_a_id,
            research_b_id,
            relationship_type,
            similarity_score,
            shared_dataset_count,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("The research connection upsert returned no row")
    return _row_to_research_connection(row)


def get_research_connections(research_id: int) -> list[ResearchConnection]:
    """Return all edges touching one saved research question."""
    if not isinstance(research_id, int) or research_id <= 0:
        raise ValueError("research_id must be a positive integer")
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, research_a_id, research_b_id, relationship_type,
                   similarity_score, shared_dataset_count, created_at
            FROM research_connections
            WHERE research_a_id = %s OR research_b_id = %s
            ORDER BY created_at DESC, id DESC
            """,
            (research_id, research_id),
        ).fetchall()
        return [_row_to_research_connection(row) for row in rows]


def get_shared_datasets(
    research_a_id: int, research_b_id: int
) -> list[dict[str, Any]]:
    """Return exact datasets shared by two saved research questions."""
    research_a_id, research_b_id = _normalize_connection_pair(
        research_a_id, research_b_id
    )
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT d.id, d.title, d.repository, d.external_id
            FROM query_dataset_matches AS match_a
            JOIN query_dataset_matches AS match_b
              ON match_b.dataset_id = match_a.dataset_id
             AND match_b.query_id = %s
            JOIN datasets AS d ON d.id = match_a.dataset_id
            WHERE match_a.query_id = %s
            ORDER BY d.id
            """,
            (research_b_id, research_a_id),
        ).fetchall()
        return [
            {
                "dataset_id": int(row[0]),
                "title": row[1],
                "repository": row[2],
                "external_id": row[3],
            }
            for row in rows
        ]


def get_research_graph(
    limit: int = 100, research_id: int | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Return a bounded saved-research graph without per-edge queries."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    if research_id is not None and (
        not isinstance(research_id, int) or research_id <= 0
    ):
        raise ValueError("research_id must be a positive integer")

    with get_connection() as connection:
        edge_query = """
            SELECT id, research_a_id, research_b_id, relationship_type,
                   similarity_score, shared_dataset_count, created_at
            FROM research_connections
        """
        edge_params: list[Any] = []
        if research_id is not None:
            edge_query += " WHERE research_a_id = %s OR research_b_id = %s"
            edge_params.extend((research_id, research_id))
        edge_query += " ORDER BY created_at DESC, id DESC LIMIT %s"
        edge_params.append(limit)
        edge_rows = connection.execute(edge_query, tuple(edge_params)).fetchall()
        if not edge_rows:
            return {"nodes": [], "edges": []}

        edge_ids = [int(row[0]) for row in edge_rows]
        research_ids = sorted(
            {int(row[1]) for row in edge_rows}
            | {int(row[2]) for row in edge_rows}
        )
        node_rows = connection.execute(
            """
            SELECT id, question, created_at
            FROM research_queries
            WHERE id = ANY(%s)
            ORDER BY id
            """,
            (research_ids,),
        ).fetchall()
        dataset_rows = connection.execute(
            """
            SELECT connection.id, dataset.id, dataset.title,
                   dataset.repository, dataset.external_id
            FROM research_connections AS connection
            JOIN query_dataset_matches AS match_a
              ON match_a.query_id = connection.research_a_id
            JOIN query_dataset_matches AS match_b
              ON match_b.query_id = connection.research_b_id
             AND match_b.dataset_id = match_a.dataset_id
            JOIN datasets AS dataset ON dataset.id = match_a.dataset_id
            WHERE connection.id = ANY(%s)
              AND connection.relationship_type = 'SHARED_DATASET'
            GROUP BY connection.id, dataset.id, dataset.title,
                     dataset.repository, dataset.external_id
            ORDER BY connection.id, dataset.id
            """,
            (edge_ids,),
        ).fetchall()

        datasets_by_edge: dict[int, list[dict[str, Any]]] = {}
        for row in dataset_rows:
            datasets_by_edge.setdefault(int(row[0]), []).append(
                {
                    "dataset_id": int(row[1]),
                    "title": row[2],
                    "repository": row[3],
                    "external_id": row[4],
                }
            )
        nodes = [
            {
                "data": {
                    "id": f"research:{int(row[0])}",
                    "research_id": int(row[0]),
                    "type": "RESEARCH_QUESTION",
                    "label": row[1],
                    "question": row[1],
                    "created_at": row[2],
                }
            }
            for row in node_rows
        ]
        edges = []
        for row in edge_rows:
            edge_id = int(row[0])
            relationship_type = row[3]
            shared_datasets = datasets_by_edge.get(edge_id, [])
            if relationship_type == SHARED_DATASET:
                evidence = (
                    f"{int(row[5])} shared discovered dataset(s): "
                    + ", ".join(item["title"] for item in shared_datasets)
                )
            else:
                evidence = (
                    f"Cosine similarity between saved research embeddings: "
                    f"{float(row[4]):.4f}"
                    if row[4] is not None
                    else "Saved research questions have a semantic similarity connection."
                )
            edges.append(
                {
                    "data": {
                        "id": f"research-connection:{edge_id}",
                        "source": f"research:{int(row[1])}",
                        "target": f"research:{int(row[2])}",
                        "relationship_type": relationship_type,
                        "similarity_score": row[4],
                        "shared_dataset_count": int(row[5]),
                        "shared_datasets": shared_datasets,
                        "evidence": evidence,
                        "created_at": row[6],
                    }
                }
            )
        return {"nodes": nodes, "edges": edges}


def persist_discovery_result(
    question: str,
    normalized_question: str | None,
    datasets: list[DatasetResult],
    embedding_service: Any | None = None,
    *,
    user_sub: str,
    research_query_id: int | None = None,
) -> int:
    """Atomically persist a live discovery query, datasets, and relationships."""
    owner = _require_owner(user_sub)
    connection = None
    started = time.perf_counter()
    embedding_started = time.perf_counter()
    try:
        connection_started = time.perf_counter()
        connection_context = get_connection()
        with connection_context as connection:
            logger.info(
                "discovery persistence stage=connection_acquisition elapsed_ms=%.1f",
                (time.perf_counter() - connection_started) * 1000,
            )
            stored_normalized_question = normalized_question or question
            embedding, embedding_model = _question_embedding(
                stored_normalized_question, embedding_service
            )
            logger.info(
                "discovery persistence stage=embedding elapsed_ms=%.1f",
                (time.perf_counter() - embedding_started) * 1000,
            )
            query_started = time.perf_counter()
            if research_query_id is not None:
                query_row = connection.execute(
                    """
                    SELECT id
                    FROM research_queries
                    WHERE id = %s
                      AND user_sub = %s
                    """,
                    (research_query_id, owner),
                ).fetchone()
                if query_row is None:
                    raise RuntimeError(
                        "The research query is not available for this user."
                    )
                query_id = int(query_row[0])
                if embedding is not None:
                    connection.execute(
                        """
                        UPDATE research_queries
                        SET normalized_question = %s,
                            embedding = %s::vector,
                            embedding_model = %s
                        WHERE id = %s
                          AND user_sub = %s
                        """,
                        (
                            stored_normalized_question,
                            embedding,
                            embedding_model,
                            query_id,
                            owner,
                        ),
                    )
            elif embedding is None:
                query_row = connection.execute(
                    """
                    INSERT INTO research_queries
                        (question, normalized_question, user_sub)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (question, stored_normalized_question, owner),
                ).fetchone()
                if query_row is None:
                    raise RuntimeError("The discovery query insert returned no ID")
                query_id = int(query_row[0])
            else:
                query_row = connection.execute(
                    """
                    INSERT INTO research_queries
                        (question, normalized_question, embedding, embedding_model, user_sub)
                    VALUES (%s, %s, %s::vector, %s, %s)
                    RETURNING id
                    """,
                    (
                        question,
                        stored_normalized_question,
                        embedding,
                        embedding_model,
                        owner,
                    ),
                ).fetchone()
                if query_row is None:
                    raise RuntimeError("The discovery query insert returned no ID")
                query_id = int(query_row[0])
            logger.info(
                "discovery persistence stage=research_question_insert elapsed_ms=%.1f",
                (time.perf_counter() - query_started) * 1000,
            )

            upsert_started = time.perf_counter()
            relationship_started = time.perf_counter()
            for rank, result in enumerate(datasets, start=1):
                item_started = time.perf_counter()
                dataset_row = _upsert_dataset_with_connection(connection, result)
                if dataset_row is None:
                    raise RuntimeError("The dataset upsert returned no database ID")
                logger.info(
                    "discovery persistence stage=dataset_metadata_upsert elapsed_ms=%.1f dataset=%s",
                    (time.perf_counter() - item_started) * 1000,
                    result.source_id,
                )
                dataset_id = int(dataset_row[0])
                relevance_score = (
                    result.preliminary_relevance_score
                    if result.preliminary_relevance_score is not None
                    else result.semantic_similarity_score
                )
                relationship_item_started = time.perf_counter()
                _save_query_dataset_match_with_connection(
                    connection,
                    query_id,
                    dataset_id,
                    rank,
                    relevance_score,
                    result.relevance_explanation,
                )
                logger.info(
                    "discovery persistence stage=relationship_insert elapsed_ms=%.1f dataset=%s",
                    (time.perf_counter() - relationship_item_started) * 1000,
                    result.source_id,
                )
            logger.info(
                "discovery persistence stage=dataset_upserts_total elapsed_ms=%.1f count=%d",
                (time.perf_counter() - upsert_started) * 1000,
                len(datasets),
            )
            connection.commit()
            logger.info(
                "discovery persistence stage=transaction_commit elapsed_ms=%.1f",
                (time.perf_counter() - relationship_started) * 1000,
            )
            logger.info(
                "discovery persistence stage=total elapsed_ms=%.1f",
                (time.perf_counter() - started) * 1000,
            )
            return query_id
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise


def find_similar_research_questions(
    embedding: Any, embedding_model: str, user_sub: str, limit: int = 5
) -> list[ResearchQuery]:
    """Find top exact-model matches owned by this verified subject."""
    owner = _require_owner(user_sub)
    if limit <= 0:
        return []
    vector = _vector_literal(embedding)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                question,
                normalized_question,
                created_at,
                1 - (embedding <=> %s::vector) AS similarity_score
            FROM research_queries
            WHERE embedding IS NOT NULL
              AND embedding_model = %s
              AND user_sub = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, embedding_model, owner, vector, min(limit, 5)),
        ).fetchall()
        return [
            {
                **_row_to_query(row[:4]),
                "similarity_score": float(row[4]),
            }
            for row in rows
        ]


def get_dataset_profile(
    dataset_id: int,
    source_version: str,
    profiler_version: str,
    resource_key: str = "",
) -> dict[str, Any] | None:
    """Load a profile only when the dataset, file, and both versions match."""
    row = get_dataset_profile_row(
        dataset_id, source_version, profiler_version, resource_key
    )
    return None if row is None else row[1]


def get_dataset_profile_row(
    dataset_id: int,
    source_version: str,
    profiler_version: str,
    resource_key: str = "",
) -> tuple[int, dict[str, Any]] | None:
    """Return the profile row id and JSON for one file version."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, profile
            FROM dataset_profiles
            WHERE dataset_id = %s
              AND source_version = %s
              AND profiler_version = %s
              AND resource_key = %s
            """,
            (dataset_id, source_version, profiler_version, resource_key),
        ).fetchone()
        if row is None:
            return None
        return int(row[0]), row[1]


def save_dataset_profile(
    dataset_id: int,
    source_version: str,
    profiler_version: str,
    profile: DataProfile,
    resource_key: str = "",
) -> int:
    """Persist one complete profile for one dataset file and version."""
    profile_payload = DataProfile.model_validate(profile).model_dump(mode="json")
    connection = None
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                INSERT INTO dataset_profiles
                    (dataset_id, source_version, profiler_version, resource_key, profile)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (dataset_id, resource_key, source_version, profiler_version)
                DO UPDATE SET profile = EXCLUDED.profile
                RETURNING id
                """,
                (
                    dataset_id,
                    source_version,
                    profiler_version,
                    resource_key,
                    Jsonb(profile_payload),
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError("The dataset profile save returned no database ID")
            connection.commit()
            return int(row[0])
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise


def get_cached_research_assessment(cache_key: str) -> dict[str, Any] | None:
    """Return a completed assessment stored for one exact input fingerprint."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT assessment
            FROM research_assessments
            WHERE cache_key = %s
              AND assessment IS NOT NULL
            LIMIT 1
            """,
            (cache_key,),
        ).fetchone()
        return None if row is None else row[0]


def save_research_assessment(
    *,
    cache_key: str,
    dataset_id: int,
    model: str,
    assessment_version: str,
    assessment: ResearchAssessment,
    query_id: int | None = None,
    profile_id: int | None = None,
) -> int:
    """Save one validated, completed suitability assessment for an exact key."""
    assessment_payload = ResearchAssessment.model_validate(assessment).model_dump(
        mode="json"
    )
    connection = None
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                INSERT INTO research_assessments
                    (
                        query_id,
                        dataset_id,
                        profile_id,
                        model,
                        assessment_version,
                        cache_key,
                        assessment,
                        suitability_score
                    )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cache_key) WHERE cache_key IS NOT NULL
                DO UPDATE SET
                    query_id = COALESCE(research_assessments.query_id, EXCLUDED.query_id),
                    dataset_id = EXCLUDED.dataset_id,
                    profile_id = COALESCE(research_assessments.profile_id, EXCLUDED.profile_id),
                    model = EXCLUDED.model,
                    assessment_version = EXCLUDED.assessment_version,
                    assessment = EXCLUDED.assessment,
                    suitability_score = EXCLUDED.suitability_score
                RETURNING id
                """,
                (
                    query_id,
                    dataset_id,
                    profile_id,
                    model,
                    assessment_version,
                    cache_key,
                    Jsonb(assessment_payload),
                    assessment.final_score,
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError("The research assessment save returned no ID")
            connection.commit()
            return int(row[0])
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise
