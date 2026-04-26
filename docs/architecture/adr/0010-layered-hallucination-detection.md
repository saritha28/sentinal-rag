# ADR-0010: Layered hallucination detection (cheap → expensive cascade)

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** evaluation, hallucination, llm

## Context

PRD §6.5 lists three hallucination-detection techniques:

- Answer vs source similarity scoring.
- LLM-as-judge validation.
- Retrieval coverage scoring.

The PRD presents these as parallel options. Production-grade RAG systems combine them in a **cascade**: cheap signals run on every query for the hot path; expensive LLM-as-judge runs only on flagged or sampled queries to control cost and latency.

Without this layering, two failure modes:

1. **All-LLM-judge:** every query incurs $0.001+ and 800ms+ for hallucination scoring. Doubles RAG cost and latency.
2. **Embedding-only:** misses contradictions that share embedding space ("the deployment succeeded" vs "the deployment failed" can have high similarity).

## Decision

Three layers, each running on every relevant query:

### Layer 1 — Free signals (every query)
- **Token overlap:** unigram + bigram overlap between answer and concatenated retrieved chunks. Score in `[0, 1]`.
- **Citation completeness:** does each claim in the answer have at least one citation? Implemented as a structured-output prompt enforcing `[citation_n]` markers, then verifying every sentence has one.
- **Retrieval coverage:** what fraction of answer tokens are paraphrased from retrieved context vs. introduced by the model? Done via embedding-similarity per-sentence to nearest retrieved chunk.

These produce `grounding_score` (persisted on `generated_answers`).

### Layer 2 — Cheap NLI (every query)
- **Model:** `cross-encoder/nli-deberta-v3-base` (or smaller variant for budget). Self-hosted on the reranker pod.
- **Pairwise:** for each (claim, supporting-chunk) pair, classify as ENTAILMENT / NEUTRAL / CONTRADICTION.
- Latency: ~30–50ms for typical answer (4–8 claims × 2 supporting chunks).
- Output: `nli_contradiction_count`, `nli_neutral_count` aggregated into `hallucination_risk_score`.

### Layer 3 — LLM-as-judge (sampled / flagged)
- **Trigger conditions:**
  - Layer 2 risk score > 0.4 (high risk → always judge).
  - 5% random sampling otherwise (calibration).
  - Always for evaluation runs (where cost is acceptable).
- **Model:** the LLM gateway routes to a "judge" alias (default: same provider as generator but with judge-specific prompt). Could be a stronger model than the generator (e.g. judge with Claude Sonnet, generate with Haiku).
- **Output:** structured JSON via the judge's structured-output mode: `{verdict, reasoning, evidence_quality, missing_evidence[]}`.
- Persisted on `generated_answers.hallucination_risk_score` (rebound) and `generated_answers.judge_reasoning`.

### Abstention
When `hallucination_risk_score > tenant.abstention_threshold` AND `query.abstain_if_unsupported` is true, the orchestrator returns:
> "I do not have enough information in the provided sources to answer that confidently."
plus the candidates that were retrieved (transparent failure).

## Consequences

### Positive

- Hot-path latency stays under 100ms for hallucination signals (Layers 1+2).
- Cost stays bounded (LLM-judge runs on ~5–10% of traffic).
- Rich, multi-dimensional signals: even if any one layer mis-fires, the others compensate.
- The `confidence_score`, `hallucination_risk_score`, `grounding_score` columns in `generated_answers` (already in the schema) map cleanly onto Layers 1+2.

### Negative

- Three subsystems to maintain. Each can drift in calibration.
- NLI model must be loaded into the retrieval-service pod (or its own pod) — extra memory.
- LLM-judge cost is non-zero; we have to monitor the sampling rate vs. budget.

### Neutral

- The cascade thresholds become tunables exposed in admin UI.

## Alternatives considered

### Option A — LLM-as-judge on every query
- **Pros:** Simplest; highest fidelity.
- **Cons:** Doubles cost and latency.
- **Rejected because:** Unacceptable for online query path.

### Option B — Embedding-similarity only
- **Pros:** Free, fast.
- **Cons:** Misses contradictions; calibration is brittle.
- **Rejected because:** Quality regressions on adversarial queries.

## Trade-off summary

| Dimension | Layered cascade | LLM-judge always | Embedding only |
|---|---|---|---|
| Per-query cost | $0 + sampled $0.001 | $0.001 | $0 |
| Per-query latency | +30–80ms | +500–1000ms | +5ms |
| Detection quality | High | Highest | Medium |
| Subsystems | 3 | 1 | 1 |

## References

- [RAG hallucination evaluation patterns](https://arxiv.org/abs/2401.00396)
- [DeBERTa-v3 NLI](https://huggingface.co/cross-encoder/nli-deberta-v3-base)
