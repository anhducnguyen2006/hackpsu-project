import pytest
from fastapi.testclient import TestClient

import database.connection as connection
from app.main import app
from database.connection import DatabaseUnavailableError, get_connection


class _Pool:
    def __init__(self, *, conninfo: str, min_size: int, max_size: int, open: bool, kwargs: dict) -> None:
        self.conninfo = conninfo
        self.min_size = min_size
        self.max_size = max_size
        self.open_flag = open
        self.kwargs = kwargs
        self.opened = False
        self.closed = False

    def open(self, *, wait: bool, timeout: float) -> None:
        self.opened = True
        self.wait = wait
        self.timeout = timeout

    def close(self) -> None:
        self.closed = True

    def connection(self) -> dict[str, bool]:
        return {"ok": True}


class _FailingPool(_Pool):
    def open(self, *, wait: bool, timeout: float) -> None:
        raise OSError("connection refused")


def test_missing_database_url_does_not_create_a_pool(monkeypatch) -> None:
    monkeypatch.setattr(connection.settings, "database_url", "   ")
    monkeypatch.setattr(
        connection,
        "ConnectionPool",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("pool created")),
    )

    connection.open_database()

    with pytest.raises(DatabaseUnavailableError, match="not connected"):
        get_connection()


def test_open_uses_only_the_configured_url(monkeypatch) -> None:
    url = "postgresql://unit-test-only@127.0.0.1:1/not-tigerdata"
    monkeypatch.setattr(connection.settings, "database_url", url)
    monkeypatch.setattr(connection, "ConnectionPool", _Pool)

    connection.open_database()
    try:
        assert connection._pool is not None
        assert connection._pool.conninfo == url
        assert connection._pool.opened is True
        assert get_connection() == {"ok": True}
    finally:
        connection.close_database()
    assert connection._pool is None


def test_failed_open_does_not_keep_a_pool_or_echo_the_url(monkeypatch) -> None:
    url = "postgresql://secret-user:secret-pass@127.0.0.1:1/private"
    monkeypatch.setattr(connection.settings, "database_url", url)
    monkeypatch.setattr(connection, "ConnectionPool", _FailingPool)

    with pytest.raises(DatabaseUnavailableError, match="could not be reached") as raised:
        connection.open_database()

    assert url not in str(raised.value)
    assert "secret-pass" not in str(raised.value)
    with pytest.raises(DatabaseUnavailableError):
        get_connection()


def test_lifespan_serves_health_when_database_open_fails(monkeypatch) -> None:
    def unavailable() -> None:
        raise DatabaseUnavailableError("down")

    monkeypatch.setattr("app.main.open_database", unavailable)
    monkeypatch.setattr("app.main.close_database", lambda: None)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
