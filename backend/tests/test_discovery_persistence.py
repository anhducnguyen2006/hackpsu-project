from fastapi.testclient import TestClient

from app.api import schemas
from app.api.routes import discovery as discovery_route
from app.main import app


def _interpretation() -> schemas.ResearchInterpretation:
    return schemas.ResearchInterpretation(
        original_research_question="How does study time relate to grades?",
        refined_question="study time and academic performance",
        research_subject="student performance",
        independent_variables=["study time"],
        dependent_variables=["academic performance"],
        target_population="students",
        synonyms=["grades"],
        search_terms=["student", "studytime", "performance"],
    )


def _dataset() -> schemas.DatasetResult:
    return schemas.DatasetResult(
        dataset_id="uci:320",
        title="Student Performance",
        description="Verified student performance metadata.",
        repository_url="https://archive.ics.uci.edu/dataset/320",
        source="UCI Machine Learning Repository",
        source_id="320",
        landing_page_url="https://archive.ics.uci.edu/dataset/320",
        data_status="available",
        semantic_similarity_score=0.91,
        relevance_explanation="Verified metadata matched.",
    )


class FakeDiscoveryService:
    def __init__(self, datasets: list[schemas.DatasetResult]) -> None:
        self.datasets = datasets

    def search_with_status(self, question: str, limit: int):
        return _interpretation(), self.datasets[:limit], [], "gemini", "semantic_embeddings"


def test_successful_discovery_persists_original_normalized_question_and_results(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    monkeypatch.setattr(discovery_route, "service", FakeDiscoveryService([_dataset()]))
    monkeypatch.setattr(
        discovery_route,
        "persist_discovery_result",
        lambda **kwargs: captured.append(kwargs) or 17,
    )

    response = TestClient(app).post(
        "/api/v1/discovery/search",
        json={"research_question": "How does study time relate to grades?", "limit": 8},
    )

    assert response.status_code == 200
    assert captured[0]["question"] == "How does study time relate to grades?"
    assert captured[0]["normalized_question"] == "study time and academic performance"
    assert captured[0]["datasets"][0].source_id == "320"


def test_zero_result_discovery_persists_query_without_datasets(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    monkeypatch.setattr(discovery_route, "service", FakeDiscoveryService([]))
    monkeypatch.setattr(
        discovery_route,
        "persist_discovery_result",
        lambda **kwargs: captured.append(kwargs) or 18,
    )

    response = TestClient(app).post(
        "/api/v1/discovery/search",
        json={"research_question": "How does study time relate to grades?", "limit": 8},
    )

    assert response.status_code == 200
    assert captured[0]["datasets"] == []


def test_repeated_discovery_attempts_persistence_each_time(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    monkeypatch.setattr(discovery_route, "service", FakeDiscoveryService([_dataset()]))
    monkeypatch.setattr(discovery_route, "persist_discovery_result", lambda **kwargs: calls.append(kwargs) or 19)

    client = TestClient(app)
    first = client.post(
        "/api/v1/discovery/search",
        json={"research_question": "How does study time relate to grades?", "limit": 8},
    )
    second = client.post(
        "/api/v1/discovery/search",
        json={"research_question": "How does study time relate to grades?", "limit": 8},
    )

    assert first.status_code == second.status_code == 200
    assert len(calls) == 2


def test_database_failure_does_not_fail_discovery_response(monkeypatch) -> None:
    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    monkeypatch.setattr(discovery_route, "service", FakeDiscoveryService([_dataset()]))

    def fail_persistence(**kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(discovery_route, "persist_discovery_result", fail_persistence)

    response = TestClient(app).post(
        "/api/v1/discovery/search",
        json={"research_question": "How does study time relate to grades?", "limit": 8},
    )

    assert response.status_code == 200
    assert response.json()["datasets"][0]["dataset_id"] == "uci:320"
    assert any("persistence unavailable" in warning for warning in response.json()["warnings"])


def test_demo_discovery_does_not_persist_cached_datasets(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(discovery_route.settings, "demo_mode", True)
    monkeypatch.setattr(
        discovery_route,
        "persist_discovery_result",
        lambda **kwargs: calls.append(kwargs) or 20,
    )

    response = TestClient(app).post(
        "/api/v1/discovery/search",
        json={"research_question": "How does study time relate to grades?", "limit": 8},
    )

    assert response.status_code == 200
    assert response.json()["ranking_status"] == "demo_cached"
    assert calls == []
