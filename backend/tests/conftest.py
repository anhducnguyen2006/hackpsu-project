"""Keep ordinary tests off live TigerData and the Gemini API."""

import pytest

import app.main as main_module
import database.connection as database_connection
from app.assessment.gemini import GeminiService


@pytest.fixture(autouse=True)
def isolate_external_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent TestClient startup from opening a configured production database.

    Repository tests that need SQL inject their own connection double. The
    Gemini client constructor is blocked so a developer `.env` key cannot
    turn a unit test into a paid API call.
    """
    monkeypatch.setattr(database_connection, "_pool", None)
    monkeypatch.setattr(main_module, "open_database", lambda: None)
    monkeypatch.setattr(main_module, "close_database", lambda: None)

    def refuse_live_gemini(self: GeminiService) -> None:
        raise AssertionError("Tests must not create a live Gemini client.")

    monkeypatch.setattr(GeminiService, "_create_client", refuse_live_gemini)

    from app import auth, limits
    from app.config import settings
    from tests.auth_tokens import AUDIENCE, ISSUER, TestKeyStore

    monkeypatch.setattr(auth, "_signing_keys", TestKeyStore())
    monkeypatch.setattr(auth, "_jwks", None)
    monkeypatch.setattr(settings, "auth0_domain", "test.example.auth0.com")
    monkeypatch.setattr(settings, "auth0_audience", AUDIENCE)
    monkeypatch.setattr(settings, "auth0_issuer", ISSUER)
    monkeypatch.setattr(settings, "auth0_required_scope", "")
    monkeypatch.setattr(settings, "dev_routes_enabled", False)
    limits.discovery_gate.max_calls = settings.auth_discovery_limit
    limits.analysis_gate.max_calls = settings.auth_analysis_limit
    limits.similarity_gate.max_calls = settings.auth_similarity_limit
    limits.discovery_gate.reset()
    limits.analysis_gate.reset()
    limits.similarity_gate.reset()
