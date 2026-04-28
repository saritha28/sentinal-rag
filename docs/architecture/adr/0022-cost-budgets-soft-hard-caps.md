# ADR-0022: Per-tenant cost budgets with soft / hard caps

- **Status:** Accepted
- **Date:** 2026-04-27
- **Tags:** cost, governance, finops, llm, multi-tenant

## Context

Every LLM call in SentinelRAG is routed through LiteLLM and double-entry recorded into `usage_records` (CLAUDE.md Architecture pillar #5). That gives us *observability* — we can see what every tenant spent. It does not give us *control*: a runaway prompt loop, a misconfigured eval run, or a hostile tenant can rack up cost between two reads of the dashboard.

For a multi-tenant SaaS that targets enterprise buyers, "we'll see it on the invoice" is not acceptable. Buyers expect:

- **Per-tenant budgets** the platform enforces, not just reports.
- **Predictable behavior** at the threshold — clear what happens at 80% spend, at 100% spend, at 110%.
- **An audit trail** of when budgets blocked or downgraded a request, surfacing the same row a finance team can join against the invoice.

We also have to fit this into a request path that already runs retrieval → rerank → generation in a few hundred milliseconds. Anything we add *before* generation budgets out of that.

## Decision

Introduce a `tenant_budgets` table and a `CostService` that gates LLM-cost-incurring requests at two thresholds:

1. **Soft cap** (default 80% of the period limit). Requests proceed but the orchestrator **downgrades** the model — Llama 3.1 70B → Llama 3.1 8B, GPT-4o → GPT-4o-mini, Cohere reranker → BGE local. The downgrade choice lives in a static map seeded at bootstrap, with overrides per tenant.
2. **Hard cap** (default 100%). Requests are **rejected** with `BUDGET_EXCEEDED` (HTTP 402 Payment Required, mapped through the existing error envelope). The error response carries `period_end` so the caller can decide whether to retry next cycle.

### Schema

```
tenant_budgets (
  id              UUID PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  period_type     TEXT NOT NULL CHECK (period_type IN ('day','week','month')),
  limit_usd       NUMERIC(12,4) NOT NULL CHECK (limit_usd > 0),
  soft_threshold_pct  INT NOT NULL DEFAULT 80  CHECK (soft_threshold_pct BETWEEN 0 AND 100),
  hard_threshold_pct  INT NOT NULL DEFAULT 100 CHECK (hard_threshold_pct BETWEEN 0 AND 200),
  downgrade_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
  current_period_start TIMESTAMPTZ NOT NULL,
  current_period_end   TIMESTAMPTZ NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_tenant_budgets_active ON tenant_budgets (tenant_id) WHERE current_period_end > now();
```

RLS policy mirrors the rest of the schema (`USING (tenant_id = current_setting('app.current_tenant_id')::uuid)`).

### Where the check happens

The check runs in `RagOrchestrator.run()` **after retrieval/rerank** but **before generation**:

- After retrieval is chosen because retrieval cost is dominated by embedding/vector ops that are already measurable; we want the budget signal to use the *actual* retrieved-context size, not a worst-case pre-estimate.
- Before generation is the only useful enforcement point. Once the LLM has been called, the cost is sunk.

The estimate is `predicted_input_tokens * unit_input_cost + max_output_tokens * unit_output_cost`, both pulled from a static price table that lives next to the `EMBEDDER_DIMENSIONS` map. The estimate is conservative — we count `max_output_tokens` not the expected, so we over-block before we under-charge.

### What `CostService` does

- `aggregate_period_spend(tenant_id, period_start, period_end) -> Decimal` — `SUM(total_cost_usd) FROM usage_records` with the obvious WHERE.
- `check_budget(tenant_id, estimate_usd) -> BudgetDecision` — returns `BudgetDecision(action: ALLOW|DOWNGRADE|DENY, current_spend, limit, threshold_hit, downgrade_to: str|None)`.
- The service caches the active-budget row per tenant for 60s in the orchestrator's request lifetime (Redis cache in Phase 7); the spend SUM is *not* cached because that's the moving signal we want to read fresh.

### Audit

Every `DOWNGRADE` and `DENY` produces an `audit_events` row (event_type = `budget.downgraded` or `budget.denied`) via the new `AuditService` (ADR-0016 implementation). The row carries the budget id, the estimate, the current spend, and the threshold pct.

## Consequences

### Positive

- Enterprise buyers get a clear, configurable budget knob with predictable threshold behavior.
- Downgrade-on-soft-cap is a useful product feature, not just a safety valve — eval runs that don't need GPT-4o transparently fall back.
- The audit trail makes "why was my request downgraded yesterday at 14:32" answerable from a single SQL join.

### Negative

- One more DB round-trip in the hot path. Mitigated by a 60s cache on the budget row and a single SUM query on `usage_records` (which is already indexed on `(tenant_id, created_at)` per migration 0009).
- Cost-table maintenance burden. New models require a price-table update; without it, `check_budget` falls back to a conservative default that may downgrade aggressively.
- Soft-cap downgrade can mask a quality regression in user-facing answers. Mitigation: emit a `cost.budget.downgrade_active` metric (ADR-0023) and surface the badge in the playground UI.

### Neutral

- We do **not** model budget rollover. A monthly budget that's 10% under at month-end resets cleanly; we don't carry the unspent into next month. If a tenant wants an annual budget with monthly rollover, they get an annual `period_type` row.

## Alternatives considered

### Option A — Hard cap only, no downgrade
- **Pros:** Simpler. One threshold, one decision.
- **Cons:** Loses the "graceful degradation" product feature; abrupt 402 at 100% is a worse UX than transparent downgrade at 80%.
- **Rejected:** Two-threshold UX is what enterprise buyers expect (compare AWS Budgets actions).

### Option B — Pre-paid credits ledger instead of period budgets
- **Pros:** Atomic decrement, no SUM-then-check race.
- **Cons:** Complicates the schema (ledger entries, refunds for failed generations); period-based budgets are what finance teams actually plan against.
- **Rejected for v1:** Period model is sufficient until we have hostile-tenant pressure that the SUM-and-check race actually matters in practice.

### Option C — Enforce in LiteLLM gateway (proxy-level budget)
- **Pros:** Off-the-shelf; LiteLLM already has a budget feature.
- **Cons:** LiteLLM's budget is keyed on its API-key model; doesn't know the SentinelRAG tenant_id. We'd have to per-tenant API keys + ops cost.
- **Rejected:** SentinelRAG owns the tenant boundary; the platform enforces, not the gateway.

## Trade-off summary

| Dimension | Soft+Hard caps (this) | Hard cap only | Credits ledger |
|---|---|---|---|
| Enforcement strength | Strong | Strong | Strongest |
| UX at threshold | Graceful | Abrupt | Graceful |
| Schema complexity | Low | Low | Medium |
| Hot-path cost | +1 DB round-trip (cached) | +1 DB round-trip (cached) | +1 DB write |
| Audit clarity | Per-event | Per-event | Per-decrement |

## References

- ADR-0005 (LiteLLM gateway — where the cost data is captured)
- ADR-0016 (audit dual-write — where DOWNGRADE/DENY events get persisted)
- CLAUDE.md "Architecture pillar #5: Cost is observed before it's optimized"
- Migration 0009 — `usage_records` partitioning
- Migration 0012 — `tenant_budgets` (introduced by this ADR)
