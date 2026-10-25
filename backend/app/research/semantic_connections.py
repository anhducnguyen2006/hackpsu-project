from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.discovery.embeddings import EmbeddingService
from app.research.repository import (
    SEMANTIC_SIMILARITY,
    _upsert_research_connection_with_connection,
)
from database.connection import get_connection

DEFAULT_SIMILARITY_THRESHOLD = 0.75
DEFAULT_MAX_NEIGHBORS = 5


@dataclass(frozen=True)
class SemanticConnectionRun:
    model_identifier: str
    embedding_dimensions: int
    similarity_threshold: float
    max_neighbors: int
    source_questions: int
    missing_embeddings: int
    incompatible_model_embeddings: int
    connections_generated: int


def generate_semantic_connections(
    embedding_service: Any | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    research_id: int | None = None,
) -> SemanticConnectionRun:
    """Persist nearest-neighbor semantic links for one exact local model.

    The threshold is a heuristic starting point, not a validated semantic
    equivalence cutoff. It should be calibrated against representative research
    questions before being treated as a product-level relevance rule.
    """
    if not 0 <= similarity_threshold <= 1:
        raise ValueError("similarity_threshold must be between 0 and 1")
    if max_neighbors <= 0:
        raise ValueError("max_neighbors must be positive")
    if research_id is not None and (not isinstance(research_id, int) or research_id <= 0):
        raise ValueError("research_id must be a positive integer")

    embedder = embedding_service or EmbeddingService()
    model_identifier = str(embedder.model_identifier)
    dimensions = int(
        getattr(embedder, "EMBEDDING_DIMENSIONS", EmbeddingService.EMBEDDING_DIMENSIONS)
    )
    if dimensions != EmbeddingService.EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Embedding model dimensions {dimensions} do not match research_queries.embedding vector({EmbeddingService.EMBEDDING_DIMENSIONS})"
        )

    connection = None
    try:
        with get_connection() as connection:
            model_query = """
                SELECT id, embedding_model
                FROM research_queries
                WHERE embedding IS NOT NULL
            """
            model_params: tuple[Any, ...] = ()
            if research_id is not None:
                model_query += " AND id = %s"
                model_params = (research_id,)
            model_query += " ORDER BY id"
            model_rows = connection.execute(model_query, model_params).fetchall()
            missing_row = connection.execute(
                """
                SELECT count(*)
                FROM research_queries
                WHERE embedding IS NULL
                """,
                (),
            ).fetchone()
            missing_embeddings = int(missing_row[0]) if missing_row else 0
            source_ids = [
                int(row[0]) for row in model_rows if row[1] == model_identifier
            ]
            incompatible_count = sum(
                1 for row in model_rows if row[1] != model_identifier
            )
            generated_pairs: set[tuple[int, int]] = set()
            for source_id in source_ids:
                candidate_rows = connection.execute(
                    """
                    SELECT candidate.id,
                           1 - (candidate.embedding <=> source.embedding)
                               AS similarity_score
                    FROM research_queries AS source
                    JOIN research_queries AS candidate
                      ON candidate.id <> source.id
                     AND candidate.embedding IS NOT NULL
                     AND candidate.embedding_model = %s
                    WHERE source.id = %s
                      AND source.embedding IS NOT NULL
                      AND source.embedding_model = %s
                      AND 1 - (candidate.embedding <=> source.embedding) >= %s
                    ORDER BY candidate.embedding <=> source.embedding,
                             candidate.id
                    LIMIT %s
                    """,
                    (
                        model_identifier,
                        source_id,
                        model_identifier,
                        similarity_threshold,
                        max_neighbors,
                    ),
                ).fetchall()
                for candidate_id, score in candidate_rows:
                    pair = (min(source_id, int(candidate_id)), max(source_id, int(candidate_id)))
                    if pair in generated_pairs:
                        continue
                    _upsert_research_connection_with_connection(
                        connection,
                        pair[0],
                        pair[1],
                        SEMANTIC_SIMILARITY,
                        float(score),
                    )
                    generated_pairs.add(pair)
            connection.commit()
            return SemanticConnectionRun(
                model_identifier=model_identifier,
                embedding_dimensions=dimensions,
                similarity_threshold=similarity_threshold,
                max_neighbors=max_neighbors,
                source_questions=len(source_ids),
                missing_embeddings=missing_embeddings,
                incompatible_model_embeddings=incompatible_count,
                connections_generated=len(generated_pairs),
            )
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        raise
