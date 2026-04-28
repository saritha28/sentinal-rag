"""Tenant budget repository (ADR-0022)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import desc, func, select, text

from app.db.models import TenantBudget
from app.db.repositories.base import BaseRepository


class TenantBudgetRepository(BaseRepository[TenantBudget]):
    model = TenantBudget

    async def get_active(self, tenant_id: UUID) -> TenantBudget | None:
        """Return the active-window budget row for the tenant, if any.

        "Active" = ``current_period_end > now()``. We pick the most recent
        end if multiple rows match (the application maintains the
        "one active per tenant" invariant; this is just defensive).
        """
        stmt = (
            select(TenantBudget)
            .where(TenantBudget.tenant_id == tenant_id)
            .where(TenantBudget.current_period_end > func.now())
            .order_by(desc(TenantBudget.current_period_end))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def period_spend(
        self,
        tenant_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Decimal:
        """``SUM(total_cost_usd) FROM usage_records`` over the budget window.

        Returns ``Decimal('0')`` for empty windows. We use raw SQL because
        ``usage_records`` is partitioned and we want to lean on the
        partition-elimination plan rather than the ORM.
        """
        result = await self.session.execute(
            text(
                "SELECT COALESCE(SUM(total_cost_usd), 0) "
                "FROM usage_records "
                "WHERE tenant_id = :tid "
                "  AND created_at >= :start "
                "  AND created_at <  :end"
            ),
            {"tid": str(tenant_id), "start": period_start, "end": period_end},
        )
        value = result.scalar_one()
        # SUM may come back as Decimal, int, or float depending on driver
        # round-tripping; normalize.
        return Decimal(str(value))
