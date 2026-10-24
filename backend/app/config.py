from pathlib import Path
import os
import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str | None = None
    google_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    backend_cors_origins: str = "http://localhost:5173"
    uci_catalog_ttl_seconds: int = 900

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
    )

    @property
    def gemini_configuration_status(self) -> str:
        if self.gemini_api_key and self.google_api_key:
            return "conflicting GEMINI_API_KEY and GOOGLE_API_KEY; using GEMINI_API_KEY explicitly"
        if self.gemini_api_key:
            return "configured"
        if self.google_api_key or os.getenv("GOOGLE_API_KEY"):
            return "missing GEMINI_API_KEY; GOOGLE_API_KEY is ignored"
        return "missing GEMINI_API_KEY; set it in backend/.env or the process environment"

    @property
    def cors_origins(self) -> list[str]:
        try:
            parsed = json.loads(self.backend_cors_origins)
        except json.JSONDecodeError:
            parsed = [origin.strip() for origin in self.backend_cors_origins.split(",")]
        if isinstance(parsed, str):
            return [parsed]
        return [str(origin) for origin in parsed]


settings = Settings()
