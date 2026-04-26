"""Permission repository.

The ``permissions`` table is platform-wide (NOT tenant-scoped). The repository
uses a non-RLS-bound session for reads where appropriate; for the typical
"list permissions" route, the regular get_db session works fine because
permissions has no RLS policy.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import Permission
from app.db.repositories.base import BaseRepository


class PermissionRepository(BaseRepository[Permission]):
    model = Permission

    async def list_all(self) -> list[Permission]:
        stmt = select(Permission).order_by(Permission.code)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Permission | None:
        stmt = select(Permission).where(Permission.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
