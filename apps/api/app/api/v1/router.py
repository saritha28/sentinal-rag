"""v1 API router aggregator."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import health, roles, tenants, users

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(tenants.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(roles.router)

# Phase 2+ will add: collections, documents, ingestion, query,
# prompts, evaluations, audit, usage.
