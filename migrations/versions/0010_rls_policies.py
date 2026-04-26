"""Row-Level Security policies for tenant isolation.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-26

Implements Enterprise_RAG_Database_Design.md section 12 across every
tenant-owned table.

Strategy:
    - Every tenant-owned table has a single policy USING/WITH CHECK on
      ``tenant_id = current_setting('app.current_tenant_id')::uuid``.
    - The application opens each request by:
          SET LOCAL app.current_tenant_id = '<tenant_uuid>';
      via the AsyncSessionFactory's checkout hook.
    - Bypass: the application's connection role does NOT have BYPASSRLS.
      Migrations connect as a superuser/owner role that owns the tables and
      bypasses RLS implicitly (table owner exemption). The runtime role
      (``sentinelrag_app``) does NOT own these tables and is subject to RLS.

The runtime role is created in this migration (idempotent for re-runs in dev
where the role already exists from prior runs). In cloud deployments the
runtime role is provisioned by Terraform and granted only the privileges
listed below.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that are tenant-owned and therefore RLS-protected.
# Order doesn't matter for policy creation, but we keep it consistent with
# migration order for readability.
_TENANT_TABLES: tuple[str, ...] = (
    "tenants",
    "users",
    "roles",
    # role_permissions and user_roles are NOT directly tenant-owned (they join
    # to tables that are); RLS is enforced via the parent join. Adding RLS
    # would require referencing the parent's tenant_id which complicates the
    # policy with subqueries that hurt performance. We protect them through
    # FK ON DELETE CASCADE + app-level checks.
    "collections",
    "collection_access_policies",
    "documents",
    "document_versions",
    "document_chunks",
    "chunk_embeddings",
    "ingestion_jobs",
    "prompt_templates",
    "prompt_versions",
    "query_sessions",
    "retrieval_results",
    "generated_answers",
    "answer_citations",
    "evaluation_datasets",
    "evaluation_cases",
    "evaluation_runs",
    "evaluation_scores",
    "audit_events",
    "usage_records",
)


def upgrade() -> None:
    # Create the runtime role if missing. In dev this lives in the same DB;
    # in cloud Terraform provisions it.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sentinelrag_app') THEN
                CREATE ROLE sentinelrag_app NOLOGIN;
            END IF;
        END$$
    """)

    for table in _TENANT_TABLES:
        # Special case: the `tenants` table itself uses `id` not `tenant_id`.
        column = "id" if table == "tenants" else "tenant_id"

        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE: the table owner is normally exempt from RLS. We don't want the
        # app role to ever be exempt by accident.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
                USING ({column} = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK ({column} = current_setting('app.current_tenant_id', true)::uuid)
        """)

        # Grant the runtime role basic DML. Specific privileges per service are
        # narrowed in cloud Terraform.
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO sentinelrag_app"
        )

    # Permissions table is platform-global, not tenant-owned. No RLS, but the
    # app role only needs SELECT.
    op.execute("GRANT SELECT ON permissions TO sentinelrag_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON role_permissions, user_roles "
        "TO sentinelrag_app"
    )
    # Sequences: needed for any future serial columns; no-op today but
    # idempotent.
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sentinelrag_app"
    )

    # Override the default privilege grant on future tables so we don't have to
    # remember this in every migration.
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sentinelrag_app
    """)


def downgrade() -> None:
    for table in _TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    # We intentionally do NOT drop the role on downgrade — it may be in use.
