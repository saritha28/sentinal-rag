"""Collections + collection access policies.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-26

Implements Enterprise_RAG_Database_Design.md sections 4.1-4.2.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE collections (
            id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id    UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name         TEXT         NOT NULL,
            description  TEXT,
            visibility   TEXT         NOT NULL DEFAULT 'private'
                CHECK (visibility IN ('private', 'tenant', 'public')),
            metadata     JSONB        NOT NULL DEFAULT '{}'::jsonb,
            created_by   UUID         REFERENCES users(id),
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),

            UNIQUE (tenant_id, name)
        )
    """)
    op.execute("CREATE INDEX idx_collections_tenant_id ON collections(tenant_id)")
    op.execute("""
        CREATE TRIGGER trg_collections_updated_at
        BEFORE UPDATE ON collections
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # Access policies: either role_id or user_id (not both null) grants access_level.
    op.execute("""
        CREATE TABLE collection_access_policies (
            id             UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id      UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            collection_id  UUID         NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
            role_id        UUID         REFERENCES roles(id) ON DELETE CASCADE,
            user_id        UUID         REFERENCES users(id) ON DELETE CASCADE,
            access_level   TEXT         NOT NULL
                CHECK (access_level IN ('read', 'write', 'admin')),
            created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CHECK (role_id IS NOT NULL OR user_id IS NOT NULL),
            CHECK (NOT (role_id IS NOT NULL AND user_id IS NOT NULL))
        )
    """)
    op.execute(
        "CREATE INDEX idx_collection_access_collection_id "
        "ON collection_access_policies(collection_id)"
    )
    op.execute(
        "CREATE INDEX idx_collection_access_role_id "
        "ON collection_access_policies(role_id) WHERE role_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_collection_access_user_id "
        "ON collection_access_policies(user_id) WHERE user_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS collection_access_policies CASCADE")
    op.execute("DROP TABLE IF EXISTS collections CASCADE")
