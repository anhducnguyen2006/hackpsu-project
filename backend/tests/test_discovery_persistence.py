import time

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
        self.embedding_service = object()

    def search_with_status(self, question: str, limit: int):
        return _interpretation(), self.datasets[:limit], [], "gemini", "semantic_embeddings"


class RecordingBackgroundTasks:
    def __init__(self) -> None:
        self.tasks = []

    def add_task(self, function, *args, **kwargs) -> None:
        self.tasks.append((function, args, kwargs))

    def run_all(self) -> None:
        for function, args, kwargs in self.tasks:
            function(*args, **kwargs)


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
    assert response.json()["warnings"] == []


def test_discovery_response_does_not_wait_for_slow_background_write(monkeypatch) -> None:
    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    monkeypatch.setattr(discovery_route, "service", FakeDiscoveryService([_dataset()]))
    persisted: list[str] = []

    def slow_persistence(**kwargs):
        time.sleep(0.15)
        persisted.append(kwargs["question"])

    monkeypatch.setattr(discovery_route, "persist_discovery_result", slow_persistence)
    tasks = RecordingBackgroundTasks()
    started = time.perf_counter()

    response = discovery_route.search(
        schemas.DiscoveryRequest(
            research_question="How does study time relate to grades?", limit=8
        ),
        tasks,
    )

    response_elapsed = time.perf_counter() - started
    assert response.datasets[0].source_id == "320"
    assert response_elapsed < 0.10
    assert persisted == []
    tasks.run_all()
    assert persisted == ["How does study time relate to grades?"]


def test_background_persistence_failure_is_logged_and_does_not_raise(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        discovery_route,
        "persist_discovery_result",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("secret database url")),
    )

    discovery_route._persist_discovery_result_background(
        "Question",
        "normalized question",
        [_dataset().model_dump(mode="json")],
        None,
    )

    assert "background persistence failed" in caplog.text
    assert "secret database url" not in caplog.text


def test_graph_updates_run_after_persistence_commit(monkeypatch) -> None:
    events: list[tuple[str, int]] = []
    monkeypatch.setattr(
        discovery_route,
        "persist_discovery_result",
        lambda **kwargs: events.append(("persist", 41)) or 41,
    )
    monkeypatch.setattr(
        discovery_route,
        "generate_semantic_connections",
        lambda research_id: events.append(("semantic", research_id)) or object(),
    )
    monkeypatch.setattr(
        discovery_route,
        "generate_shared_dataset_connections",
        lambda research_id: events.append(("shared", research_id)) or object(),
    )

    discovery_route._persist_discovery_result_background(
        "Question", "normalized question", [], None
    )

    assert events == [("persist", 41), ("semantic", 41), ("shared", 41)]


def test_graph_update_failure_is_logged_without_exposing_error(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        discovery_route,
        "generate_semantic_connections",
        lambda research_id: (_ for _ in ()).throw(
            RuntimeError("secret database url")
        ),
    )
    monkeypatch.setattr(
        discovery_route,
        "generate_shared_dataset_connections",
        lambda research_id: object(),
    )

    discovery_route._update_research_connections_background(41)

    assert "research_connections background task failed" in caplog.text
    assert "secret database url" not in caplog.text


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
