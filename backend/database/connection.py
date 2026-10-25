from pathlib import Path

from psycopg_pool import ConnectionPool
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = DatabaseSettings()

if not settings.database_url:
    raise RuntimeError(
        "DATABASE_URL is missing. Set it in backend/.env or the process environment."
    )

pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=5,
    open=False,
)

def open_db():
    pool.open()

def close_db():
    pool.close()


# Descriptive aliases used by the database smoke test and application code.
def open_database():
    open_db()


def close_database():
    close_db()


def get_connection():
    return pool.connection()
