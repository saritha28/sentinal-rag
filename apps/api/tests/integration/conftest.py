"""Shared fixtures for integration tests.

Uses testcontainers to spin up a real ``pgvector/pgvector:pg16`` Postgres,
runs all Alembic migrations end-to-end, and yields an async session bound to
the real DB. Each test gets a clean schema via a per-test transactional roll-
back wouldn't work here (RLS sets are per-transaction); we instead truncate
seeded rows in the function-scope teardown.

NB: requires Docker available on the test runner.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID, uuid4

import alembic.config
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Spin up a single Postgres for the whole test session."""
    with PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="sentinel",
        password="sentinel",
        dbname="sentinelrag",
    ) as container:
        yield container


@pytest.fixture(scope="session")
def database_urls(postgres_container: PostgresContainer) -> dict[str, str]:
    """Async + sync DSNs for the running container."""
    sync_url = postgres_container.get_connection_url()  # postgresql+psycopg2://...
    # Normalize to plain postgresql:// for psycopg3 (Alembic env.py),
    # and asyncpg variant for the application.
    sync_url = sync_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    async_url = sync_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    return {"sync": sync_url, "async": async_url}


@pytest.fixture(scope="session")
def applied_migrations(database_urls: dict[str, str]) -> dict[str, str]:
    """Apply all Alembic migrations against the test container once per session."""
    os.environ["DATABASE_URL_SYNC"] = database_urls["sync"]
    os.environ["DATABASE_URL"] = database_urls["async"]

    cfg = alembic.config.Config(str(REPO_ROOT / "migrations" / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    alembic.config.command.upgrade(cfg, "head")
    return database_urls


@pytest_asyncio.fixture
async def engine(applied_migrations: dict[str, str]):
    """Async engine for tests; one per test for isolation of pool state."""
    eng = create_async_engine(applied_migrations["async"], pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def admin_session(session_factory) -> AsyncIterator[AsyncSession]:
    """Session that does NOT bind tenant context. Bypasses RLS as table owner."""
    async with session_factory() as session:
        async with session.begin():
            yield session


async def _set_tenant(session: AsyncSession, tenant_id: UUID | None) -> None:
    """Issue ``SET LOCAL app.current_tenant_id`` for this transaction."""
    val = str(tenant_id) if tenant_id else ""
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :v, true)"),
        {"v": val},
    )


@pytest_asyncio.fixture
async def tenant_session_factory(session_factory):
    """Returns a callable that yields an RLS-bound session for a given tenant."""

    def _factory(tenant_id: UUID | None):
        async def _ctx() -> AsyncIterator[AsyncSession]:
            async with session_factory() as session:
                async with session.begin():
                    await _set_tenant(session, tenant_id)
                    yield session

        return _ctx

    return _factory


@pytest_asyncio.fixture
async def cleanup_db(session_factory) -> AsyncIterator[None]:
    """After each test, truncate all tenant-owned tables (preserves migrations + permissions)."""
    yield
    async with session_factory() as session:
        async with session.begin():
            # Order matters — truncate-with-cascade handles FKs.
            await session.execute(
                text(
                    "TRUNCATE TABLE "
                    "user_roles, role_permissions, users, roles, "
                    "tenants RESTART IDENTITY CASCADE"
                )
            )


@pytest.fixture
def tenant_factory():
    """Helper to mint tenant UUIDs in tests."""

    def _make() -> UUID:
        return uuid4()

    return _make
