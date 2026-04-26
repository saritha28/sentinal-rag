"""Tenant repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.db.models import Tenant
from app.db.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    model = Tenant

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        return await self.get(tenant_id)
