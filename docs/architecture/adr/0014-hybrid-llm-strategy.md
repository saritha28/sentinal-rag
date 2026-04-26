# ADR-0014: Hybrid LLM strategy — Ollama default, OpenAI/Anthropic opt-in

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** llm, cost, demo

## Context

The portfolio system needs to actually answer queries when reviewers visit it. Real LLM APIs cost real money, and a portfolio that's "live for two days then disabled because it ran out of credits" is worse than one that's always-on with self-hosted models.

Counter-pressure: cloud LLMs are still meaningfully better than 8B-class self-hosted models on adversarial RAG queries, and the eval framework is the headline portfolio feature — eval reports comparing self-hosted vs. cloud are valuable artifacts.

## Decision

**Hybrid: self-hosted by default, cloud per request.**

### Default path (live demo, dev, eval baseline)
- Generation: **Ollama Llama 3.1 8B Instruct** (fits on a single inexpensive GPU node; CPU-mode in dev is acceptable, slow).
- Embeddings: **`nomic-embed-text`** via Ollama (768-dim).
- Reranker: **bge-reranker-v2-m3** (ADR-0006).
- All three speak the LiteLLM gateway (ADR-0005) interface. No code changes between models.

### Opt-in cloud path (on-demand quality, eval comparisons)
- Per-request override: query body's `generation.model` field can specify `openai/gpt-4.1-mini`, `anthropic/claude-haiku-4-5`, etc.
- Authorization: only tenants with `llm:cloud_models` permission can request cloud models. Default tenant has self-hosted only.
- Embeddings: tenants can opt their collections into `text-embedding-3-small` (1536-dim). Per-collection embedding model means cross-collection retrieval is partitioned by model — explicit, not silent.
- Hard budget cap per tenant per month, enforced in `cost_service` before each LLM call.

### Eval runs (Phase 4)
- Eval datasets are run with both default and cloud models in matrix mode. Results reports show A/B ("our self-hosted Llama 3.1 8B at $0 vs. GPT-4.1-mini at $X reaches Y% faithfulness").

## Consequences

### Positive

- Live demo runs at near-zero ongoing cost.
- Clear cost story for the portfolio: "we built and benchmarked our own infra, then quantified what cloud models add."
- Tenant-level permissioning around cloud models matches real enterprise procurement reality.
- The eval matrix is the headline artifact: a chart showing model × cost × quality.

### Negative

- A small GPU node is required in production for acceptable Ollama latency. Spot `g4dn.xlarge` ~$70/mo on AWS. We accept this.
- Self-hosted model quality is below cloud on hardest queries. The default-path responses won't always be impressive.
- Two embedding models in the same DB means two `embedding_model` rows per chunk for tenants who opt-in to both — storage grows. Acceptable.

### Neutral

- The `chunk_embeddings` table's `(chunk_id, embedding_model)` unique key (already in the schema) is the right design.

## Alternatives considered

### Option A — Cloud only with hard cap
- **Pros:** Best demo quality; simpler infra.
- **Cons:** $50–$200/mo even with caps; "live demo" becomes "live until the hard cap trips." Conflicts with self-hostable narrative.
- **Rejected because:** Ongoing cost + narrative misalignment.

### Option B — Self-hosted only
- **Pros:** $0 ongoing.
- **Cons:** Loses the "I can use cloud models when needed" signal; eval comparison is asymmetric.
- **Rejected because:** A recruiter-grade demo benefits from showing both.

### Option C — Demo-mode-only (no live endpoint)
- **Pros:** No GPU pod needed.
- **Cons:** Reviewers can't *try* the system, just watch a video. Materially weaker portfolio impact.
- **Rejected because:** Live > video.

## Trade-off summary

| Dimension | Hybrid | Cloud only | Self-hosted only |
|---|---|---|---|
| Live-demo cost/mo | ~$70 (GPU) | $50–$200 | ~$70 |
| Demo quality (hardest queries) | OK by default, great on opt-in | Great | OK |
| Eval narrative | A/B matrix | One column | One column |
| Self-hostable claim | Honest | Compromised | Strong |

## References

- [Ollama](https://ollama.com/)
- [Llama 3.1 8B Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct)
- [nomic-embed-text](https://ollama.com/library/nomic-embed-text)
