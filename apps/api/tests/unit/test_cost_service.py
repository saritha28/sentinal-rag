"""Unit tests for CostService budget gating (ADR-0022)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.db.models import TenantBudget
from app.services.cost_service import (
    BudgetAction,
    BudgetDecision,
    CostService,
    enforce_or_raise,
    estimate_completion_cost,
)
from sentinelrag_shared.errors import BudgetExceededError


# A stand-in for TenantBudgetRepository — keeps the unit test free of a real
# session. The repository contract the service consumes is just the two
# methods below, so a duck-typed fake is enough.
class FakeBudgetRepo:
    def __init__(
        self,
        *,
        budget: TenantBudget | None,
        spend: Decimal,
    ) -> None:
        self._budget = budget
        self._spend = spend

    async def get_active(self, tenant_id: UUID) -> TenantBudget | None:
        return self._budget

    async def period_spend(
        self,
        tenant_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Decimal:
        return self._spend


def _make_budget(
    *,
    limit: str = "100.00",
    soft: int = 80,
    hard: int = 100,
    downgrade_policy: dict[str, Any] | None = None,
) -> TenantBudget:
    now = datetime.now(UTC)
    return TenantBudget(
        id=uuid4(),
        tenant_id=uuid4(),
        period_type="month",
        limit_usd=Decimal(limit),
        soft_threshold_pct=soft,
        hard_threshold_pct=hard,
        downgrade_policy=downgrade_policy or {},
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
    )


@pytest.mark.unit
def test_estimate_uses_max_output_tokens() -> None:
    cheap = estimate_completion_cost(
        model="openai/gpt-4o-mini",
        estimated_input_tokens=1_000,
        max_output_tokens=100,
    )
    expensive = estimate_completion_cost(
        model="openai/gpt-4o-mini",
        estimated_input_tokens=1_000,
        max_output_tokens=2_000,
    )
    assert expensive > cheap


@pytest.mark.unit
def test_estimate_unknown_model_falls_back_to_ceiling() -> None:
    # Unknown model uses gpt-4o pricing — should be more expensive than mini
    # for the same token shape.
    unknown = estimate_completion_cost(
        model="some-future-model/foo",
        estimated_input_tokens=1_000,
        max_output_tokens=500,
    )
    mini = estimate_completion_cost(
        model="openai/gpt-4o-mini",
        estimated_input_tokens=1_000,
        max_output_tokens=500,
    )
    assert unknown > mini


@pytest.mark.unit
@pytest.mark.asyncio
class TestCheckBudget:
    async def test_no_budget_configured_allows(self) -> None:
        repo = FakeBudgetRepo(budget=None, spend=Decimal("0"))
        svc = CostService(repo)  # type: ignore[arg-type]
        decision = await svc.check_budget(
            tenant_id=uuid4(),
            estimate_usd=Decimal("0.50"),
            requested_model="openai/gpt-4o",
        )
        assert decision.action == BudgetAction.ALLOW
        assert decision.reason == "no-budget-configured"

    async def test_under_soft_cap_allows(self) -> None:
        budget = _make_budget(limit="100.00")
        repo = FakeBudgetRepo(budget=budget, spend=Decimal("10"))
        svc = CostService(repo)  # type: ignore[arg-type]
        decision = await svc.check_budget(
            tenant_id=budget.tenant_id,
            estimate_usd=Decimal("1.00"),
            requested_model="openai/gpt-4o",
        )
        assert decision.action == BudgetAction.ALLOW

    async def test_at_soft_cap_downgrades(self) -> None:
        # 80% of 100 = 80 soft cap; 75 + 6 = 81 → soft.
        budget = _make_budget(limit="100.00")
        repo = FakeBudgetRepo(budget=budget, spend=Decimal("75"))
        svc = CostService(repo)  # type: ignore[arg-type]
        decision = await svc.check_budget(
            tenant_id=budget.tenant_id,
            estimate_usd=Decimal("6.00"),
            requested_model="openai/gpt-4o",
        )
        assert decision.action == BudgetAction.DOWNGRADE
        assert decision.downgrade_to == "openai/gpt-4o-mini"

    async def test_no_downgrade_available_falls_back_to_allow(self) -> None:
        # ollama models have no cheaper tier; soft-cap-hit just emits a warn.
        budget = _make_budget(limit="100.00")
        repo = FakeBudgetRepo(budget=budget, spend=Decimal("85"))
        svc = CostService(repo)  # type: ignore[arg-type]
        decision = await svc.check_budget(
            tenant_id=budget.tenant_id,
            estimate_usd=Decimal("1.00"),
            requested_model="ollama/llama3.1:8b",
        )
        assert decision.action == BudgetAction.ALLOW
        assert "soft-cap-hit" in (decision.reason or "")

    async def test_over_hard_cap_denies(self) -> None:
        budget = _make_budget(limit="100.00")
        repo = FakeBudgetRepo(budget=budget, spend=Decimal("99"))
        svc = CostService(repo)  # type: ignore[arg-type]
        decision = await svc.check_budget(
            tenant_id=budget.tenant_id,
            estimate_usd=Decimal("5.00"),
            requested_model="openai/gpt-4o",
        )
        assert decision.action == BudgetAction.DENY

    async def test_per_tenant_downgrade_override_wins(self) -> None:
        budget = _make_budget(
            limit="100.00",
            downgrade_policy={"openai/gpt-4o": "anthropic/claude-3-5-haiku"},
        )
        repo = FakeBudgetRepo(budget=budget, spend=Decimal("85"))
        svc = CostService(repo)  # type: ignore[arg-type]
        decision = await svc.check_budget(
            tenant_id=budget.tenant_id,
            estimate_usd=Decimal("1.00"),
            requested_model="openai/gpt-4o",
        )
        assert decision.action == BudgetAction.DOWNGRADE
        assert decision.downgrade_to == "anthropic/claude-3-5-haiku"


@pytest.mark.unit
def test_enforce_or_raise_returns_downgrade_target() -> None:
    decision = BudgetDecision(
        action=BudgetAction.DOWNGRADE,
        current_spend_usd=Decimal("85"),
        limit_usd=Decimal("100"),
        period_end="2026-04-30T00:00:00+00:00",
        downgrade_to="openai/gpt-4o-mini",
    )
    assert enforce_or_raise(decision) == "openai/gpt-4o-mini"


@pytest.mark.unit
def test_enforce_or_raise_raises_on_deny() -> None:
    decision = BudgetDecision(
        action=BudgetAction.DENY,
        current_spend_usd=Decimal("105"),
        limit_usd=Decimal("100"),
        period_end="2026-04-30T00:00:00+00:00",
        reason="over hard cap",
    )
    with pytest.raises(BudgetExceededError) as ei:
        enforce_or_raise(decision)
    assert ei.value.details["limit_usd"] == "100"


@pytest.mark.unit
def test_enforce_or_raise_returns_none_on_allow() -> None:
    decision = BudgetDecision(
        action=BudgetAction.ALLOW,
        current_spend_usd=Decimal("0"),
        limit_usd=Decimal("100"),
        period_end="2026-04-30T00:00:00+00:00",
    )
    assert enforce_or_raise(decision) is None
