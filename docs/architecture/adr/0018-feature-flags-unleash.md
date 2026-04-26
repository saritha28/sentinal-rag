# ADR-0018: Unleash self-hosted for feature flags

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** feature-flags, prompt-routing, experimentation

## Context

PRD §6.6 requires "A/B testing prompts" and "regression testing on prompt changes." Without a feature-flag layer, prompt-version routing requires a service redeploy for every experiment. That's slow and hides flag state in app config rather than making it observable.

A feature-flag service also enables:

- Tenant-level rollout of new retrieval strategies.
- Per-tenant kill switches (a misbehaving tenant can be locked out of expensive paths).
- Gradual rollouts of model changes ("10% of queries use new judge model").

Choices:

- **Unleash** — open-source, K8s-native, mature, has a UI.
- **GrowthBook** — open-source, more experimentation-focused.
- **LaunchDarkly** — managed, gold standard, paid.
- **DIY DB-backed flags** — table + API.

## Decision

**Unleash self-hosted** in K8s.

- Helm chart from `unleash/unleash`, separate Postgres database from app data.
- Two SDKs in use:
  - **Python:** `UnleashClient` initialized at service start; cached in-memory; refreshed every 30s.
  - **TypeScript:** `unleash-proxy-client` (frontend) + `unleash-client` (Next.js server actions).
- Flag naming: `<scope>.<feature>.<variant>` — e.g. `retrieval.rerank.use_cohere`, `prompt.rag_default.version_v3`.
- Tenant context propagated to the flag SDK so per-tenant rollouts work.
- A small wrapper at `packages/shared/python/feature_flags/` makes the rest of the codebase ignorant of Unleash specifics.

Flag categories used in v1:
- **Rollouts:** `prompt.<template>.version` returns the active version ID for routing through `prompt_service`.
- **Kill switches:** `llm.cloud_models.enabled`, `eval.llm_judge.enabled`.
- **Experiments:** `retrieval.hybrid_weights.experiment_a` (variant: `default | bm25_heavy | vector_heavy`).

## Consequences

### Positive

- Prompts and retrieval strategies can be flighted without redeploys.
- Kill-switching a tenant or feature is fast and observable.
- Experiment variants integrate with the eval framework — we record the flag variant on `query_session` metadata and analyze by variant.

### Negative

- One more service to operate (Unleash + its Postgres). ~half a day to set up properly.
- Flag debt is real; we add a quarterly "flag cleanup" task.
- Latency: Unleash SDKs cache aggressively (30s default), but the first lookup at service startup blocks. Mitigation: warm cache before serving traffic.

### Neutral

- The wrapper layer means swapping providers later (e.g. to GrowthBook) is one-file work.

## Alternatives considered

### Option A — DIY DB-backed flags
- **Pros:** No new infra.
- **Cons:** No UI, no SDK ecosystem, building a poor Unleash.
- **Rejected because:** Re-implementing existing OSS.

### Option B — GrowthBook
- **Pros:** Better experimentation analytics.
- **Cons:** Slightly less polished SDK story; smaller community.
- **Acceptable alternative:** Could swap if experimentation analytics become primary.

### Option C — LaunchDarkly
- **Pros:** Best-in-class.
- **Cons:** Paid; conflicts with self-hostable narrative.
- **Rejected because:** Same as ADR-0008 reasoning.

## Trade-off summary

| Dimension | Unleash | GrowthBook | LaunchDarkly | DIY |
|---|---|---|---|---|
| Self-hosted | Yes | Yes | No | Yes |
| Cost | $0 (infra) | $0 (infra) | $$$ | $0 (eng time) |
| UI quality | Good | Good | Best | None |
| SDK ecosystem | Broad | Broad | Broadest | None |

## References

- [Unleash](https://www.getunleash.io/)
