# ADR-0016: Audit log dual-write to Postgres + S3 Object Lock

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** audit, security, compliance

## Context

PRD §6.9 calls audit logs "immutable" with "query replay capability." The DB schema has an `audit_events` table with append-only columns. But Postgres alone is not immutable:

- An admin with `DELETE` privilege can wipe rows.
- Backups can be tampered with by anyone with backup-admin access.
- Logical replication can be silently disabled.

Real compliance frameworks (SOC 2, HIPAA, PCI-DSS) require **independent immutable storage** of security-relevant events. The standard production pattern: write to a queryable database for reasonably-recent reads, and mirror to immutable object storage (S3 with Object Lock in Compliance mode) for the audit-grade record.

## Decision

Dual-write every audit event:

### Write 1 — Postgres
- `audit_events` table (per spec).
- Indexed for application-level lookups: `idx_audit_events_tenant_created`, `idx_audit_events_resource`.
- Partitioned monthly (per spec §11).
- Used by `/audit/events` API.
- Retention: 90 days hot, then dropped from Postgres (S3 has the long-term copy).

### Write 2 — S3 with Object Lock
- Bucket: `<project>-<env>-audit-log`, Object Lock **enabled at bucket creation** (cannot be added later — must be set at create time).
- Lock mode: **Compliance** (cannot be unlocked even by root).
- Default retention: 7 years.
- Object key: `tenant_id=<uuid>/year=<YYYY>/month=<MM>/day=<DD>/hour=<HH>/<event_uuid>.json.gz`.
- Format: gzipped JSON, one event per object (cheap; we batch-read by prefix).
- Replication to a second bucket in another region: enabled.
- KMS-encrypted with bucket-specific CMK.

### Write coordination
- The audit middleware writes to Postgres synchronously (request-blocking) and **publishes to a queue** (Redis Streams or Temporal signal) for the S3 write. The S3 write is async because it must not block the request.
- A daily reconciliation job compares the Postgres `audit_events` for the previous day against the S3 prefix and alerts on any drift.
- If the S3 write fails for >5min on a tenant: we **escalate to an alert**, but we do NOT block writes (availability > durability for a single async path; reconciliation backfills).

### Read paths
- App API: Postgres (recent 90 days).
- Compliance/legal review: S3 Athena queries against the audit prefix.
- Both are exposed via `/audit/events` with a `?source=` flag (default: postgres; `?source=archive` triggers Athena).

## Consequences

### Positive

- True immutability: even root cannot delete or modify locked objects in Compliance mode.
- Durable beyond the database — disaster recovery for audit is independent.
- Long retention (7 years) without bloating the operational DB.
- Athena queries on archived audit are powerful for retrospective investigations.

### Negative

- Two write paths means two failure modes. Reconciliation is mandatory.
- S3 Object Lock once-set cannot be undone for the bucket. We need the bucket configured correctly at create time — Terraform module gets this right or fails.
- Cost: Object Lock + Replication + KMS adds modest cost; well within portfolio budget.
- The async S3 write is a queue-based architecture; small extra surface.

### Neutral

- For GCP/Azure mirror (ADR-0011): GCS bucket lock + retention policy and Azure Blob Immutable Storage are the equivalents. Same model applies.

## Alternatives considered

### Option A — Postgres only (per spec, surface read)
- **Pros:** Simple.
- **Cons:** Not actually immutable. Fails compliance scrutiny.
- **Rejected because:** Recruiter-grade portfolio claims compliance posture.

### Option B — Append-only ledger DB (QLDB, immudb)
- **Pros:** Cryptographic verifiability built-in.
- **Cons:** AWS QLDB is being deprecated; immudb is a niche operational add. More signal than substance for our scale.
- **Rejected because:** Diminishing returns vs. complexity.

### Option C — S3 only
- **Pros:** Single write path.
- **Cons:** Application can't query recent events efficiently; every UI lookup hits Athena.
- **Rejected because:** UI latency.

## Trade-off summary

| Dimension | This (dual-write) | Postgres only | S3 only |
|---|---|---|---|
| Immutability | Strong (Object Lock) | Application-level only | Strong |
| App-query latency | Fast (Postgres) | Fast | Slow (Athena) |
| Compliance posture | SOC2/HIPAA-friendly | Insufficient | OK |
| Operational complexity | Medium | Low | Medium |

## References

- [S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [GCS bucket lock](https://cloud.google.com/storage/docs/bucket-lock)
- [Azure Blob Immutable](https://learn.microsoft.com/en-us/azure/storage/blobs/immutable-storage-overview)
