"""Common Pydantic schema primitives used across API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIModel(BaseModel):
    """Base for all API request/response schemas.

    Configured to:
        - Accept ORM objects via ``model_validate`` (``from_attributes``).
        - Serialize datetimes in ISO-8601 with timezone.
    """

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class Page(APIModel, Generic[T]):
    """Cursorless paginated list."""

    items: list[T]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=200)
    offset: int = Field(..., ge=0)


class IDResponse(APIModel):
    """Used for endpoints that return only the new resource's ID."""

    id: UUID


class TimestampedRead(APIModel):
    """Mixin for records that expose created_at."""

    created_at: datetime


class FullTimestampedRead(TimestampedRead):
    updated_at: datetime
