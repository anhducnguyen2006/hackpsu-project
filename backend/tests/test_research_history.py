from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import research as research_route
from app.research import repository


def _query(query_id: int, question: str) -> dict:
    return {
        "id": query_id,
        "question": question,
        "normalized_question": question.lower(),
        "created_at": datetime(2026, 10, 25, 12, query_id, tzinfo=timezone.utc),
    }


def test_research_history_returns_newest_queries(monkeypatch) -> None:
    expected = [_query(2, "Second question"), _query(1, "First question")]
    monkeypatch.setattr(research_route, "list_recent_research_questions", lambda limit: expected[:limit])

    response = TestClient(app).get("/api/v1/research/history?limit=2")

    assert response.status_code == 200
    assert response.json() == [
        {
            **item,
            "created_at": item["created_at"].isoformat().replace("+00:00", "Z"),
        }
        for item in expected
    ]


def test_research_query_returns_404_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(research_route, "get_research_question", lambda query_id: None)

    response = TestClient(app).get("/api/v1/research/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Research query not found"}


def test_research_query_returns_timestamp(monkeypatch) -> None:
    expected = _query(7, "Does rainfall affect yield?")
    monkeypatch.setattr(research_route, "get_research_question", lambda query_id: expected)

    response = TestClient(app).get("/api/v1/research/7")

    assert response.status_code == 200
    assert response.json()["id"] == 7
    assert response.json()["created_at"].endswith("Z")


def test_research_session_returns_saved_matches_and_assessments(monkeypatch) -> None:
    expected = {
        **_query(7, "Does rainfall affect yield?"),
        "datasets": [
            {
                "metadata": {"title": "Rainfall observations"},
                "rank": 1,
                "relevance_score": 0.9,
                "explanation": "Verified match.",
            }
        ],
        "assessments": [
            {
                "dataset_id": 3,
                "model": "gemini",
                "assessment_version": "v1",
                "assessment": {"overall_assessment": "Useful"},
                "suitability_score": 80,
                "created_at": datetime(2026, 10, 25, tzinfo=timezone.utc),
            }
        ],
    }
    monkeypatch.setattr(research_route, "get_research_session", lambda query_id: expected)

    response = TestClient(app).get("/api/v1/research/7/session")

    assert response.status_code == 200
    assert response.json()["datasets"][0]["metadata"]["title"] == "Rainfall observations"
    assert response.json()["assessments"][0]["suitability_score"] == 80


class FakeConnection:
    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple]] = []
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query: str, params: tuple):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_repository_saves_with_parameterized_values_and_commits(monkeypatch) -> None:
    timestamp = datetime(2026, 10, 25, 13, tzinfo=timezone.utc)
    connection = FakeConnection([(11, "Original", "Original", timestamp)])
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    saved = repository.save_research_question("Original")

    assert saved["id"] == 11
    assert connection.calls[0][1] == ("Original", "Original")
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_repository_reads_history_and_single_query(monkeypatch) -> None:
    timestamp = datetime(2026, 10, 25, 13, tzinfo=timezone.utc)
    connection = FakeConnection([(11, "Original", "normalized", timestamp)])
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    history = repository.list_recent_research_questions(5)
    query = repository.get_research_question(11)

    assert history[0]["normalized_question"] == "normalized"
    assert query is not None and query["id"] == 11
    assert connection.calls[0][1] == (5,)
    assert connection.calls[1][1] == (11,)
