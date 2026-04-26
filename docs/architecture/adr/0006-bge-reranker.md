# ADR-0006: bge-reranker-v2-m3 as default reranker

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** retrieval, reranker, ml-models

## Context

`Enterprise_RAG_PRD.md` §6.3 requires a "cross-encoder reranker" stage in the hybrid retrieval pipeline. The choices in 2026:

- **Cohere Rerank 3** — paid API, strong quality, vendor lock-in, ~$1/1k searches.
- **Jina Reranker v2** — paid API, similar shape.
- **bge-reranker-v2-m3** (BAAI) — open-source, multilingual, runs on CPU at acceptable latency, GPU recommended.
- **mxbai-rerank-large-v1** — open-source, strong on English benchmarks.
- **MS MARCO MiniLM cross-encoder** — older but very small/fast.

For a self-hostable, recruiter-grade platform with the "Hybrid LLM strategy: Ollama default" decision (ADR-0014), an open-source reranker matches the narrative. `bge-reranker-v2-m3` is the current strongest open option on multilingual MTEB benchmarks and integrates cleanly via `sentence-transformers` or `FlagEmbedding`.

## Decision

- Default: **`BAAI/bge-reranker-v2-m3`**, served via a small `apps/retrieval-service` GPU pod (or CPU pod for dev — slower but functional).
- Interface: `Reranker.rerank(query: str, candidates: list[Chunk], top_k: int) -> list[RerankedChunk]` in `apps/retrieval-service/app/services/reranker.py`.
- Adapters shipped: `BgeReranker` (default), `CohereReranker` (env-flag), `NoOpReranker` (returns top_k by hybrid score; for tests).
- Inference batching: pad-to-batch within a 50ms window to amortize GPU cost.
- Production deployment: dedicated K8s deployment with GPU node selector (`nvidia.com/gpu: 1`), HPA on inference queue depth.

## Consequences

### Positive

- Zero per-query cost on the live demo.
- Open-source narrative ("we run our own model") is a stronger signal than "we hit Cohere's API."
- Multilingual support out of the box (m3 = multilingual + multifunctional + multigranular).
- Offline-able — no Internet egress on the hot retrieval path.

### Negative

- **GPU node pool required** for acceptable latency at scale. This adds infra cost (~$70/mo for a `g4dn.xlarge` spot in AWS) and complexity. CPU mode is functional for dev/demo at low QPS but adds ~150–400ms per rerank.
- Model artifacts must be baked into the image or pulled at startup — we choose to bake into image (~2GB layer).
- Quality is competitive with but slightly below Cohere Rerank 3 on English-only MS MARCO. On most enterprise data we tested it's a wash.

### Neutral

- The `Reranker` interface forces good abstraction.

## Alternatives considered

### Option A — Cohere Rerank 3
- **Pros:** Best out-of-box quality; no infra.
- **Cons:** Per-query cost; vendor lock-in; conflicts with "self-hostable" narrative.
- **Rejected because:** ADR-0014 already commits to self-hosted-first.

### Option B — No reranker, hybrid-merge only
- **Pros:** Simpler; lower latency.
- **Cons:** PRD requires reranker; recall@k drops measurably without it on long-tail queries.
- **Rejected because:** Spec violation and quality regression.

### Option C — MS MARCO MiniLM cross-encoder (older small model)
- **Pros:** Tiny (~100MB), fast on CPU.
- **Cons:** English-only; clearly weaker on retrieval benchmarks.
- **Rejected because:** Too dated for a 2026 portfolio.

## Trade-off summary

| Dimension | bge-reranker-v2-m3 | Cohere Rerank 3 | No reranker |
|---|---|---|---|
| Per-query cost | $0 | ~$0.001 | $0 |
| Latency (GPU) | 80–150ms | 100–200ms (network) | 0ms |
| Latency (CPU) | 200–500ms | same | 0ms |
| nDCG@10 (MS MARCO) | ~0.41 | ~0.43 | ~0.36 |
| Multilingual | Yes | English-strong | N/A |
| Infra components | +1 GPU pod | 0 | 0 |

## References

- [BAAI bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [MTEB Reranking benchmark](https://huggingface.co/spaces/mteb/leaderboard)
