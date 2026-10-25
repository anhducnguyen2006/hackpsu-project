from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

from app.api.routes import research as research_route
from app.main import app
from app.research import repository


class FakeConnection:
    def __init__(self, edge_rows, node_rows, dataset_rows) -> None:
        self.responses = [edge_rows, node_rows, dataset_rows]
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def execute(self, query: str, params: tuple[Any, ...]) -> "FakeConnection":
        self.calls.append((query, params))
        self.rows = self.responses.pop(0)
        return self

    def fetchall(self):
        return self.rows


def test_saved_graph_returns_nodes_edges_and_shared_dataset_explanations(monkeypatch) -> None:
    timestamp = datetime(2026, 10, 25, tzinfo=timezone.utc)
    connection = FakeConnection(
        edge_rows=[
            (8, 7, 12, repository.SHARED_DATASET, None, 2, timestamp),
            (9, 7, 13, repository.SEMANTIC_SIMILARITY, 0.91, 0, timestamp),
        ],
        node_rows=[
            (7, "Does rainfall affect yield?", timestamp),
            (12, "How does precipitation affect crops?", timestamp),
            (13, "Does temperature affect yield?", timestamp),
        ],
        dataset_rows=[
            (8, 41, "Rainfall observations", "UCI", "320"),
            (8, 42, "Crop yields", "Zenodo", "abc"),
        ],
    )
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    graph = repository.get_research_graph(limit=10)

    assert [node["data"]["id"] for node in graph["nodes"]] == [
        "research:7",
        "research:12",
        "research:13",
    ]
    shared = graph["edges"][0]["data"]
    assert shared["id"] == "research-connection:8"
    assert shared["source"] == "research:7"
    assert shared["target"] == "research:12"
    assert shared["relationship_type"] == "SHARED_DATASET"
    assert shared["similarity_score"] is None
    assert shared["shared_dataset_count"] == 2
    assert [item["dataset_id"] for item in shared["shared_datasets"]] == [41, 42]
    semantic = graph["edges"][1]["data"]
    assert semantic["relationship_type"] == "SEMANTIC_SIMILARITY"
    assert semantic["similarity_score"] == 0.91
    assert semantic["shared_datasets"] == []
    assert len(connection.calls) == 3


def test_saved_graph_supports_neighborhood_filter_and_edge_limit(monkeypatch) -> None:
    connection = FakeConnection(
        edge_rows=[(8, 7, 12, repository.SHARED_DATASET, None, 1, None)],
        node_rows=[(7, "Question 7", None), (12, "Question 12", None)],
        dataset_rows=[],
    )
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    repository.get_research_graph(limit=3, research_id=7)

    edge_query, params = connection.calls[0]
    assert "research_a_id = %s OR research_b_id = %s" in edge_query
    assert params == (7, 7, 3)


def test_saved_graph_returns_empty_graph_without_connections(monkeypatch) -> None:
    connection = FakeConnection([], [], [])
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    assert repository.get_research_graph() == {"nodes": [], "edges": []}
    assert len(connection.calls) == 1


def test_graph_endpoint_returns_typed_cytoscape_compatible_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        research_route,
        "get_research_graph",
        lambda limit, research_id: {
            "nodes": [
                {
                    "data": {
                        "id": "research:7",
                        "research_id": 7,
                        "type": "RESEARCH_QUESTION",
                        "label": "Question",
                        "question": "Question",
                        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    }
                }
            ],
            "edges": [],
        },
    )

    response = TestClient(app).get("/api/v1/research/graph?limit=5&research_id=7")

    assert response.status_code == 200
    assert response.json()["nodes"][0]["data"]["id"] == "research:7"
    assert response.json()["edges"] == []


def test_graph_endpoint_returns_empty_graph(monkeypatch) -> None:
    monkeypatch.setattr(
        research_route,
        "get_research_graph",
        lambda limit, research_id: {"nodes": [], "edges": []},
    )

    response = TestClient(app).get("/api/v1/research/graph")

    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}
