# SentinelRAG — Phase Plan

This is the live phase plan for the SentinelRAG build. Update this file when a phase completes or when scope changes — future Claude instances read this at the start of every session to know where we are.

## Status legend

- 🟢 Complete
- 🟡 In progress
- ⚪ Not started

## Current phase

**Phase 1 — Core data plane + tenancy.** Complete (pending live verification: `uv sync`, `make db-upgrade`, `pytest -m integration`). Phase 2 (ingestion pipeline) is next.

## Phase ledger

### Phase 0 — Foundations 🟢
**Goal:** repo scaffolding, tooling, local dev stack, CI bones, ADR catalog.
- 🟢 Update `CLAUDE.md` with locked stack and override notes.
- 🟢 Write ADR catalog (0000 template + 0001–0019).
- 🟢 Bootstrap monorepo skeleton (directories + root config).
- 🟢 `docker-compose.yml` for full local dev stack.
- 🟢 GitHub Actions CI for lint + typecheck.
- 🟢 Stub `apps/api` with `/health` + OTel + structlog.
- 🟢 `Makefile` with `make up`, `make api`, `make lint`, `make fmt`.
- 🟢 Pre-commit hooks.

**Verification deferred to next session (requires running tools the user has):**
- Run `uv sync` and confirm the workspace resolves.
- Run `make up` and confirm all containers come up healthy.
- Run `make api` and `curl localhost:8000/api/v1/health`.
- Run `make test` and confirm the health unit test passes.
- `git init`, push to GitHub, confirm CI runs green on the first PR.

**Done when:** the verification steps above pass on the user's machine.

### Phase 1 — Core data plane + tenancy 🟢
**Goal:** schema, RBAC, RLS, tenant context.
- 🟢 Alembic setup + 10 hand-written migrations covering the full schema (HNSW index, no raw_text column, partitioned audit/usage, tsvector+GIN on chunks, RLS policies on every tenant-owned table).
- 🟢 SQLAlchemy 2.0 async models + Pydantic v2 schemas for tenancy + RBAC entities.
- 🟢 Repository layer for tenants/users/roles/permissions.
- 🟢 DB session factory with contextvar-driven `SET LOCAL app.current_tenant_id`; admin (RLS-bypass) factory for tenant-creation flows.
- 🟢 Keycloak JWKS-cached JWT verifier in `packages/shared/python/sentinelrag_shared/auth/`.
- 🟢 AuthContext + `require_auth` / `require_permission` FastAPI dependencies.
- 🟢 RequestContextMiddleware (request_id) + error-handler middleware (DomainError → JSON envelope).
- 🟢 `/tenants`, `/tenants/me`, `/users`, `/users/me`, `/users/{id}/roles`, `/roles`, `/permissions` endpoints.
- 🟢 RLS integration tests proving cross-tenant reads/writes are blocked.
- 🟢 JWT verifier unit tests (valid, expired, wrong audience, missing tenant_id, tampered signature).

**Verification deferred to next session (requires user's machine):**
- `uv sync` resolves the workspace.
- `make up && make db-upgrade` applies all 10 migrations cleanly.
- `pytest -m integration` passes (RLS proven against real Postgres).
- `pytest -m unit` passes (JWT verifier with stubbed JWKS).

**Done when:** the verification steps above pass.

### Phase 2 — Ingestion pipeline ⚪
**Goal:** docs in → chunks + embeddings out.
- `ObjectStorage` interface (S3 / GCS / MinIO).
- `unstructured` parser; three chunking strategies; `Embedder` interface (Ollama default + OpenAI adapter via LiteLLM).
- Temporal `IngestionWorkflow` with activities `download → parse → chunk → embed → index → finalize`.
- `/documents` upload, `/ingestion/jobs` CRUD.
- Idempotency via content hashes.

**Done when:** uploading a PDF produces searchable chunks visible by tenant.

### Phase 3 — Retrieval + RAG orchestrator ⚪
**Goal:** end-to-end query with grounded citations.
- `KeywordSearch` (Postgres FTS) + `VectorSearch` (pgvector HNSW) + `Reranker` (bge).
- Query-time RBAC injection (the headline feature).
- `RagOrchestrator` calling: query rewrite → hybrid retrieve → rerank → context assemble → LLM (LiteLLM) → hallucination detect → response.
- `/query`, `/query/{id}/trace` endpoints.
- Persistence into `query_sessions`, `retrieval_results`, `generated_answers`, `answer_citations`.

**Done when:** end-to-end query returns grounded, cited answer; trace shows every stage.

### Phase 4 — Prompt registry + evaluation ⚪
**Goal:** versioned prompts + ragas-driven evaluation.
- Prompt template + version CRUD; flag-driven version selection (Unleash).
- `EvaluationRunWorkflow` with ragas + custom evaluators.
- Golden dataset CRUD; per-run reporting.
- `/prompts`, `/eval/datasets`, `/eval/cases`, `/eval/runs` endpoints.

**Done when:** running an eval produces ragas + citation-accuracy scores; prompt version routing toggles via Unleash without redeploy.

### Phase 5 — Frontend ⚪
**Goal:** Next.js dashboard against the live API.
- Routes: dashboard, collections, documents, query playground, evaluations, prompts, audit, usage, settings.
- NextAuth.js bound to Keycloak.
- TanStack Query against generated TypeScript SDK.
- Streaming query trace viewer.

**Done when:** all major API features are usable through the UI.

### Phase 6 — Observability + cost + audit hardening ⚪
**Goal:** prod-grade telemetry and audit immutability.
- OTel collector + Tempo (traces) + Prometheus + Grafana dashboards (latency-per-stage, hallucination, cost).
- Audit dual-write to Postgres + S3 Object Lock; reconciliation job.
- Cost service: per-tenant budgets, soft/hard caps, model downgrade on hot signal.
- SLO panels.

**Done when:** Grafana shows live RAG metrics; budget alert demonstrably fires.

### Phase 7 — AWS production deployment ⚪
**Goal:** live `dev.<domain>` on AWS.
- Terraform: VPC, EKS, RDS Postgres, ElastiCache, S3, Secrets Manager, ACM, IAM/IRSA.
- Helm chart consolidating all manifests.
- ArgoCD installed; one Application per env (dev only initially).
- External Secrets Operator + AWS Secrets Manager.
- HPA, PDB, NetworkPolicies per service.

**Done when:** push to main → ArgoCD deploys → live URL serves a query.

### Phase 8 — Multi-cloud + scale features ⚪
**Goal:** GCP mirror deployment + OpenSearch reintroduction.
- GCP Terraform mirror; same Helm chart.
- OpenSearch as second `KeywordSearch` adapter; A/B against Postgres FTS.
- k6 load tests; chaos tests via litmus or chaos-mesh.
- Trivy/bandit/tfsec security scans in CI.
- Disaster recovery runbook.

**Done when:** GCP deploy verified once; OpenSearch A/B report committed; resilience evidence documented.

### Phase 9 — Portfolio polish ⚪
**Goal:** readable artifacts a senior engineer can absorb in 30 minutes.
- Root README with architecture diagram, quick-start, live demo URL.
- C4 diagrams in `docs/architecture/c4/` (rendered PNGs).
- ADR index complete and current.
- Cost report (1 month synthetic traffic).
- Eval report: before/after hybrid retrieval; before/after rerank; before/after prompt v2.
- 5-minute demo video.

**Done when:** the repo's README sells the project on its own.

## Cross-phase rules

- Every architectural decision lands as an ADR before code.
- Every cross-cutting library/tool change lands as a new ADR (don't edit accepted ADRs — supersede).
- No phase is "done" until its tests pass in CI on a clean checkout.
- After each phase, this file is updated with what shipped + what was deferred.
- Each phase's deliverables include an entry in `docs/operations/runbooks/` if the phase added a new operational concern.
