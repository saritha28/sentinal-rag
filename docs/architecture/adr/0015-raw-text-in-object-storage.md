# ADR-0015: Raw document text stored in object storage, not Postgres

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** storage, schema, scalability

## Context

`Enterprise_RAG_Database_Design.md` §5.2 has:

```sql
CREATE TABLE document_versions (
    ...
    raw_text TEXT,
    storage_uri TEXT,
    ...
);
```

A 200-page PDF can extract to ~500KB of text; a multi-thousand-page corpus rapidly bloats the table beyond Postgres's comfort zone for a column type meant for short strings. TOAST'd columns have predictable performance issues at scale (fetching `raw_text` on `SELECT *` is silently expensive; vacuum/backup costs balloon).

The schema already has `storage_uri TEXT` — clearly the original intent was object storage. We make this explicit and remove the `raw_text` ambiguity.

## Decision

- **`document_versions.raw_text` is dropped** from the migration that creates the table.
- `storage_uri` becomes mandatory and is the canonical source of raw text.
- Raw text is written to object storage (S3/GCS/MinIO) at path:
  ```
  s3://<bucket>/<tenant_id>/documents/<document_id>/versions/<version_id>/raw.txt
  ```
  with `Content-Type: text/plain; charset=utf-8` and `Content-Encoding: gzip`.
- An `ObjectStorage` interface (per ADR-0011 portability) abstracts the cloud-specific client.
- Chunked content (`document_chunks.content`) **stays in Postgres** — it's bounded (a few hundred to a few thousand chars per chunk), feeds Postgres FTS via `tsvector`, and joins to embeddings.
- Original binary (PDF, DOCX) is also kept in object storage at:
  ```
  s3://<bucket>/<tenant_id>/documents/<document_id>/versions/<version_id>/original.<ext>
  ```
- For very small documents (<32KB raw text), we still write to object storage — uniformity wins over a special case.

## Consequences

### Positive

- `document_versions` rows stay small and fast.
- Postgres backups are reasonable size.
- We can stream raw text to a worker without pulling a giant column from the DB.
- Object storage is cheaper than Postgres storage at scale (~10× cost difference).

### Negative

- One extra read (object storage fetch) when re-chunking or re-embedding. Acceptable: re-chunking is rare and async.
- Backup/restore now spans two stores. We document the procedure in `docs/operations/backup.md`.
- Authorization on raw-text reads requires presigned URLs scoped per-request, not a simple SQL `SELECT`. Implemented in `document_service.get_raw_text(...)` — never expose direct S3 paths.

### Neutral

- Chunk content lives in two places (Postgres rows AND derivable from raw.txt). The Postgres copy is the source of truth for retrieval; raw.txt is only for re-processing.

## Alternatives considered

### Option A — Keep `raw_text TEXT` (per spec)
- **Pros:** Single store; `SELECT raw_text FROM ...` works.
- **Cons:** Bloats DB; vacuum cost; TOAST slow path.
- **Rejected because:** Won't scale beyond a few thousand documents per tenant.

### Option B — Use Postgres `LARGE OBJECT` (lo) type
- **Pros:** In-DB, no extra service.
- **Cons:** Awkward API; lacks the operational story of S3 (lifecycle, replication, versioning).
- **Rejected because:** Worse than either option.

## Trade-off summary

| Dimension | Object storage | Postgres TEXT | Postgres LO |
|---|---|---|---|
| Storage cost @ scale | $0.023/GB/mo | ~$0.115/GB/mo | ~$0.115/GB/mo |
| Read latency (cold) | ~50–200ms | ~5–50ms | ~5–50ms |
| DB backup time | Bounded | Grows | Grows |
| Authorization | Presigned URLs | SQL | SQL |

## Notes on the design docs

**Overrides** `Enterprise_RAG_Database_Design.md` §5.2. The Alembic migration creates `document_versions` without `raw_text`; `storage_uri` is `NOT NULL`.

## References

- [Postgres TOAST](https://www.postgresql.org/docs/current/storage-toast.html)
