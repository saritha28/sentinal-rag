"""Tenants, users, roles, permissions (multi-tenant RBAC core).

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-26

Implements Enterprise_RAG_Database_Design.md sections 3.1-3.6.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- tenants ----
    op.execute("""
        CREATE TABLE tenants (
            id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            name        TEXT         NOT NULL,
            slug        TEXT         NOT NULL UNIQUE,
            plan        TEXT         NOT NULL DEFAULT 'developer',
            status      TEXT         NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'suspended', 'deleted')),
            metadata    JSONB        NOT NULL DEFAULT '{}'::jsonb,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TRIGGER trg_tenants_updated_at
        BEFORE UPDATE ON tenants
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # ---- users ----
    op.execute("""
        CREATE TABLE users (
            id                    UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id             UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email                 TEXT         NOT NULL,
            full_name             TEXT,
            external_identity_id  TEXT,
            status                TEXT         NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'invited', 'disabled')),
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),

            UNIQUE (tenant_id, email)
        )
    """)
    op.execute("CREATE INDEX idx_users_tenant_id ON users(tenant_id)")
    op.execute(
        "CREATE INDEX idx_users_external_identity ON users(external_identity_id) "
        "WHERE external_identity_id IS NOT NULL"
    )
    op.execute("""
        CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # ---- roles ----
    op.execute("""
        CREATE TABLE roles (
            id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id       UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name            TEXT         NOT NULL,
            description     TEXT,
            is_system_role  BOOLEAN      NOT NULL DEFAULT false,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            UNIQUE (tenant_id, name)
        )
    """)
    op.execute("CREATE INDEX idx_roles_tenant_id ON roles(tenant_id)")

    # ---- permissions (global, not tenant-scoped) ----
    # Permissions are platform-wide constants; tenants reference them by code.
    op.execute("""
        CREATE TABLE permissions (
            id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            code         TEXT         NOT NULL UNIQUE,
            description  TEXT,
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)

    # Seed the permission codes referenced in the design doc + a few obvious extras.
    op.execute("""
        INSERT INTO permissions (code, description) VALUES
            ('tenants:admin',         'Manage tenant settings'),
            ('users:read',            'List and view users'),
            ('users:write',           'Create, update, deactivate users'),
            ('roles:admin',           'Create roles and assign permissions'),
            ('collections:read',      'List collections and metadata'),
            ('collections:write',     'Create and update collections'),
            ('collections:admin',     'Manage collection access policies'),
            ('documents:read',        'Read documents and chunks'),
            ('documents:write',       'Upload and modify documents'),
            ('queries:execute',       'Run RAG queries'),
            ('prompts:read',          'View prompt templates and versions'),
            ('prompts:admin',         'Create, update, retire prompts'),
            ('evals:run',             'Run evaluation jobs'),
            ('evals:admin',           'Manage evaluation datasets'),
            ('audit:read',            'View audit log'),
            ('billing:read',          'View usage and cost reports'),
            ('llm:cloud_models',      'Use cloud LLM providers (otherwise self-hosted only)')
    """)

    # ---- role_permissions ----
    op.execute("""
        CREATE TABLE role_permissions (
            role_id        UUID  NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id  UUID  NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_id)
        )
    """)

    # ---- user_roles ----
    op.execute("""
        CREATE TABLE user_roles (
            user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id     UUID         NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            granted_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            granted_by  UUID         REFERENCES users(id),
            PRIMARY KEY (user_id, role_id)
        )
    """)
    op.execute("CREATE INDEX idx_user_roles_user_id ON user_roles(user_id)")
    op.execute("CREATE INDEX idx_user_roles_role_id ON user_roles(role_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_roles CASCADE")
    op.execute("DROP TABLE IF EXISTS role_permissions CASCADE")
    op.execute("DROP TABLE IF EXISTS permissions CASCADE")
    op.execute("DROP TABLE IF EXISTS roles CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE")
