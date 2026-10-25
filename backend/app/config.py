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
    external_request_timeout_seconds: float = 12.0
    analysis_max_download_bytes: int = 50_000_000
    analysis_max_rows: int = 100_000
    analysis_max_columns: int = 500
    analysis_max_redirects: int = 3
    analysis_download_concurrency: int = 2
    gemini_request_timeout_ms: int = 15000
    demo_mode: bool = False

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
        origins = [parsed] if isinstance(parsed, str) else [str(origin) for origin in parsed]
        # The browser serializes an Origin without a trailing slash. Normalize
        # configuration values so `http://localhost:5173/` still matches it.
        origins = [origin.strip().rstrip("/") for origin in origins]
        local_aliases = {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        }
        if any(origin in local_aliases for origin in origins):
            origins.extend(local_aliases)
        return list(dict.fromkeys(origins))


settings = Settings()
