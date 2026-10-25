from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections.abc import Sequence
from typing import Any

import numpy as np

from app.api.schemas import DatasetRecord
from app.config import settings

logger = logging.getLogger(__name__)

class EmbeddingServiceError(RuntimeError):
    """Raised when local semantic ranking cannot be completed."""


class EmbeddingService:
    """Lazy, process-local Sentence Transformers ranking for dataset metadata."""

    # BAAI/bge-small-en-v1.5 produces 384-dimensional embeddings.
    EMBEDDING_DIMENSIONS = 384

    def __init__(
        self,
        model_name: str = settings.embedding_model_name,
        model_version: str = settings.embedding_model_version,
        model: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.model_version = model_version
        self._model = model
        self._model_lock = threading.Lock()
        self._embedding_cache: dict[tuple[str, str, str, str], np.ndarray] = {}
        self._dataset_cache_keys: dict[tuple[str, str], tuple[str, str, str, str]] = {}

    @property
    def model_identifier(self) -> str:
        return f"{self.model_name}@{self.model_version}"

    def embed_text(self, text: str) -> np.ndarray:
        """Return one normalized local-model embedding for arbitrary text."""
        if not text or not text.strip():
            raise EmbeddingServiceError("Embedding text is empty.")
        return self._normalize_rows(self._encode([text.strip()]))[0]

    def rank(
        self,
        research_question: str,
        candidates: Sequence[DatasetRecord],
        top_k: int,
    ) -> list[tuple[DatasetRecord, float]]:
        if not candidates or top_k <= 0:
            return []
        if not research_question.strip():
            raise EmbeddingServiceError("Research question text is empty.")
        scores = self.score_queries([research_question], candidates)[0]
        ranked = list(zip(candidates, (scores.get(candidate.id, -1.0) for candidate in candidates)))
        ranked.sort(key=lambda item: (-item[1], item[0].id))
        return [(candidate, float(score)) for candidate, score in ranked[:top_k]]

    def score_queries(
        self,
        queries: Sequence[str],
        candidates: Sequence[DatasetRecord],
    ) -> list[dict[str, float]]:
        """Return normalized cosine scores for each query and candidate.

        Dataset vectors are cached independently from query vectors, so adding
        concepts does not repeat model work for unchanged repository metadata.
        """
        query_texts = [query.strip() for query in queries if query and query.strip()]
        if not query_texts or not candidates:
            return [{} for _ in query_texts]
        valid = [
            (candidate, self.dataset_text(candidate))
            for candidate in candidates
            if self.dataset_text(candidate).strip()
        ]
        if not valid:
            return [{} for _ in query_texts]
        try:
            query_started = time.perf_counter()
            query_matrix = self._normalize_rows(self._encode(query_texts))
            query_elapsed = (time.perf_counter() - query_started) * 1000
            candidate_started = time.perf_counter()
            candidate_matrix = self._candidate_embeddings(valid)
            candidate_elapsed = (time.perf_counter() - candidate_started) * 1000
            similarity_started = time.perf_counter()
            scores = np.clip(query_matrix @ candidate_matrix.T, -1.0, 1.0)
            logger.info(
                "discovery stage=vector_similarity queries=%d candidates=%d query_embedding_ms=%.1f candidate_embedding_ms=%.1f cosine_ms=%.1f",
                len(query_texts),
                len(valid),
                query_elapsed,
                candidate_elapsed,
                (time.perf_counter() - similarity_started) * 1000,
            )
            return [
                {candidate.id: float(score) for (candidate, _), score in zip(valid, row)}
                for row in scores
            ]
        except EmbeddingServiceError:
            raise
        except Exception as error:
            raise EmbeddingServiceError(f"Local semantic ranking failed: {error}") from error

    def _candidate_embeddings(
        self, valid: list[tuple[DatasetRecord, str]]
    ) -> np.ndarray:
        missing: list[tuple[DatasetRecord, str, tuple[str, str, str, str]]] = []
        embeddings: list[np.ndarray | None] = []
        for candidate, text in valid:
            key = self._cache_key(candidate, text)
            embedding = self._embedding_cache.get(key)
            embeddings.append(embedding)
            if embedding is None:
                missing.append((candidate, text, key))
        if missing:
            generated = self._normalize_rows(self._encode([text for _, text, _ in missing]))
            for (candidate, _, key), embedding in zip(missing, generated):
                previous_key = self._dataset_cache_keys.get((candidate.source, candidate.source_id))
                if previous_key and previous_key != key:
                    self._embedding_cache.pop(previous_key, None)
                self._embedding_cache[key] = embedding
                self._dataset_cache_keys[(candidate.source, candidate.source_id)] = key
            generated_by_key = {key: embedding for (_, _, key), embedding in zip(missing, generated)}
            embeddings = [
                embedding if embedding is not None else generated_by_key[self._cache_key(candidate, text)]
                for (candidate, text), embedding in zip(valid, embeddings)
            ]
        return np.vstack([embedding for embedding in embeddings if embedding is not None])

    def _encode(self, texts: list[str]) -> np.ndarray:
        model = self._model if self._model is not None else self._load_model()
        try:
            encoded = model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
            )
        except Exception as error:
            raise EmbeddingServiceError(
                f"Embedding model '{self.model_name}' failed: {error}"
            ) from error
        array = np.asarray(encoded, dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if array.ndim != 2 or array.shape[0] != len(texts):
            raise EmbeddingServiceError("Embedding model returned an invalid shape.")
        return array

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                return self._model
            except Exception as error:
                raise EmbeddingServiceError(
                    f"Embedding model '{self.model_name}' could not be loaded: {error}"
                ) from error

    @classmethod
    def dataset_text(cls, record: DatasetRecord) -> str:
        variables = "; ".join(
            f"{variable.name}: {variable.description}"
            if variable.description
            else variable.name
            for variable in record.variables
        )
        sections = [
            f"Title: {record.title}",
            f"Description: {record.description}" if record.description else "",
            f"Subjects: {', '.join(record.subjects)}" if record.subjects else "",
            f"Variables: {variables}" if variables else "",
            (
                f"Geographic coverage: {', '.join(record.geographic_coverage)}"
                if record.geographic_coverage
                else ""
            ),
            (
                f"Temporal coverage: {', '.join(record.temporal_coverage)}"
                if record.temporal_coverage
                else ""
            ),
        ]
        return "\n".join(section for section in sections if section).strip()

    def _cache_key(
        self, record: DatasetRecord, text: str
    ) -> tuple[str, str, str, str]:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return (
            f"{record.source}:{record.source_id}",
            content_hash,
            self.model_name,
            self.model_version,
        )

    @staticmethod
    def _normalize_rows(values: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise EmbeddingServiceError("Embedding model returned a zero vector.")
        return values / norms
