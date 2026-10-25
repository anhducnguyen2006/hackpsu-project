from __future__ import annotations

import numpy as np
import pytest

from app.api.schemas import DatasetRecord
from app.discovery.embeddings import EmbeddingService, EmbeddingServiceError


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts, **kwargs):
        values = list(texts)
        self.calls.append(values)
        vectors = []
        for text in values:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "climate" in lowered or "rainfall" in lowered else 0.0,
                    1.0 if "heart" in lowered or "cholesterol" in lowered else 0.0,
                ]
            )
        return np.asarray(vectors, dtype=np.float32)


def record(source_id: str, title: str, description: str) -> DatasetRecord:
    return DatasetRecord(
        id=f"test:{source_id}",
        source="Test",
        source_id=source_id,
        title=title,
        description=description,
        landing_page_url=f"https://example.org/{source_id}",
    )


def test_embedding_service_ranks_by_normalized_cosine_similarity() -> None:
    model = FakeModel()
    service = EmbeddingService(model_name="fake", model_version="test", model=model)
    climate = record("climate", "Climate observations", "Rainfall measurements")
    heart = record("heart", "Heart disease", "Cholesterol measurements")

    ranked = service.rank("How does rainfall vary with climate?", [heart, climate], top_k=2)

    assert [item[0].source_id for item in ranked] == ["climate", "heart"]
    assert ranked[0][1] == pytest.approx(1.0)
    assert ranked[1][1] == pytest.approx(0.0)
    assert model.calls == [
        ["How does rainfall vary with climate?"],
        [
            "Title: Heart disease\nDescription: Cholesterol measurements",
            "Title: Climate observations\nDescription: Rainfall measurements",
        ],
    ]


def test_dataset_embedding_cache_uses_content_hash_and_invalidates_changes() -> None:
    model = FakeModel()
    service = EmbeddingService(model=model)
    original = record("1", "Climate observations", "Rainfall measurements")
    changed = record("1", "Climate observations", "Heart cholesterol measurements")

    service.rank("climate", [original], top_k=1)
    service.rank("climate", [original], top_k=1)
    service.rank("climate", [changed], top_k=1)

    assert len(model.calls) == 5
    assert len(service._embedding_cache) == 1


def test_embedding_service_handles_empty_inputs_without_loading_model() -> None:
    service = EmbeddingService(model_name="fake")

    assert service.rank("question", [], top_k=5) == []
    assert service._model is None
    with pytest.raises(EmbeddingServiceError, match="empty"):
        service.rank(" ", [record("1", "Dataset", "Description")], top_k=1)
    assert service._model is None


def test_embedding_service_surfaces_model_errors() -> None:
    class BrokenModel:
        def encode(self, texts, **kwargs):
            raise RuntimeError("offline")

    service = EmbeddingService(model=BrokenModel())
    with pytest.raises(EmbeddingServiceError, match="failed"):
        service.rank("climate", [record("1", "Climate", "Rainfall")], top_k=1)
