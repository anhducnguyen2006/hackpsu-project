from fastapi.testclient import TestClient

from app.main import app
from tests.auth_tokens import bearer


def test_health() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_requires_authentication() -> None:
    response = TestClient(app).get("/api/v1/health/database")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication is required."


def test_database_health_reports_unavailable_without_claiming_a_connection() -> None:
    response = TestClient(app).get("/api/v1/health/database", headers=bearer())
    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"
    assert "postgresql://" not in response.text


def test_cors_preflight_allows_frontend_origin() -> None:
    response = TestClient(app).options(
        "/api/v1/discovery/search",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

