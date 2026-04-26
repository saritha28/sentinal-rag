"""Application lifespan: startup + shutdown hooks.

Bootstraps logging, telemetry, the JWT verifier, and disposes the DB engine
on shutdown. The DB engine is created lazily on first use (see
``app/db/session.py``) so we don't open connections during static analysis.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.db.session import dispose_engines
from sentinelrag_shared.auth import JWTVerifier
from sentinelrag_shared.logging import configure_logging, get_logger
from sentinelrag_shared.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    configure_logging(
        level=settings.log_level,
        json_output=settings.environment != "local",
        service_name=settings.service_name,
    )
    configure_telemetry(
        service_name=settings.service_name,
        service_version=settings.service_version,
        environment=settings.environment,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
    )

    # JWT verifier — single instance per process, JWKS cached.
    app.state.jwt_verifier = JWTVerifier(
        issuer=settings.keycloak_issuer_url,
        audience=settings.keycloak_audience,
        jwks_url=settings.keycloak_jwks_url,
        algorithms=(settings.jwt_algorithm,),
    )

    log = get_logger(__name__)
    log.info(
        "service.startup",
        environment=settings.environment,
        version=settings.service_version,
    )

    try:
        yield
    finally:
        log.info("service.shutdown")
        await app.state.jwt_verifier.close()
        await dispose_engines()
