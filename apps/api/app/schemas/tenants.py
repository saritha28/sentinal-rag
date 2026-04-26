"""Pydantic schemas for tenant API I/O."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import APIModel, FullTimestampedRead

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


class TenantCreate(APIModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=2, max_length=64)
    plan: str = Field(default="developer", max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        v = v.lower()
        if not _SLUG_RE.match(v):
            msg = (
                "slug must be lowercase alphanumeric with hyphens, "
                "2-64 chars, and not start or end with a hyphen"
            )
            raise ValueError(msg)
        return v


class TenantUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    plan: str | None = Field(default=None, max_length=64)
    status: str | None = None
    metadata: dict[str, Any] | None = None


class TenantRead(FullTimestampedRead):
    id: UUID
    name: str
    slug: str
    plan: str
    status: str
    metadata: dict[str, Any] = Field(alias="metadata_")
