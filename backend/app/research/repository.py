from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from app.api.schemas import DataProfile, DatasetRecord, DatasetResult, ResearchAssessment
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


def persist_discovery_result(
    question: str,
    normalized_question: str | None,
    datasets: list[DatasetResult],
) -> int:
    """Atomically persist a live discovery query, datasets, and relationships."""
    connection = None
    try:
        with get_connection() as connection:
            query_row = connection.execute(
                """
                INSERT INTO research_queries (question, normalized_question)
                VALUES (%s, %s)
                RETURNING id
                """,
                (question, normalized_question or question),
            ).fetchone()
            if query_row is None:
                raise RuntimeError("The discovery query insert returned no ID")
            query_id = int(query_row[0])

            for rank, result in enumerate(datasets, start=1):
                dataset_row = _upsert_dataset_with_connection(connection, result)
                if dataset_row is None:
                    raise RuntimeError("The dataset upsert returned no database ID")
                dataset_id = int(dataset_row[0])
                relevance_score = (
                    result.preliminary_relevance_score
                    if result.preliminary_relevance_score is not None
                    else result.semantic_similarity_score
                )
                _save_query_dataset_match_with_connection(
                    connection,
                    query_id,
                    dataset_id,
                    rank,
                    relevance_score,
                    result.relevance_explanation,
                )
            connection.commit()
            return query_id
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise


def get_dataset_profile(
    dataset_id: int, source_version: str, profiler_version: str
) -> dict[str, Any] | None:
    """Load a profile only when dataset and both version keys match exactly."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT profile
            FROM dataset_profiles
            WHERE dataset_id = %s
              AND source_version = %s
              AND profiler_version = %s
            """,
            (dataset_id, source_version, profiler_version),
        ).fetchone()
        return None if row is None else row[0]


def save_dataset_profile(
    dataset_id: int,
    source_version: str,
    profiler_version: str,
    profile: DataProfile,
) -> int:
    """Persist one complete, JSON-compatible profile using the cache key."""
    profile_payload = DataProfile.model_validate(profile).model_dump(mode="json")
    connection = None
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                INSERT INTO dataset_profiles
                    (dataset_id, source_version, profiler_version, profile)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (dataset_id, source_version, profiler_version)
                DO UPDATE SET profile = EXCLUDED.profile
                RETURNING id
                """,
                (
                    dataset_id,
                    source_version,
                    profiler_version,
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
                    dataset_id = EXCLUDED.dataset_id,
                    profile_id = EXCLUDED.profile_id,
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
