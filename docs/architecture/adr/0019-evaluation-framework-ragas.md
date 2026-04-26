# ADR-0019: `ragas` + custom evaluators for evaluation framework

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** evaluation, ragas, llm-as-judge

## Context

PRD §6.7 calls evaluation a "critical hiring signal" and lists:

- **Offline:** context relevance, faithfulness, answer correctness.
- **Online:** user feedback, citation CTR, task success rate.
- **Advanced:** LLM-as-judge, regression testing on prompt changes.

The DB schema (`evaluation_*` tables) is comprehensive. The question is *how* the evaluators are implemented. Options:

- **Build everything from scratch.**
- **`ragas`** — open-source, opinionated RAG-eval library. Faithfulness, answer relevancy, context recall, context precision out of the box.
- **`TruLens`** — observability + eval, more all-in-one.
- **`DeepEval`** — pytest-style RAG evaluators.
- **`promptfoo`** — YAML-driven prompt testing.

## Decision

**`ragas` for the standard evaluators + custom evaluators for the spec-specific ones.**

- Standard evaluators (use ragas):
  - **Faithfulness** — `ragas.metrics.faithfulness`
  - **Context Relevance** — `ragas.metrics.context_precision`
  - **Context Recall** — `ragas.metrics.context_recall`
  - **Answer Relevancy** — `ragas.metrics.answer_relevancy`
- Custom evaluators (`apps/evaluation-service/app/evaluators/`):
  - **Citation Accuracy** — does each citation chunk_id actually appear in retrieved candidates AND support the cited claim? Spec-specific, no library does this.
  - **Hallucination Risk** — wraps the production layered detector (ADR-0010) so eval and runtime use the same code path.
  - **Answer Correctness** — semantic-similarity match against `expected_answer` in the eval case + structured rubric matching (`grading_rubric.must_include` / `must_not_include` in `evaluation_cases`).
  - **LLM Judge** — bespoke prompt for end-to-end grading.
- All evaluators implement a shared `Evaluator` interface returning `EvaluationScore` with `name`, `score [0,1]`, `latency_ms`, `cost_usd`, `reasoning`.
- Eval runs are Temporal workflows (ADR-0007): `EvaluationRunWorkflow` fans out activities per case × evaluator.
- Reports: aggregated scores stored in `evaluation_scores`; summary dashboards in Grafana; PDF/HTML report generation in Phase 9.

## Consequences

### Positive

- We don't reimplement the standard 4 metrics — `ragas` is well-tested and benchmarked.
- Custom evaluators where they matter (citation accuracy, hallucination) — these are the differentiators.
- Same `Evaluator` interface for ragas wrappers and custom evaluators — one code path for the runner.
- Eval-runtime parity for hallucination detection — production uses the same code, reducing drift between eval and prod judgments.

### Negative

- `ragas` has its own LLM call patterns — we must wire it through our LiteLLM gateway (it accepts a `langchain` or `llama-index` LLM; we adapt). Without this, ragas burns its own OpenAI tokens, defeating ADR-0014.
- `ragas` is opinionated and occasionally has breaking changes between versions. We pin and bump deliberately.
- Some `ragas` metrics are LLM-as-judge under the hood — they cost money. We default eval runs to the cloud judge model and surface cost prominently in `evaluation_runs`.

### Neutral

- Online metrics (CTR, user feedback) are not ragas's domain — they live in our own services and stream into the same `evaluation_scores`-shaped data store.

## Alternatives considered

### Option A — Build everything from scratch
- **Pros:** Full control.
- **Cons:** Re-implementing solved problems.
- **Rejected because:** Time, plus ragas is a recruiter-recognized name.

### Option B — `TruLens`
- **Pros:** All-in-one with tracing.
- **Cons:** Heavier; we already have OpenTelemetry tracing.
- **Rejected because:** Overlap with our observability stack.

### Option C — `DeepEval` / `promptfoo`
- **Pros:** Good for ad-hoc prompt tests.
- **Cons:** Less of a portfolio-recognized name; weaker for the "platform" framing.
- **Acceptable alternative:** `promptfoo` could augment ragas for prompt-level regression CI.

## Trade-off summary

| Dimension | ragas + custom | DIY | TruLens |
|---|---|---|---|
| Eng cost | Medium | High | Medium |
| Standard metrics | Built-in | Hand-rolled | Built-in |
| Custom metrics | Easy | Easy | Possible |
| Recruiter recognition | Strong | None | Medium |

## References

- [ragas](https://github.com/explodinggradients/ragas)
- [ragas metrics](https://docs.ragas.io/en/latest/concepts/metrics/index.html)
