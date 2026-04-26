"""Pydantic schemas for user API I/O."""

from __future__ import annotations

from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import APIModel, FullTimestampedRead


class UserCreate(APIModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=200)
    external_identity_id: str | None = Field(default=None, max_length=200)


class UserUpdate(APIModel):
    full_name: str | None = Field(default=None, max_length=200)
    status: str | None = None


class UserRead(FullTimestampedRead):
    id: UUID
    tenant_id: UUID
    email: EmailStr
    full_name: str | None
    external_identity_id: str | None
    status: str


class UserRoleAssign(APIModel):
    role_id: UUID
