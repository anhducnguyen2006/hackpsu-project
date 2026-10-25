from __future__ import annotations

from typing import Any

import pytest

from app.api.schemas import DatasetRecord, DatasetResult, DatasetVariable
from app.research import repository


class FakeConnection:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def execute(self, query: str, params: tuple[Any, ...]) -> "FakeConnection":
        self.calls.append((query, params))
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.rows.pop(0) if self.rows else None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def dataset(**updates: Any) -> DatasetRecord:
    values: dict[str, Any] = {
        "id": "zenodo:123",
        "source": "Zenodo",
        "source_id": "123",
        "title": "Rainfall observations",
        "description": "Verified dataset description",
        "landing_page_url": "https://zenodo.org/records/123",
        "variables": [DatasetVariable(name="rainfall")],
        "subjects": ["climate"],
        "doi": "10.5281/zenodo.123",
    }
    values.update(updates)
    return DatasetRecord(**values)


def test_upsert_dataset_inserts_verified_metadata_and_uses_identity(monkeypatch) -> None:
    connection = FakeConnection([(41,)])
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    dataset_id = repository.upsert_dataset(dataset())

    query, params = connection.calls[0]
    assert dataset_id == 41
    assert "ON CONFLICT (repository, external_id)" in query
    assert params[:5] == (
        "Zenodo",
        "123",
        "Rainfall observations",
        "https://zenodo.org/records/123",
        "Verified dataset description",
    )
    assert params[5].obj["source_id"] == "123"
    assert params[5].obj["variables"] == [{"name": "rainfall", "description": None, "data_type": None, "unit": None}]
    assert connection.commits == 1


def test_repeated_upsert_uses_same_database_identity_without_duplicates(monkeypatch) -> None:
    first = FakeConnection([(41,)])
    second = FakeConnection([(41,)])
    connections = iter([first, second])
    monkeypatch.setattr(repository, "get_connection", lambda: next(connections))

    assert repository.upsert_dataset(dataset(title="Original")) == 41
    assert repository.upsert_dataset(dataset(title="Updated")) == 41
    assert "title = EXCLUDED.title" in second.calls[0][0]
    assert second.calls[0][1][2] == "Updated"


def test_upsert_dataset_rejects_missing_external_id(monkeypatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(repository, "get_connection", lambda: connection)
    missing_id = DatasetResult(
        dataset_id="zenodo:123",
        source="Zenodo",
        source_id=None,
        title="Dataset without an external ID",
        repository_url="https://zenodo.org/records/123",
        data_status="metadata_only",
        relevance_explanation="Verified metadata match.",
    )

    with pytest.raises(ValueError, match="verified external dataset ID"):
        repository.upsert_dataset(missing_id)

    assert connection.calls == []


def test_query_dataset_match_is_parameterized_and_upserted(monkeypatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    repository.save_query_dataset_match(7, 41, rank=2, relevance_score=0.91, explanation="Verified match")

    query, params = connection.calls[0]
    assert "ON CONFLICT (query_id, dataset_id)" in query
    assert params == (7, 41, 2, 0.91, "Verified match")
    assert connection.commits == 1


def test_query_dataset_match_preserves_missing_score_and_explanation(monkeypatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    repository.save_query_dataset_match(7, 41, rank=1)

    assert connection.calls[0][1] == (7, 41, 1, None, None)


def result(dataset_id: str, title: str, score: float) -> DatasetResult:
    return DatasetResult(
        dataset_id=f"uci:{dataset_id}",
        source="UCI Machine Learning Repository",
        source_id=dataset_id,
        title=title,
        repository_url=f"https://archive.ics.uci.edu/dataset/{dataset_id}",
        landing_page_url=f"https://archive.ics.uci.edu/dataset/{dataset_id}",
        data_status="available",
        semantic_similarity_score=score,
        relevance_explanation="Verified metadata match.",
    )


def test_persist_discovery_result_commits_query_datasets_and_matches_atomically(
    monkeypatch,
) -> None:
    connection = FakeConnection([(99,), (41,), (42,)])
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    query_id = repository.persist_discovery_result(
        "Original question",
        "normalized question",
        [result("320", "Student Performance", 0.91), result("856", "Higher Education", 0.72)],
        user_sub="auth0|user-a",
    )

    assert query_id == 99
    assert len(connection.calls) == 5
    assert connection.calls[0][1] == (
        "Original question",
        "normalized question",
        "auth0|user-a",
    )
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_persist_discovery_result_rolls_back_partial_writes(monkeypatch) -> None:
    connection = FakeConnection([(99,), (41,)])
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    with pytest.raises(RuntimeError, match="dataset upsert returned"):
        repository.persist_discovery_result(
            "Original question",
            None,
            [result("320", "Student Performance", 0.91), result("856", "Higher Education", 0.72)],
            user_sub="auth0|user-a",
        )

    assert connection.commits == 0
    assert connection.rollbacks == 1
