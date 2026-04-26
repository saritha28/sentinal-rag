"""Base repository class — thin generic CRUD over an AsyncSession.

Repositories that need richer queries override or extend the base methods.
The base assumes:
    - The model has a single-column UUID primary key named ``id``.
    - Tenant scoping is handled by RLS, not by repository-level filters.
"""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic UUID-keyed async repository."""

    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: UUID) -> T | None:
        return await self.session.get(self.model, entity_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[T]:
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()
