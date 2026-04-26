"""Pydantic schemas for role API I/O."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.schemas.common import APIModel, TimestampedRead


class RoleCreate(APIModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=200)
    permission_codes: list[str] = Field(default_factory=list)


class RoleUpdate(APIModel):
    description: str | None = Field(default=None, max_length=200)
    permission_codes: list[str] | None = None


class RoleRead(TimestampedRead):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    is_system_role: bool
    permission_codes: list[str] = Field(default_factory=list)


class PermissionRead(APIModel):
    code: str
    description: str | None
