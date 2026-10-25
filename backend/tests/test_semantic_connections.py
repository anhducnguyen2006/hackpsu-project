from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.research import repository
from app.research.semantic_connections import generate_semantic_connections


class FakeEmbedder:
    EMBEDDING_DIMENSIONS = 384
    model_identifier = "BAAI/bge-small-en-v1.5@1"


class FakeConnection:
    def __init__(self, sources, missing, candidates) -> None:
        self.sources = sources
        self.missing = missing
        self.candidates = candidates
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
        if "SELECT id, embedding_model" in query:
            self._rows = self.sources
        elif "SELECT count(*)" in query:
            self._rows = [(self.missing,)]
        elif "SELECT candidate.id" in query:
            candidates = self.candidates.get(params[1], [])
            self._rows = [
                row for row in candidates if row[1] >= params[3]
            ][: params[4]]
        elif "INSERT INTO research_connections" in query:
            self.inserted.append(params)
            self._rows = [
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
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def run(
    monkeypatch,
    sources,
    candidates,
    threshold=0.75,
    max_neighbors=5,
    research_id=None,
):
    connection = FakeConnection(sources, 0, candidates)
    monkeypatch.setattr("app.research.semantic_connections.get_connection", lambda: connection)
    result = generate_semantic_connections(
        FakeEmbedder(), threshold, max_neighbors, research_id
    )
    return result, connection


def test_similar_questions_are_persisted_and_reciprocal_duplicates_are_skipped(
    monkeypatch,
) -> None:
    result, connection = run(
        monkeypatch,
        [(1, FakeEmbedder.model_identifier), (2, FakeEmbedder.model_identifier)],
        {1: [(2, 0.91)], 2: [(1, 0.91)]},
    )

    assert result.connections_generated == 1
    assert connection.inserted == [
        (1, 2, repository.SEMANTIC_SIMILARITY, 0.91, 0)
    ]
    assert connection.commits == 1


def test_unrelated_questions_below_threshold_are_not_linked(monkeypatch) -> None:
    result, connection = run(
        monkeypatch,
        [(1, FakeEmbedder.model_identifier), (2, FakeEmbedder.model_identifier)],
        {1: [(2, 0.30)], 2: [(1, 0.30)]},
    )

    assert result.connections_generated == 0
    assert connection.inserted == []


def test_candidate_ranking_and_neighbor_limit_are_honored(monkeypatch) -> None:
    result, connection = run(
        monkeypatch,
        [
            (1, FakeEmbedder.model_identifier),
            (2, FakeEmbedder.model_identifier),
            (3, FakeEmbedder.model_identifier),
        ],
        {1: [(3, 0.93), (2, 0.84)], 2: [], 3: []},
        max_neighbors=1,
    )

    assert result.connections_generated == 1
    assert connection.inserted[0][:4] == (
        1,
        3,
        repository.SEMANTIC_SIMILARITY,
        0.93,
    )


def test_missing_and_incompatible_embeddings_are_reported_and_not_compared(
    monkeypatch,
) -> None:
    connection = FakeConnection(
        [
            (1, FakeEmbedder.model_identifier),
            (2, "other-model@1"),
        ],
        4,
        {1: []},
    )
    monkeypatch.setattr("app.research.semantic_connections.get_connection", lambda: connection)

    result = generate_semantic_connections(FakeEmbedder())

    assert result.source_questions == 1
    assert result.missing_embeddings == 4
    assert result.incompatible_model_embeddings == 1
    assert result.connections_generated == 0
    assert connection.inserted == []


def test_empty_history_commits_without_creating_edges(monkeypatch) -> None:
    result, connection = run(monkeypatch, [], {})

    assert result.source_questions == 0
    assert result.connections_generated == 0
    assert connection.commits == 1
    assert connection.inserted == []


def test_scoped_generation_only_selects_the_new_research_question(monkeypatch) -> None:
    result, connection = run(
        monkeypatch,
        [(7, FakeEmbedder.model_identifier)],
        {7: []},
        research_id=7,
    )
    # The fake has one source; the production query adds the ID predicate.
    model_query, model_params = connection.calls[0]
    assert "AND id = %s" in model_query
    assert model_params == (7,)
    assert result.source_questions == 1


@pytest.mark.parametrize(
    ("threshold", "max_neighbors"),
    [(-0.1, 5), (1.1, 5), (0.75, 0)],
)
def test_generation_rejects_invalid_limits(monkeypatch, threshold, max_neighbors) -> None:
    with pytest.raises(ValueError):
        generate_semantic_connections(
            FakeEmbedder(), threshold, max_neighbors
        )
