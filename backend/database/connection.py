from __future__ import annotations

import threading
from pathlib import Path

from psycopg_pool import ConnectionPool
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseUnavailableError(RuntimeError):
    """Raised when TigerData is not configured or its pool cannot be used."""


class DatabaseSettings(BaseSettings):
    database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = DatabaseSettings()

_lock = threading.Lock()
_pool: ConnectionPool | None = None


def database_configured() -> bool:
    return bool(settings.database_url.strip())


def open_db() -> None:
    """Open the configured pool. A missing URL does not connect anywhere."""
    global _pool
    if not database_configured():
        return
    with _lock:
        if _pool is not None:
            return
        pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=5,
            open=False,
            kwargs={"connect_timeout": 5},
        )
        try:
            pool.open(wait=True, timeout=5)
        except Exception as error:
            try:
                pool.close()
            except Exception:
                pass
            raise DatabaseUnavailableError(
                "TigerData could not be reached. Check DATABASE_URL."
            ) from error
        _pool = pool


def close_db() -> None:
    global _pool
    with _lock:
        pool = _pool
        _pool = None
    if pool is not None:
        pool.close()


# Descriptive aliases used by the database smoke test and application code.
def open_database() -> None:
    open_db()


def close_database() -> None:
    close_db()


def get_connection():
    if _pool is None:
        raise DatabaseUnavailableError(
            "Research storage is unavailable because TigerData is not connected."
        )
    return _pool.connection()
