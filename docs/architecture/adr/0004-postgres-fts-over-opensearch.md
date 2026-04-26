# ADR-0004: Postgres FTS for v1 BM25; OpenSearch deferred to Phase 8

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** retrieval, search, infra-cost

## Context

`Enterprise_RAG_PRD.md` §6.3 and `Enterprise_RAG_Deployment.md` §2 specify **OpenSearch** as the BM25 keyword-search engine. OpenSearch is the heaviest single piece of infra in the spec:

- Minimum 3-node managed cluster for production.
- ~$300+/mo idle on AWS managed OpenSearch (smallest viable production cluster: `t3.medium.search` × 3).
- JVM tuning, snapshot management, version upgrades.
- Separate VPC routing.

For a portfolio system at <10M chunks/tenant, **PostgreSQL Full-Text Search** with `tsvector` + `GIN` indexes delivers competitive BM25 results with one less datastore. Postgres FTS implements BM25-equivalent ranking (`ts_rank_cd` is BM25-shaped; `pg_search` extension if we want pure BM25) and is performant up to ~50M rows on a properly-tuned RDS instance.

## Decision

- **v1 (Phases 1–7):** All keyword-search traffic uses Postgres FTS via a `KeywordSearch` interface in `apps/retrieval-service/app/services/bm25_retriever.py`.
- **v2 (Phase 8):** Implement the same interface against OpenSearch (managed AWS OpenSearch / GCP elasticsearch-compatible). Deploy behind a feature flag; A/B test against Postgres FTS.
- The **Terraform OpenSearch module is NOT created in early phases** (it appears in `infra/terraform/aws/modules/opensearch/` only in Phase 8).
- The K8s manifests and Helm chart values do not reference OpenSearch in v1.
- Schema: add `tsvector` column to `document_chunks` populated by trigger from `content`; GIN index on it.

```sql
ALTER TABLE document_chunks
  ADD COLUMN content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;

CREATE INDEX idx_chunks_content_tsv ON document_chunks USING GIN (content_tsv);
```

(Migration also adds language-aware variant when we support i18n.)

## Consequences

### Positive

- **One fewer datastore** to operate, secure, monitor, and back up.
- Chunks and their search index are transactionally consistent (no async indexing pipeline to babysit).
- ~$300+/mo saved on the live demo.
- Migration story (Phase 8) becomes a *deliberate engineering exercise* with measured before/after — strong recruiter signal ("here's the eval data that proved we needed OpenSearch").

### Negative

- Postgres FTS scoring is `ts_rank` family, not pure Okapi BM25. For most queries indistinguishable; for some long-document or term-frequency-heavy queries, scores will differ from a real BM25 implementation. Mitigated in Phase 8.
- Postgres FTS lacks some niceties: synonym dictionaries are global per-database, fuzzy/typo tolerance requires `pg_trgm`, no native stemming for non-English without effort.
- We give up the recruiter-checkbox of "I deployed OpenSearch on day one."

### Neutral

- The `KeywordSearch` interface forces good abstraction discipline — net positive design pressure.

## Alternatives considered

### Option A — OpenSearch from day one (per spec)
- **Pros:** Matches the spec exactly. Real BM25. Better at >50M chunks. Recruiter checkbox.
- **Cons:** $300+/mo, a JVM cluster to babysit, indexing pipeline to maintain (CDC from Postgres or dual-write), more failure modes.
- **Rejected because:** Cost and complexity are not justified at v1 scale; the migration story is more interesting than the day-one deployment.

### Option B — `pg_search` (ParadeDB) extension
- **Pros:** Pure BM25 inside Postgres; very high quality.
- **Cons:** Newer, smaller community, may not be available on managed RDS without custom AMI. Operational risk for a portfolio.
- **Rejected because:** Requires self-managed Postgres or Aurora customizations; loses the "uses RDS, just works" story.

### Option C — Tantivy / Meilisearch
- **Pros:** Lighter than OpenSearch.
- **Cons:** Yet another component; less recognizable to recruiters than OpenSearch when we eventually add a "real" search engine.
- **Rejected because:** Doesn't beat the migration story OpenSearch gives us in Phase 8.

## Trade-off summary

| Dimension | Postgres FTS v1 | OpenSearch v1 |
|---|---|---|
| Datastores | 1 | 2 |
| Idle cost (AWS) | $0 (in RDS) | ~$300+/mo |
| BM25 fidelity | Approximate | True |
| Indexing pipeline | None (trigger) | CDC or dual-write |
| Recall @ 50M chunks | Degrades | Holds |
| Recruiter signal | "Pragmatic, can scale later" | "Already at scale" |

## Notes on the design docs

**Overrides** `Enterprise_RAG_PRD.md` §6.3 and `Enterprise_RAG_Deployment.md` §2 (the OpenSearch Terraform module) for v1. OpenSearch returns in Phase 8 as a parallel implementation behind the same `KeywordSearch` interface.

## References

- [PostgreSQL Full Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [BM25 vs ts_rank discussion](https://blog.crunchydata.com/blog/postgres-full-text-search-a-search-engine-in-a-database)
