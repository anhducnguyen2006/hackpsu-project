from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.research import repository
from app.research.shared_dataset_connections import (
    generate_shared_dataset_connections,
)


class FakeConnection:
    def __init__(self, pair_rows=None, shared_rows=None) -> None:
        self.pair_rows = pair_rows or []
        self.shared_rows = shared_rows or []
        self.rows: list[tuple[Any, ...]] = []
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.inserted: list[tuple[Any, ...]] = []
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> "FakeConnection":
        self.calls.append((query, params))
        if "GROUP BY matches_a.query_id" in query:
            self.rows = self.pair_rows
        elif "SELECT DISTINCT d.id" in query:
            self.rows = self.shared_rows
        elif "INSERT INTO research_connections" in query:
            self.inserted.append(params)
            self.rows = [
                (
                    len(self.inserted),
                    params[0],
                    params[1],
                    params[2],
                    params[3],
                    params[4],
                    datetime.now(timezone.utc),
                )
            ]
        else:
            raise AssertionError(f"Unexpected query: {query}")
        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_overlapping_queries_create_one_canonical_edge_with_unique_count(monkeypatch) -> None:
    connection = FakeConnection([(9, 3, 2)])
    monkeypatch.setattr(
        "app.research.shared_dataset_connections.get_connection",
        lambda: connection,
    )

    result = generate_shared_dataset_connections()

    assert result.query_pairs_considered == 1
    assert result.connections_generated == 1
    assert connection.inserted == [
        (3, 9, repository.SHARED_DATASET, None, 2)
    ]
    assert connection.commits == 1
    assert "count(DISTINCT matches_a.dataset_id)" in connection.calls[0][0]
    assert "matches_a.query_id < matches_b.query_id" in connection.calls[0][0]


def test_nonoverlapping_queries_create_no_edges(monkeypatch) -> None:
    connection = FakeConnection([])
    monkeypatch.setattr(
        "app.research.shared_dataset_connections.get_connection",
        lambda: connection,
    )

    result = generate_shared_dataset_connections()

    assert result.query_pairs_considered == 0
    assert result.connections_generated == 0
    assert connection.inserted == []
    assert connection.commits == 1


def test_scoped_generation_only_considers_pairs_touching_new_query(monkeypatch) -> None:
    connection = FakeConnection([(3, 9, 1)])
    monkeypatch.setattr(
        "app.research.shared_dataset_connections.get_connection",
        lambda: connection,
    )

    generate_shared_dataset_connections(research_id=9)

    pair_query, pair_params = connection.calls[0]
    assert "WHERE matches_a.query_id = %s OR matches_b.query_id = %s" in pair_query
    assert pair_params == (9, 9)


def test_generation_is_idempotent_via_connection_upsert(monkeypatch) -> None:
    first = FakeConnection([(1, 8, 2)])
    second = FakeConnection([(1, 8, 2)])
    connections = iter([first, second])
    monkeypatch.setattr(
        "app.research.shared_dataset_connections.get_connection",
        lambda: next(connections),
    )

    generate_shared_dataset_connections()
    generate_shared_dataset_connections()

    assert first.inserted == second.inserted == [
        (1, 8, repository.SHARED_DATASET, None, 2)
    ]
    assert "ON CONFLICT (research_a_id, research_b_id, relationship_type)" in second.calls[1][0]


def test_shared_dataset_explanation_returns_exact_ids_and_titles(monkeypatch) -> None:
    connection = FakeConnection(
        shared_rows=[
            (41, "Rainfall observations", "UCI", "320"),
            (42, "Crop yields", "Zenodo", "abc"),
        ]
    )
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    shared = repository.get_shared_datasets(12, 7)

    assert shared == [
        {
            "dataset_id": 41,
            "title": "Rainfall observations",
            "repository": "UCI",
            "external_id": "320",
        },
        {
            "dataset_id": 42,
            "title": "Crop yields",
            "repository": "Zenodo",
            "external_id": "abc",
        },
    ]
    assert connection.calls[0][1] == (12, 7)
    assert "query_dataset_matches" in connection.calls[0][0]
    assert "datasets" in connection.calls[0][0]
