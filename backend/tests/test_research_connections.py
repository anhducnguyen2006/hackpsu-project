from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

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

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def connection_row(edge_id: int = 11) -> tuple[Any, ...]:
    return (
        edge_id,
        7,
        12,
        repository.SEMANTIC_SIMILARITY,
        0.88,
        0,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_upsert_normalizes_reversed_pair_and_uses_a_unique_conflict_key(monkeypatch) -> None:
    connection = FakeConnection([connection_row()])
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    saved = repository.upsert_research_connection(
        12,
        7,
        repository.SEMANTIC_SIMILARITY,
        similarity_score=0.88,
    )

    query, params = connection.calls[0]
    assert (saved["research_a_id"], saved["research_b_id"]) == (7, 12)
    assert params == (7, 12, "SEMANTIC_SIMILARITY", 0.88, 0)
    assert "ON CONFLICT (research_a_id, research_b_id, relationship_type)" in query
    assert connection.commits == 1


def test_duplicate_edges_are_upserted_by_the_database_constraint(monkeypatch) -> None:
    first = FakeConnection([connection_row()])
    second = FakeConnection([connection_row()])
    connections = iter([first, second])
    monkeypatch.setattr(repository, "get_connection", lambda: next(connections))

    repository.upsert_research_connection(7, 12, repository.SHARED_DATASET, shared_dataset_count=2)
    repository.upsert_research_connection(12, 7, repository.SHARED_DATASET, shared_dataset_count=3)

    assert first.calls[0][1][:3] == (7, 12, repository.SHARED_DATASET)
    assert second.calls[0][1][:3] == (7, 12, repository.SHARED_DATASET)
    assert "ON CONFLICT (research_a_id, research_b_id, relationship_type)" in second.calls[0][0]


@pytest.mark.parametrize(
    ("research_a_id", "research_b_id"),
    [(0, 2), (-1, 2), (2, 2), ("1", 2)],
)
def test_invalid_research_ids_are_rejected_before_database_write(
    monkeypatch, research_a_id, research_b_id
) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    with pytest.raises(ValueError):
        repository.upsert_research_connection(
            research_a_id, research_b_id, repository.SHARED_DATASET
        )

    assert connection.calls == []


def test_foreign_key_failure_rolls_back(monkeypatch) -> None:
    class ForeignKeyFailure(FakeConnection):
        def execute(self, query: str, params: tuple[Any, ...]) -> "FakeConnection":
            self.calls.append((query, params))
            raise RuntimeError("foreign key violation")

    connection = ForeignKeyFailure()
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    with pytest.raises(RuntimeError, match="foreign key"):
        repository.upsert_research_connection(7, 999, repository.SHARED_DATASET)

    assert connection.rollbacks == 1


def test_retrieve_connections_matches_either_side(monkeypatch) -> None:
    connection = FakeConnection([connection_row()])
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    connections = repository.get_research_connections(12)

    query, params = connection.calls[0]
    assert len(connections) == 1
    assert connections[0]["research_b_id"] == 12
    assert "research_a_id = %s OR research_b_id = %s" in query
    assert params == (12, 12)


def test_retrieve_rejects_invalid_id(monkeypatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    with pytest.raises(ValueError):
        repository.get_research_connections(0)

    assert connection.calls == []
