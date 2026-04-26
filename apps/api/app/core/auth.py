"""FastAPI bindings for auth: ``require_auth`` + ``require_permission``.

The verifier is constructed once at app startup (lifespan) and stored on
``app.state.jwt_verifier``. The ``require_auth`` dependency:

    1. Extracts the bearer token.
    2. Verifies signature and claims via JWTVerifier.
    3. Loads the user's permission set from the DB.
    4. Builds an AuthContext.
    5. Sets the ``current_tenant_id`` and ``current_user_id`` contextvars
       so downstream sessions auto-bind RLS context.

The same dependency is the ONLY place the runtime tenant context is set.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import RoleRepository, UserRepository
from app.db.session import current_tenant_id, current_user_id, get_admin_db
from sentinelrag_shared.auth import AuthContext, JWTVerifier, JWTVerifierError
from sentinelrag_shared.errors import AuthRequiredError
from sentinelrag_shared.errors.exceptions import AuthInvalidError


def _get_verifier(request: Request) -> JWTVerifier:
    verifier = getattr(request.app.state, "jwt_verifier", None)
    if verifier is None:
        msg = "JWT verifier not configured."
        raise RuntimeError(msg)
    return verifier


async def require_auth(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    db: Annotated[AsyncSession, Depends(get_admin_db)] = ...,  # type: ignore[assignment]
) -> AuthContext:
    """Verify the bearer token and yield an AuthContext.

    The DB dependency uses the admin (RLS-bypass) session because the very
    first lookup — finding the user record — needs to happen before tenant
    context is set. After that we set the contextvars so subsequent
    ``Depends(get_db)`` calls within the same request bind RLS correctly.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthRequiredError()

    token = authorization.split(" ", 1)[1].strip()
    verifier = _get_verifier(request)

    try:
        claims = await verifier.verify(token)
    except JWTVerifierError as exc:
        raise AuthInvalidError(str(exc)) from exc

    # Load the user. Keycloak's ``sub`` is stored on our user as
    # ``external_identity_id``. The user record is the application's
    # authoritative identity (per ADR-0008).
    user_repo = UserRepository(db)
    user = await user_repo.get_by_external_id(str(claims.sub))
    if user is None:
        # First-login provisioning — create the user lazily. Tenant must
        # already exist (matched by claims.tenant_id).
        from app.db.models import User
        from app.db.repositories import TenantRepository

        tenant = await TenantRepository(db).get_by_id(claims.tenant_id)
        if tenant is None:
            raise AuthInvalidError("Tenant in token does not exist.")
        user = User(
            tenant_id=claims.tenant_id,
            email=claims.email.lower(),
            external_identity_id=str(claims.sub),
            full_name=claims.raw.get("name") or claims.raw.get("preferred_username"),
        )
        db.add(user)
        await db.flush()

    # Resolve permissions from our DB (Keycloak roles are ignored).
    role_repo = RoleRepository(db)
    permissions = await role_repo.list_user_permission_codes(user.id)

    ctx = AuthContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        permissions=frozenset(permissions),
    )

    # Bind contextvars so the request's get_db() session sets RLS correctly.
    current_tenant_id.set(ctx.tenant_id)
    current_user_id.set(ctx.user_id)

    return ctx


def require_permission(code: str):
    """Dependency factory: ``require_permission('users:write')``."""

    async def _dependency(
        ctx: Annotated[AuthContext, Depends(require_auth)],
    ) -> AuthContext:
        ctx.require_permission(code)
        return ctx

    return _dependency
