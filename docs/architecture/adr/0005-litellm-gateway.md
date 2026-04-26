# ADR-0005: LiteLLM as the unified LLM gateway

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** llm, observability, cost-tracking

## Context

The platform needs to call LLMs from multiple providers (OpenAI, Anthropic, local Ollama, optionally Cohere/Mistral). The PRD §6.10 requires:

- Token usage tracking per call.
- Cost per tenant.
- Cost-aware model routing (cheap vs expensive).
- Fallback chains on rate limits / outages.
- Caching (semantic + response).

Without an abstraction layer, every service that calls an LLM duplicates: provider SDK selection, retry logic, token counting, cost computation, request logging. This is exactly the role of an LLM gateway.

Options:
- **LiteLLM** (BerriAI, open-source) — unified Python SDK + optional proxy server, supports 100+ providers, cost tables built-in.
- **Portkey** — managed gateway, paid.
- **Helicone** — observability-first, less routing-focused.
- **Roll our own** thin wrapper.

## Decision

Use **LiteLLM** as a Python library (NOT the proxy server) wrapped in a thin adapter at `packages/shared/python/llm/gateway.py`. The adapter:

1. Loads model routing config from a `ModelPolicy` (per-tenant, defined in DB).
2. Calls LiteLLM `completion()` / `embedding()` / `rerank()` with the resolved model.
3. Returns a normalized response object including `prompt_tokens`, `completion_tokens`, `cost_usd`, `provider`, `model_name`, `latency_ms`.
4. Persists a `usage_record` linked to the active `query_session_id` (via context vars).
5. Handles fallback chain (e.g. `gpt-4.1-mini → claude-haiku-4.5 → ollama/llama3.1:8b`).

The adapter — not LiteLLM directly — is what services import. We can swap LiteLLM for something else (or delete it entirely) by changing one file.

We do **not** run LiteLLM as a separate proxy server in v1. Reasons: (a) extra hop and latency, (b) extra service to operate, (c) we already have OpenTelemetry doing the cross-cutting observability LiteLLM-proxy provides. Revisit in Phase 8 if multi-language gateway becomes a need.

## Consequences

### Positive

- One place to change provider routing, retries, cost tables, fallbacks.
- LiteLLM's cost table is updated by upstream maintainers — we don't track OpenAI's pricing changes.
- Local Ollama "just works" via the same interface as OpenAI calls.
- Fallback chains become trivial.

### Negative

- LiteLLM has a high churn rate; we pin a specific version and bump deliberately.
- The cost table can lag — we add a manual override config for newer models.
- When a provider releases a new feature (e.g. structured outputs), we wait on LiteLLM to support it OR fall through to the provider SDK directly for that one call.

### Neutral

- Adapter discipline is required. We don't allow direct `openai.chat.completions.create()` calls outside the adapter (lint rule).

## Alternatives considered

### Option A — Direct provider SDKs
- **Pros:** Newest features available immediately; no third-party churn.
- **Cons:** Code duplication across services; cost tracking re-implemented N times; fallback chains expensive to write.
- **Rejected because:** Re-implementing what LiteLLM does well is unjustified cost.

### Option B — LiteLLM as proxy server
- **Pros:** Multi-language consumption (frontend can call directly); centralized rate limiting.
- **Cons:** Extra hop, extra service, extra failure mode. Frontend doesn't call LLMs directly anyway.
- **Rejected because:** Doesn't earn its complexity at our scale.

### Option C — Portkey / Helicone (managed)
- **Pros:** No infra to run; nicer UI.
- **Cons:** Recurring cost; vendor dependency for a recruiter-grade self-hostable platform.
- **Rejected because:** Conflicts with the self-hostable/portable narrative.

## Trade-off summary

| Dimension | LiteLLM (lib) | Direct SDKs | LiteLLM proxy |
|---|---|---|---|
| Setup time | Low | Low (per provider) | Medium |
| Cost-tracking | Built-in | Hand-rolled | Built-in |
| Fallbacks | Built-in | Hand-rolled | Built-in |
| Latency overhead | ~negligible | None | +network hop |
| Operational components | 0 | 0 | 1 |

## References

- [LiteLLM](https://docs.litellm.ai/)
