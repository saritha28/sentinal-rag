"""User service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories import UserRepository
from app.schemas.users import UserCreate, UserUpdate
from sentinelrag_shared.errors.exceptions import ConflictError, UserNotFoundError


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def create(self, *, tenant_id: UUID, payload: UserCreate) -> User:
        existing = await self.repo.get_by_email(payload.email.lower())
        if existing is not None:
            raise ConflictError(f"User with email {payload.email} already exists.")
        user = User(
            tenant_id=tenant_id,
            email=payload.email.lower(),
            full_name=payload.full_name,
            external_identity_id=payload.external_identity_id,
        )
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            raise ConflictError("User could not be created.") from exc
        return user

    async def get(self, user_id: UUID) -> User:
        user = await self.repo.get(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[User]:
        return await self.repo.list(limit=limit, offset=offset)

    async def update(self, user_id: UUID, payload: UserUpdate) -> User:
        user = await self.get(user_id)
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.status is not None:
            user.status = payload.status
        await self.db.flush()
        return user

    async def assign_role(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        granted_by: UUID,
    ) -> None:
        # Verify the user and role exist (RLS will hide other tenants' rows
        # automatically; cross-tenant assignment fails as a 404).
        await self.get(user_id)
        from app.db.repositories import RoleRepository

        role = await RoleRepository(self.db).get(role_id)
        if role is None:
            from sentinelrag_shared.errors.exceptions import RoleNotFoundError

            raise RoleNotFoundError()
        try:
            await self.repo.assign_role(
                user_id=user_id, role_id=role_id, granted_by=granted_by
            )
        except IntegrityError:
            # Already assigned — idempotent.
            pass
