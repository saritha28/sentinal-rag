"""User repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.db.models import User, UserRole
from app.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> User | None:
        stmt = select(User).where(User.external_identity_id == external_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def assign_role(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        granted_by: UUID | None = None,
    ) -> UserRole:
        link = UserRole(user_id=user_id, role_id=role_id, granted_by=granted_by)
        self.session.add(link)
        await self.session.flush()
        return link

    async def revoke_role(self, *, user_id: UUID, role_id: UUID) -> None:
        stmt = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        )
        result = await self.session.execute(stmt)
        link = result.scalar_one_or_none()
        if link is not None:
            await self.session.delete(link)
            await self.session.flush()

    async def list_role_ids(self, user_id: UUID) -> list[UUID]:
        stmt = select(UserRole.role_id).where(UserRole.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
