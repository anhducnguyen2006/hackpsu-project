from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.routes import research as research_route
from app.main import app
from app.research import repository


class FakeConnection:
    def __init__(self, row=None, rows=None) -> None:
        self.row = row
        self.rows = rows or []
        self.calls = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=()):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class FakeEmbedder:
    EMBEDDING_DIMENSIONS = 3
    model_identifier = "local-test-model@1"

    def embed_text(self, text: str):
        return [1.0, 0.0, 0.0]


def test_research_question_persists_embedding_and_model(monkeypatch) -> None:
    connection = FakeConnection(row=(12, "Question", "question", datetime.now(timezone.utc)))
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    saved = repository.save_research_question(
        "Question", "question", embedding_service=FakeEmbedder()
    )

    query, params = connection.calls[0]
    assert saved["id"] == 12
    assert "embedding" in query
    assert params[2] == "[1,0,0]"
    assert params[3] == "local-test-model@1"
    assert connection.commits == 1


def test_similarity_query_uses_cosine_distance_and_exact_model(monkeypatch) -> None:
    timestamp = datetime.now(timezone.utc)
    connection = FakeConnection(
        rows=[
            (2, "Similar", "similar", timestamp, 0.98),
            (1, "Related", "related", timestamp, 0.81),
        ]
    )
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    results = repository.find_similar_research_questions(
        [1.0, 0.0, 0.0], "local-test-model@1", limit=9
    )

    query, params = connection.calls[0]
    assert [item["id"] for item in results] == [2, 1]
    assert "embedding <=> %s::vector" in query
    assert "embedding_model = %s" in query
    assert params[1] == "local-test-model@1"
    assert params[3] == 5


def test_similarity_endpoint_returns_top_matches(monkeypatch) -> None:
    class RouteEmbedder(FakeEmbedder):
        model_identifier = "BAAI/bge-small-en-v1.5@1"

    monkeypatch.setattr(research_route, "embedding_service", RouteEmbedder())
    monkeypatch.setattr(
        research_route,
        "find_similar_research_questions",
        lambda embedding, embedding_model, limit: [
            {
                "id": 7,
                "question": "Related question",
                "normalized_question": "related question",
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "similarity_score": 0.9,
            }
        ],
    )

    response = TestClient(app).post(
        "/api/v1/research/similar",
        json={"research_question": "Find a related question"},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == 7
    assert response.json()[0]["similarity_score"] == 0.9


def test_similarity_endpoint_handles_empty_history(monkeypatch) -> None:
    monkeypatch.setattr(research_route, "embedding_service", FakeEmbedder())
    monkeypatch.setattr(
        research_route, "find_similar_research_questions", lambda *args, **kwargs: []
    )

    response = TestClient(app).post(
        "/api/v1/research/similar",
        json={"research_question": "No previous questions"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_similarity_endpoint_handles_unavailable_embeddings(monkeypatch) -> None:
    class BrokenEmbedder:
        model_identifier = "local-test-model@1"

        def embed_text(self, text: str):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(research_route, "embedding_service", BrokenEmbedder())

    response = TestClient(app).post(
        "/api/v1/research/similar",
        json={"research_question": "Embedding service unavailable"},
    )

    assert response.status_code == 200
    assert response.json() == []
