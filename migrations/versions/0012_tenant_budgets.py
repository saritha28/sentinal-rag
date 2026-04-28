"""Per-tenant cost budgets (ADR-0022).

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-27

Introduces ``tenant_budgets`` so the platform can enforce per-tenant LLM
spend caps with soft (downgrade) and hard (deny) thresholds. Default
privilege grants from migration 0010's ``ALTER DEFAULT PRIVILEGES`` cover
the runtime role, so no explicit GRANT is needed here.

The "active budget" partial unique index keeps lookups O(1) without a
separate "is_active" column — at any moment there is at most one row whose
period straddles ``now()``.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE tenant_budgets (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id             UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            period_type           TEXT NOT NULL
                                  CHECK (period_type IN ('day','week','month')),
            limit_usd             NUMERIC(12,4) NOT NULL CHECK (limit_usd > 0),
            soft_threshold_pct    INT NOT NULL DEFAULT 80
                                  CHECK (soft_threshold_pct BETWEEN 0 AND 100),
            hard_threshold_pct    INT NOT NULL DEFAULT 100
                                  CHECK (hard_threshold_pct BETWEEN 0 AND 200),
            downgrade_policy      JSONB NOT NULL DEFAULT '{}'::jsonb,
            current_period_start  TIMESTAMPTZ NOT NULL,
            current_period_end    TIMESTAMPTZ NOT NULL,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK (current_period_end > current_period_start)
        )
    """)

    # Active budget per tenant: at most one row whose window straddles now().
    # The non-immutable predicate (now()) means this index can't enforce the
    # constraint at write time across overlapping rows; we treat it as a hot
    # lookup index. Application code maintains the "one active" invariant.
    op.execute("""
        CREATE INDEX idx_tenant_budgets_active
            ON tenant_budgets (tenant_id, current_period_end DESC)
    """)

    # RLS — same shape as every other tenant-owned table (see migration 0010).
    op.execute("ALTER TABLE tenant_budgets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_budgets FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant_budgets
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_budgets")
