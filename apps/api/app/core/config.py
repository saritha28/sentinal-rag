"""Application settings.

Settings are loaded from environment variables (see ``.env.example``) via
pydantic-settings. The Settings instance is a process-wide singleton accessed
through :func:`get_settings`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod"]


class Settings(BaseSettings):
    """API service runtime settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Service identity ---
    service_name: str = "sentinelrag-api"
    service_version: str = "0.1.0"
    environment: Environment = "local"
    log_level: str = "INFO"
    api_base_path: str = "/api/v1"

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinelrag",
        description="Async DSN; must use asyncpg driver.",
    )

    # --- Cache ---
    redis_url: str = "redis://localhost:6380/0"

    # --- Auth (Keycloak) ---
    keycloak_issuer_url: str = "http://localhost:8080/realms/sentinelrag"
    keycloak_audience: str = "sentinelrag-api"
    keycloak_jwks_url: str = (
        "http://localhost:8080/realms/sentinelrag/protocol/openid-connect/certs"
    )
    jwt_algorithm: str = "RS256"

    # --- Observability ---
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"

    # --- Temporal ---
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"

    # --- Feature flags ---
    unleash_url: str = "http://localhost:4242/api/"
    unleash_api_token: str = ""
    unleash_app_name: str = "sentinelrag-api"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton."""
    return Settings()
