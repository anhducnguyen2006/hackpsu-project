from fastapi.testclient import TestClient

from app.api import schemas
from app.api.routes import discovery as discovery_route
from app.main import app
from tests.auth_tokens import bearer


class FakeDiscoveryService:
    def search_with_status(self, question: str, limit: int):
        interpretation = schemas.ResearchInterpretation(
            original_research_question=question,
            research_subject="student performance",
            independent_variables=["study time"],
            dependent_variables=["academic performance"],
            target_population="students",
            synonyms=["grades"],
            search_terms=["student", "studytime", "performance"],
        )
        dataset = schemas.DatasetResult(
            dataset_id="uci:320",
            title="Student Performance",
            description="Student study time and performance",
            repository_url="https://archive.ics.uci.edu/dataset/320",
            variables=["studytime", "G3"],
            data_status="available",
            semantic_similarity_score=0.91,
            score_type="semantic_similarity",
            relevance_explanation="Verified metadata matched the research concepts.",
            score_confidence="high",
            matched_research_variables=["studytime", "G3"],
            missing_or_unverified_variables=[],
            classification="relevant",
        )
        return interpretation, [dataset][:limit], [], "gemini", "semantic_embeddings"


def test_discovery_route_serializes_interpretation_and_results(monkeypatch) -> None:
    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    monkeypatch.setattr(discovery_route, "service", FakeDiscoveryService())

    response = TestClient(app).post(
        "/api/v1/discovery/search",
        headers=bearer(),
        json={"research_question": "How does study time relate to grades?", "limit": 12},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["processing_mode"] == "gemini"
    assert payload["ranking_status"] == "semantic_embeddings"
    assert payload["interpretation"]["independent_variables"] == ["study time"]
    assert payload["datasets"][0]["dataset_id"] == "uci:320"


def test_discovery_route_validates_question_and_limit() -> None:
    client = TestClient(app)

    short_question = client.post(
        "/api/v1/discovery/search",
        headers=bearer(),
        json={"research_question": "short", "limit": 12},
    )
    invalid_limit = client.post(
        "/api/v1/discovery/search",
        headers=bearer(),
        json={"research_question": "How does study time relate to grades?", "limit": 26},
    )

    assert short_question.status_code == 422
    assert invalid_limit.status_code == 422


def test_discovery_route_labels_demo_response(monkeypatch) -> None:
    monkeypatch.setattr(discovery_route.settings, "demo_mode", True)

    response = TestClient(app).post(
        "/api/v1/discovery/search",
        headers=bearer(),
        json={"research_question": "How does study time relate to grades?", "limit": 12},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_status"] == "demo_cached"
    assert any("DEMO_MODE" in warning for warning in payload["warnings"])
