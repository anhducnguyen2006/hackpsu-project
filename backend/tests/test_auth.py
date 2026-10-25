"""Hermetic Auth0 access-token checks. JWKS is a local RSA key, never the network."""

from __future__ import annotations

import time

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.api.routes import datasets as datasets_route
from app.api.routes import discovery as discovery_route
from app.auth import authenticate_token
from app.config import settings
from app.limits import discovery_gate
from app.main import app
from tests.auth_tokens import (
    AUDIENCE,
    ISSUER,
    other_private_key,
    token,
    unsigned_token,
)


def _question() -> dict:
    return {"research_question": "How does study time relate to grades?", "limit": 8}


def test_public_health_does_not_require_a_token() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_discovery_without_token_does_not_search(monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("discovery ran without authentication")

    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    monkeypatch.setattr(discovery_route, "service", type("Blocked", (), {"search_with_status": staticmethod(explode)})())
    response = TestClient(app).post("/api/v1/discovery/search", json=_question())
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication is required."


def test_demo_mode_does_not_bypass_authentication(monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("demo search ran without authentication")

    monkeypatch.setattr(discovery_route.settings, "demo_mode", True)
    monkeypatch.setattr(discovery_route, "demo_search", explode)
    response = TestClient(app).post("/api/v1/discovery/search", json=_question())
    assert response.status_code == 401


def test_protected_analysis_without_token_does_not_analyze(monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("analysis ran without authentication")

    monkeypatch.setattr(datasets_route.analysis_service, "analyze", explode)
    response = TestClient(app).post(
        "/api/v1/datasets/uci:320/analyze",
        json={"research_question": "How does study time relate to grades?"},
    )
    assert response.status_code == 401


def test_protected_history_without_token_returns_401() -> None:
    response = TestClient(app).get("/api/v1/research/history")
    assert response.status_code == 401


def test_valid_access_token_carries_the_verified_subject() -> None:
    principal = authenticate_token(token("auth0|researcher-7"))
    assert principal.sub == "auth0|researcher-7"


@pytest.mark.parametrize(
    ("builder", "reason"),
    [
        (lambda: token(iss="https://evil.example/"), "issuer"),
        (lambda: token(aud="https://other.example/api"), "audience"),
        (lambda: token(aud="spa-client-id-used-as-an-id-token"), "audience"),
        (lambda: token(exp=int(time.time()) - 30, iat=int(time.time()) - 120), "expired"),
        (lambda: token(nbf=int(time.time()) + 3600), "immature"),
        (lambda: token(private=other_private_key), "signature"),
        (lambda: token(algorithm="HS256", private="not-the-auth0-signing-key-value!!"), "algorithm"),
        (unsigned_token, "algorithm"),
        (lambda: token(kid="rotated-away"), "key"),
        (lambda: token(sub=""), "subject"),
        (lambda: token(include_sub=False), "malformed"),
        (lambda: "not-a-jwt", "malformed"),
    ],
)
def test_invalid_tokens_are_rejected(builder, reason) -> None:
    with pytest.raises(auth.AuthenticationError) as caught:
        authenticate_token(builder())
    assert caught.value.reason == reason


def test_unknown_signing_key_refreshes_once_and_still_rejects() -> None:
    store = auth._signing_keys
    store.refresh_count = 0
    with pytest.raises(auth.AuthenticationError) as caught:
        authenticate_token(token(kid="not-published"))
    assert caught.value.reason == "key"
    assert store.refresh_count == 1


def test_key_rotation_accepts_a_key_published_on_refresh() -> None:
    store = auth._signing_keys
    store.fail_until_refresh = True
    store.refresh_count = 0
    principal = authenticate_token(token())
    assert principal.sub == "auth0|user-a"
    assert store.refresh_count == 1


def test_missing_auth0_configuration_fails_closed(monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("discovery ran without Auth0 configuration")

    monkeypatch.setattr(settings, "auth0_domain", "")
    monkeypatch.setattr(settings, "auth0_audience", "")
    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    monkeypatch.setattr(discovery_route, "service", type("Blocked", (), {"search_with_status": staticmethod(explode)})())
    missing = TestClient(app).post("/api/v1/discovery/search", json=_question())
    presented = TestClient(app).post(
        "/api/v1/discovery/search",
        headers={"Authorization": f"Bearer {token()}"},
        json=_question(),
    )
    assert missing.status_code == 503
    assert presented.status_code == 503
    assert missing.json()["detail"] == "Authentication is not configured."


def test_required_scope_returns_403_without_running_storage(monkeypatch) -> None:
    calls: list[str] = []

    def record(user_sub: str, limit: int) -> list:
        calls.append(user_sub)
        return []

    monkeypatch.setattr(settings, "auth0_required_scope", "read:research")
    monkeypatch.setattr("app.api.routes.research.list_recent_research_questions", record)
    denied = TestClient(app).get(
        "/api/v1/research/history",
        headers={"Authorization": f"Bearer {token()}"},
    )
    allowed = TestClient(app).get(
        "/api/v1/research/history",
        headers={"Authorization": f"Bearer {token(scope='read:research')}"},
    )
    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert calls == ["auth0|user-a"]


def test_valid_token_does_not_contact_auth0(monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("live Auth0 JWKS client constructed")

    monkeypatch.setattr(jwt, "PyJWKClient", explode)
    monkeypatch.setattr(
        "app.api.routes.research.list_recent_research_questions",
        lambda user_sub, limit: [],
    )
    response = TestClient(app).get(
        "/api/v1/research/history",
        headers={"Authorization": f"Bearer {token('auth0|user-a')}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_discovery_rate_limit_stops_before_another_search(monkeypatch) -> None:
    calls = {"count": 0}

    class CountingService:
        def search_with_status(self, question: str, limit: int):
            calls["count"] += 1
            from app.api import schemas

            interpretation = schemas.ResearchInterpretation(
                original_research_question=question,
                research_subject="student performance",
                independent_variables=["study time"],
                dependent_variables=["academic performance"],
                target_population="students",
                synonyms=["grades"],
                search_terms=["student", "studytime", "performance"],
            )
            return interpretation, [], [], "keyword_fallback", "keyword_fallback"

    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    monkeypatch.setattr(discovery_route, "service", CountingService())
    monkeypatch.setattr(
        discovery_route,
        "persist_discovery_result",
        lambda **_kwargs: 1,
    )
    monkeypatch.setattr(discovery_gate, "max_calls", 1)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token()}"}
    first = client.post("/api/v1/discovery/search", headers=headers, json=_question())
    second = client.post("/api/v1/discovery/search", headers=headers, json=_question())
    assert first.status_code == 200
    assert second.status_code == 429
    assert calls["count"] == 1


def test_dev_dataset_route_does_not_fetch_when_disabled_or_anonymous(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        datasets_route,
        "adapter",
        type("Adapter", (), {"fetch_and_profile": staticmethod(lambda dataset_id: calls.append(dataset_id) or {})})(),
    )
    anonymous = TestClient(app).get("/api/v1/dev/dataset-test")
    authenticated = TestClient(app).get(
        "/api/v1/dev/dataset-test",
        headers={"Authorization": f"Bearer {token()}"},
    )
    assert anonymous.status_code == 401
    assert authenticated.status_code == 404
    assert calls == []


def test_authenticated_history_reports_unavailable_tigerdata() -> None:
    response = TestClient(app).get(
        "/api/v1/research/history",
        headers={"Authorization": f"Bearer {token()}"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Research storage is unavailable."
    assert "postgresql://" not in response.text


def test_missing_owner_column_does_not_fall_back_to_global_history(monkeypatch) -> None:
    def missing_column(*_args, **_kwargs):
        raise psycopg.errors.UndefinedColumn("column research_queries.user_sub does not exist")

    monkeypatch.setattr(
        "app.api.routes.research.list_recent_research_questions",
        missing_column,
    )
    response = TestClient(app).get(
        "/api/v1/research/history",
        headers={"Authorization": f"Bearer {token()}"},
    )
    assert response.status_code == 503
    assert "004_research_query_owner.sql" in response.json()["detail"]


def test_user_cannot_read_another_users_question_or_session(monkeypatch) -> None:
    from datetime import datetime, timezone

    owned = {
        "id": 7,
        "question": "Private rainfall question",
        "normalized_question": "private rainfall question",
        "created_at": datetime(2026, 10, 25, tzinfo=timezone.utc),
        "datasets": [],
        "assessments": [],
    }

    def question(query_id: int, user_sub: str):
        if user_sub == "auth0|user-a" and query_id == 7:
            return owned
        return None

    def session(query_id: int, user_sub: str):
        return question(query_id, user_sub)

    monkeypatch.setattr("app.api.routes.research.get_research_question", question)
    monkeypatch.setattr("app.api.routes.research.get_research_session", session)
    client = TestClient(app)
    owner = {"Authorization": f"Bearer {token('auth0|user-a')}"}
    other = {"Authorization": f"Bearer {token('auth0|user-b')}"}
    assert client.get("/api/v1/research/7", headers=owner).status_code == 200
    assert client.get("/api/v1/research/7", headers=other).status_code == 404
    assert client.get("/api/v1/research/7/session", headers=other).status_code == 404
    assert client.get("/api/v1/research/7/session", headers=owner).json()["question"] == "Private rainfall question"


def test_similarity_search_uses_the_token_subject(monkeypatch) -> None:
    seen: list[str] = []

    class Embedder:
        model_identifier = "local-test-model@1"

        def embed_text(self, text: str):
            return [1.0, 0.0, 0.0]

    def find(embedding, embedding_model, user_sub, limit=5):
        seen.append(user_sub)
        return []

    monkeypatch.setattr("app.api.routes.research.embedding_service", Embedder())
    monkeypatch.setattr("app.api.routes.research.find_similar_research_questions", find)
    response = TestClient(app).post(
        "/api/v1/research/similar",
        headers={"Authorization": f"Bearer {token('auth0|user-a')}"},
        json={
            "research_question": "Does rainfall affect yield?",
            "user_sub": "auth0|user-b",
            "user_id": "auth0|user-b",
            "owner_id": "auth0|user-b",
        },
    )
    assert response.status_code == 200
    assert seen == ["auth0|user-a"]


def test_background_persistence_refuses_anonymous_history(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        discovery_route,
        "persist_discovery_result",
        lambda **kwargs: calls.append(kwargs) or 1,
    )
    discovery_route._persist_discovery_result_background(
        "Question",
        "normalized",
        [],
        None,
        "   ",
    )
    assert calls == []


def test_issuer_and_audience_constants_match_the_fixture() -> None:
    assert ISSUER.endswith("/")
    assert AUDIENCE.startswith("https://")
