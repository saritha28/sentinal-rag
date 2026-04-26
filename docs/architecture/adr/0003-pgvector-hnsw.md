# ADR-0003: pgvector with HNSW indexes (overrides spec's ivfflat)

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** database, vector-search, pgvector, retrieval

## Context

`Enterprise_RAG_Database_Design.md` §5.4 specifies:

```sql
CREATE INDEX idx_chunk_embeddings_vector
ON chunk_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

`ivfflat` was the only viable pgvector index in 2023. Since pgvector 0.5.0 (mid-2023), **HNSW** has been available and is now the production default for two reasons:

1. **Recall.** At equal latency budget HNSW reliably beats ivfflat by 5–15% on standard benchmarks (Wikipedia, MS MARCO). For a recruiter-grade RAG demo, retrieval recall is *the* metric.
2. **Operational.** ivfflat requires `REINDEX` after meaningful insertion volume to maintain quality (the cluster centroids drift). HNSW supports incremental insert without reindexing.

The trade-offs (RAM, build time) are real but acceptable at our scale (<10M chunks per tenant in v1).

## Decision

Use **HNSW** with `vector_cosine_ops`:

```sql
CREATE INDEX idx_chunk_embeddings_vector
ON chunk_embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

- `m = 16`, `ef_construction = 64` are pgvector's recommended defaults — tune later only if benchmarks demand.
- Query-time `hnsw.ef_search` is set per-query in `apps/retrieval-service`, default 40, tunable up to 100 for high-recall paths.
- Single index per `(tenant_id, embedding_model)` pair. We do NOT prefilter on `tenant_id` via the index — RLS handles that — but we partition by `embedding_model` because cross-model search is meaningless.

## Consequences

### Positive

- Higher recall at the same latency.
- No periodic `REINDEX` operational burden.
- Inserts during ingestion don't degrade index quality.

### Negative

- HNSW uses ~2–3× more RAM than ivfflat per index.
- Initial index build is slower (matters at first migration on existing data; rare afterward).
- We assume pgvector ≥ 0.7.0 (HNSW + filter pushdown improvements). RDS PostgreSQL must support this — verify in Terraform module.

### Neutral

- Index hyperparameters (`m`, `ef_construction`) become things we have to remember to tune.

## Alternatives considered

### Option A — Keep ivfflat
- **Pros:** Less RAM, faster to build, the spec already says it.
- **Cons:** Lower recall, requires REINDEX maintenance, signals "I copy-pasted a 2023 tutorial."
- **Rejected because:** The PRD targets retrieval precision@5 > 85% — a goal HNSW makes meaningfully easier.

### Option B — External vector DB (Qdrant / Weaviate / Milvus)
- **Pros:** HNSW out of the box, more retrieval features, scales further.
- **Cons:** Another datastore to operate; another network hop; data-consistency issues between Postgres rows and external vector store; loses the "ACID-on-everything" Postgres-only story which is itself a portfolio asset.
- **Rejected because:** At our scale pgvector wins. ADR-0004 (drop OpenSearch) follows the same "fewer datastores" thesis.

## Trade-off summary

| Dimension | HNSW | ivfflat | External vector DB |
|---|---|---|---|
| Recall@10 (typical) | 0.92–0.97 | 0.80–0.90 | 0.93–0.98 |
| RAM per 1M vectors @ 1536d | ~12 GB | ~6 GB | varies |
| Reindex needed on insert | No | Yes (eventually) | No |
| Operational components | 1 (Postgres) | 1 (Postgres) | 2+ |

## Notes on the design docs

**Overrides** `Enterprise_RAG_Database_Design.md` §5.4. The Alembic migration must use HNSW, not ivfflat. Do NOT migrate to ivfflat to "match the doc."

## References

- [pgvector HNSW](https://github.com/pgvector/pgvector#hnsw)
- [Malkov & Yashunin, HNSW paper (2016)](https://arxiv.org/abs/1603.09320)
