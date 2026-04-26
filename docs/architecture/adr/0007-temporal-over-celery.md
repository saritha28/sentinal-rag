# ADR-0007: Temporal for durable workflows (overrides spec's Celery)

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** workflow, async, ingestion, evaluation

## Context

`Enterprise_RAG_Folder_Structure.md` lists `apps/api/app/workers/celery_app.py` and friends. The platform has two long-running, multi-step pipelines:

- **Ingestion:** download → parse → chunk → embed → index → mark-complete (per document; potentially thousands per job).
- **Evaluation:** for each case in a dataset → run query → score with N evaluators → aggregate → report.

Both have these characteristics:

- Multi-step, with each step potentially failing and needing retry.
- Long-running (a 1k-doc ingestion can take 30+ minutes; an eval run can take an hour).
- Need durable progress (worker crash mid-job should resume, not restart).
- Need cancellation (`/ingestion/jobs/{id}/cancel`).
- Need observability — which step is slow, where retries piled up.

Celery handles step 1 (job queue) but is bad at the rest. You can hand-roll checkpointing in `ingestion_jobs` table state, but you're rebuilding what Temporal gives you for free.

Temporal is the workflow-as-code answer: workflow definitions in Python, durable execution semantics, built-in retries, signals, queries, versioning, and a UI showing every workflow's history.

## Decision

- Replace Celery entirely with **Temporal** (self-hosted in K8s).
- Workflows live in `apps/temporal-worker/app/workflows/`. Activities (the actual work) live in `apps/temporal-worker/app/activities/`.
- Each domain gets a workflow: `IngestionWorkflow`, `EvaluationRunWorkflow`, `BatchEmbeddingWorkflow`, `RegressionTestWorkflow`.
- The API service calls `temporal_client.start_workflow(...)` and persists the resulting `workflow_id` on the relevant job row (e.g. `ingestion_jobs.workflow_id`).
- Activities are idempotent (content-hash keyed). If an activity is retried we should not duplicate chunks.
- Local dev: `temporalio/auto-setup` image in docker-compose; embedded SQLite in dev mode.
- Production: Temporal Cluster Helm chart with PostgreSQL persistence (separate DB from app data).

## Consequences

### Positive

- Durable execution semantics — worker crashes don't lose progress.
- Built-in retries with exponential backoff per activity.
- Workflow versioning — we can roll out new ingestion logic without breaking in-flight workflows.
- The Temporal Web UI is invaluable for debugging — every step, every retry, every signal visible.
- Test discipline: we use the Temporal test framework (`pytest-asyncio` + `temporalio.testing.WorkflowEnvironment`) so workflow correctness is unit-testable.

### Negative

- Temporal Cluster is non-trivial to operate: separate Postgres database, history shards, frontend/matching/history/worker services. We use the official Helm chart but it's still 4 services.
- Memory/CPU floor higher than Celery (~1GB Temporal services + Postgres for history).
- Steeper learning curve — workflow code has determinism rules (no `datetime.now()`, no `random()`, only via Temporal APIs).

### Neutral

- The folder structure changes: `apps/api/app/workers/` is removed; `apps/temporal-worker/` is added.

## Alternatives considered

### Option A — Celery (per spec)
- **Pros:** Simpler; well-known.
- **Cons:** No durable workflow semantics; we'd hand-roll job state machines in Postgres for ingestion (which is what most teams do, badly).
- **Rejected because:** The hand-rolled state machine is exactly the bug surface Temporal exists to remove. For a recruiter-grade portfolio, "I picked Temporal because pipeline durability matters" is a stronger signal than the Celery default.

### Option B — Arq or Dramatiq
- **Pros:** Native asyncio; lighter than Celery.
- **Cons:** Same fundamental problem as Celery (no durable workflow primitives).
- **Rejected because:** Same as Celery.

### Option C — Prefect / Dagster
- **Pros:** Pythonic workflow engines.
- **Cons:** Both lean toward data engineering DAGs more than service workflows; less recruiter-recognized in the AI infra space.
- **Rejected because:** Temporal has stronger industry mindshare for service-side durable execution.

### Option D — AWS Step Functions / GCP Workflows
- **Pros:** Managed service.
- **Cons:** Cloud lock-in (we run on three clouds per ADR-0011); each cloud has a different syntax.
- **Rejected because:** Multi-cloud parity is a hard requirement.

## Trade-off summary

| Dimension | Temporal | Celery |
|---|---|---|
| Setup time | 1 day | 2 hours |
| Multi-step durability | Built-in | Hand-rolled |
| Retry primitives | Built-in | Built-in |
| Versioning | Built-in | Hand-rolled |
| Operational components | 4+ pods | 2 pods |
| Recruiter signal | Strong | Standard |

## Notes on the design docs

**Overrides** `Enterprise_RAG_Folder_Structure.md` (Celery references) and `Enterprise_RAG_Deployment.md` §6.3 (the K8s Celery worker manifest). New deployments to be added: `temporal-frontend`, `temporal-history`, `temporal-matching`, `temporal-worker` (our app workers), and the Temporal database.

## References

- [Temporal Python SDK](https://docs.temporal.io/dev-guide/python)
- [Temporal Helm chart](https://github.com/temporalio/helm-charts)
