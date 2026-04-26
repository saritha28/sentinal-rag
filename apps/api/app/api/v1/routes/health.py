"""Health and readiness endpoints.

``/health``      — liveness probe; cheap; always returns 200 unless the process
                   itself is broken.
``/health/ready`` — readiness probe; checks downstream dependencies (DB, Redis,
                   Temporal). Returns 503 with details when any are unhealthy.
                   Implementation deferred until Phase 1 wires real DB sessions.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


@router.get("/health", status_code=status.HTTP_200_OK, response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.service_version,
        environment=settings.environment,
    )
