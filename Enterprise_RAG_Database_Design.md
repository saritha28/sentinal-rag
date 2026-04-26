# SentinelRAG — Production Database Schema + API Contracts

## 1. Database Design Principles

**Database:** PostgreSQL
**Vector support:** `pgvector`
**Tenant isolation:** `tenant_id` on every tenant-owned table
**Security:** Row-level security-ready schema
**Auditability:** immutable append-only audit tables
**Evaluation-first:** every query, retrieval, generation, and score is traceable

---

# 2. Core PostgreSQL Extensions

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

---

# 3. Core Multi-Tenant Schema

## 3.1 Tenants

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    plan TEXT NOT NULL DEFAULT 'developer',
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 3.2 Users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    external_identity_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, email)
);

CREATE INDEX idx_users_tenant_id ON users(tenant_id);
```

---

## 3.3 Roles

```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    is_system_role BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, name)
);
```

---

## 3.4 Permissions

```sql
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code TEXT NOT NULL UNIQUE,
    description TEXT
);
```

Example permission codes:

```text
documents:read
documents:write
collections:admin
queries:execute
audit:read
evals:run
prompts:admin
billing:read
```

---

## 3.5 Role Permissions

```sql
CREATE TABLE role_permissions (
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
```

---

## 3.6 User Roles

```sql
CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
```

---

# 4. Knowledge Domain Schema

## 4.1 Collections

Collections are logical knowledge spaces such as HR, Engineering, Legal, Finance.

```sql
CREATE TABLE collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    visibility TEXT NOT NULL DEFAULT 'private',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, name)
);

CREATE INDEX idx_collections_tenant_id ON collections(tenant_id);
```

---

## 4.2 Collection Access Policies

```sql
CREATE TABLE collection_access_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    access_level TEXT NOT NULL CHECK (
        access_level IN ('read', 'write', 'admin')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (
        role_id IS NOT NULL OR user_id IS NOT NULL
    )
);

CREATE INDEX idx_collection_access_collection_id
ON collection_access_policies(collection_id);
```

---

# 5. Document Ingestion Schema

## 5.1 Documents

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,

    title TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (
        source_type IN ('upload', 's3', 'gcs', 'url', 'database', 'api')
    ),
    source_uri TEXT,
    mime_type TEXT,
    checksum TEXT NOT NULL,

    sensitivity_level TEXT NOT NULL DEFAULT 'internal'
        CHECK (sensitivity_level IN ('public', 'internal', 'confidential', 'restricted')),

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'indexed', 'failed', 'archived')),

    metadata JSONB NOT NULL DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_tenant_collection
ON documents(tenant_id, collection_id);

CREATE INDEX idx_documents_status
ON documents(status);
```

---

## 5.2 Document Versions

```sql
CREATE TABLE document_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    version_number INT NOT NULL,
    content_hash TEXT NOT NULL,
    raw_text TEXT,
    storage_uri TEXT,
    parser_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (document_id, version_number)
);

CREATE INDEX idx_document_versions_document_id
ON document_versions(document_id);
```

---

## 5.3 Document Chunks

```sql
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    document_version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,

    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    token_count INT,
    page_number INT,
    section_title TEXT,

    access_policy JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (document_version_id, chunk_index)
);

CREATE INDEX idx_chunks_tenant_document
ON document_chunks(tenant_id, document_id);
```

---

## 5.4 Chunk Embeddings

```sql
CREATE TABLE chunk_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,

    embedding_model TEXT NOT NULL,
    embedding vector(1536) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (chunk_id, embedding_model)
);

CREATE INDEX idx_chunk_embeddings_tenant
ON chunk_embeddings(tenant_id);

CREATE INDEX idx_chunk_embeddings_vector
ON chunk_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

---

# 6. Ingestion Job Schema

```sql
CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,

    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),

    input_source JSONB NOT NULL,
    chunking_strategy TEXT NOT NULL DEFAULT 'semantic',
    embedding_model TEXT NOT NULL,

    documents_total INT DEFAULT 0,
    documents_processed INT DEFAULT 0,
    chunks_created INT DEFAULT 0,

    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ingestion_jobs_tenant_status
ON ingestion_jobs(tenant_id, status);
```

---

# 7. Prompt Registry Schema

## 7.1 Prompt Templates

```sql
CREATE TABLE prompt_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    description TEXT,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, name)
);
```

---

## 7.2 Prompt Versions

```sql
CREATE TABLE prompt_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    prompt_template_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,

    version_number INT NOT NULL,
    system_prompt TEXT NOT NULL,
    user_prompt_template TEXT NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    model_config JSONB NOT NULL DEFAULT '{}',

    is_default BOOLEAN NOT NULL DEFAULT false,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (prompt_template_id, version_number)
);
```

---

# 8. Query, Retrieval, and Generation Trace Schema

## 8.1 Query Sessions

```sql
CREATE TABLE query_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),

    query_text TEXT NOT NULL,
    normalized_query TEXT,
    collection_ids UUID[] NOT NULL,

    status TEXT NOT NULL DEFAULT 'running',
    latency_ms INT,
    total_cost_usd NUMERIC(12,6) DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_query_sessions_tenant_user
ON query_sessions(tenant_id, user_id);

CREATE INDEX idx_query_sessions_created_at
ON query_sessions(created_at);
```

---

## 8.2 Retrieval Results

```sql
CREATE TABLE retrieval_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    query_session_id UUID NOT NULL REFERENCES query_sessions(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES document_chunks(id),

    retrieval_stage TEXT NOT NULL CHECK (
        retrieval_stage IN ('bm25', 'vector', 'hybrid_merge', 'rerank')
    ),

    rank INT NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_retrieval_results_session
ON retrieval_results(query_session_id);
```

---

## 8.3 Generated Answers

```sql
CREATE TABLE generated_answers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    query_session_id UUID NOT NULL REFERENCES query_sessions(id) ON DELETE CASCADE,

    answer_text TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version_id UUID REFERENCES prompt_versions(id),

    input_tokens INT,
    output_tokens INT,
    cost_usd NUMERIC(12,6),

    confidence_score DOUBLE PRECISION,
    hallucination_risk_score DOUBLE PRECISION,
    grounding_score DOUBLE PRECISION,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_generated_answers_session
ON generated_answers(query_session_id);
```

---

## 8.4 Answer Citations

```sql
CREATE TABLE answer_citations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    generated_answer_id UUID NOT NULL REFERENCES generated_answers(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES document_chunks(id),

    citation_index INT NOT NULL,
    quoted_text TEXT,
    relevance_score DOUBLE PRECISION,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_answer_citations_answer
ON answer_citations(generated_answer_id);
```

---

# 9. Evaluation Schema

## 9.1 Evaluation Datasets

```sql
CREATE TABLE evaluation_datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    description TEXT,
    dataset_type TEXT NOT NULL DEFAULT 'golden',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, name)
);
```

---

## 9.2 Evaluation Cases

```sql
CREATE TABLE evaluation_cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES evaluation_datasets(id) ON DELETE CASCADE,

    input_query TEXT NOT NULL,
    expected_answer TEXT,
    expected_citation_chunk_ids UUID[],
    grading_rubric JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 9.3 Evaluation Runs

```sql
CREATE TABLE evaluation_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES evaluation_datasets(id),

    name TEXT NOT NULL,
    model_config JSONB NOT NULL,
    retrieval_config JSONB NOT NULL,
    prompt_version_id UUID REFERENCES prompt_versions(id),

    status TEXT NOT NULL DEFAULT 'queued',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 9.4 Evaluation Scores

```sql
CREATE TABLE evaluation_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    evaluation_run_id UUID NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    evaluation_case_id UUID NOT NULL REFERENCES evaluation_cases(id) ON DELETE CASCADE,
    query_session_id UUID REFERENCES query_sessions(id),

    context_relevance_score DOUBLE PRECISION,
    faithfulness_score DOUBLE PRECISION,
    answer_correctness_score DOUBLE PRECISION,
    citation_accuracy_score DOUBLE PRECISION,
    latency_ms INT,
    cost_usd NUMERIC(12,6),

    judge_model TEXT,
    judge_reasoning TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_eval_scores_run
ON evaluation_scores(evaluation_run_id);
```

---

# 10. Audit and Billing Schema

## 10.1 Audit Events

```sql
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    actor_user_id UUID REFERENCES users(id),

    event_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    action TEXT NOT NULL,

    ip_address INET,
    user_agent TEXT,
    request_id TEXT,

    before_state JSONB,
    after_state JSONB,
    metadata JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_events_tenant_created
ON audit_events(tenant_id, created_at);

CREATE INDEX idx_audit_events_resource
ON audit_events(resource_type, resource_id);
```

---

## 10.2 Usage Records

```sql
CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    query_session_id UUID REFERENCES query_sessions(id),

    usage_type TEXT NOT NULL CHECK (
        usage_type IN ('embedding', 'completion', 'rerank', 'storage', 'evaluation')
    ),

    provider TEXT,
    model_name TEXT,
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    unit_cost_usd NUMERIC(12,8),
    total_cost_usd NUMERIC(12,6),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_usage_records_tenant_created
ON usage_records(tenant_id, created_at);
```

---

# 11. Recommended Partitioning Strategy

Use monthly partitioning for high-volume tables:

```sql
-- Recommended partition candidates:
-- audit_events
-- query_sessions
-- retrieval_results
-- usage_records
-- evaluation_scores
```

Example:

```sql
CREATE TABLE audit_events_2026_04
PARTITION OF audit_events
FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
```

---

# 12. Row-Level Security Example

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_documents
ON documents
USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

At request start:

```sql
SET app.current_tenant_id = '<tenant_uuid>';
```

---

# 13. API Contract Overview

Base URL:

```text
/api/v1
```

Authentication:

```http
Authorization: Bearer <jwt>
X-Tenant-ID: <tenant_id>
```

---

# 14. API Contracts

## 14.1 Health

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "prod"
}
```

---

# 15. Tenant APIs

## Create Tenant

```http
POST /tenants
```

Request:

```json
{
  "name": "Acme Corporation",
  "slug": "acme",
  "plan": "enterprise"
}
```

Response:

```json
{
  "id": "tenant_uuid",
  "name": "Acme Corporation",
  "slug": "acme",
  "plan": "enterprise",
  "status": "active"
}
```

---

# 16. Collection APIs

## Create Collection

```http
POST /collections
```

Request:

```json
{
  "name": "Engineering Knowledge Base",
  "description": "Architecture docs, runbooks, RFCs",
  "visibility": "private"
}
```

Response:

```json
{
  "id": "collection_uuid",
  "name": "Engineering Knowledge Base",
  "visibility": "private",
  "created_at": "2026-04-26T10:00:00Z"
}
```

---

## List Collections

```http
GET /collections
```

Response:

```json
{
  "items": [
    {
      "id": "collection_uuid",
      "name": "Engineering Knowledge Base",
      "visibility": "private",
      "document_count": 1200
    }
  ]
}
```

---

# 17. Document APIs

## Upload Document

```http
POST /documents
Content-Type: multipart/form-data
```

Form fields:

```text
collection_id
file
sensitivity_level
metadata
```

Response:

```json
{
  "document_id": "document_uuid",
  "status": "pending",
  "ingestion_job_id": "job_uuid"
}
```

---

## Get Document

```http
GET /documents/{document_id}
```

Response:

```json
{
  "id": "document_uuid",
  "title": "Platform Architecture.pdf",
  "collection_id": "collection_uuid",
  "status": "indexed",
  "sensitivity_level": "confidential",
  "created_at": "2026-04-26T10:00:00Z"
}
```

---

## Delete Document

```http
DELETE /documents/{document_id}
```

Response:

```json
{
  "deleted": true
}
```

---

# 18. Ingestion APIs

## Create Ingestion Job

```http
POST /ingestion/jobs
```

Request:

```json
{
  "collection_id": "collection_uuid",
  "source": {
    "type": "s3",
    "uri": "s3://company-docs/engineering/"
  },
  "chunking_strategy": "semantic",
  "embedding_model": "text-embedding-3-small"
}
```

Response:

```json
{
  "job_id": "job_uuid",
  "status": "queued"
}
```

---

## Get Ingestion Job

```http
GET /ingestion/jobs/{job_id}
```

Response:

```json
{
  "job_id": "job_uuid",
  "status": "running",
  "documents_total": 500,
  "documents_processed": 240,
  "chunks_created": 18700
}
```

---

# 19. Query APIs

## Execute RAG Query

```http
POST /query
```

Request:

```json
{
  "query": "What is our rollback process for failed Kubernetes deployments?",
  "collection_ids": ["collection_uuid"],
  "retrieval": {
    "mode": "hybrid",
    "top_k_bm25": 20,
    "top_k_vector": 20,
    "top_k_rerank": 8
  },
  "generation": {
    "model": "gpt-4.1-mini",
    "temperature": 0.1,
    "max_tokens": 800
  },
  "options": {
    "include_citations": true,
    "include_debug_trace": false,
    "abstain_if_unsupported": true
  }
}
```

Response:

```json
{
  "query_session_id": "query_session_uuid",
  "answer": "The rollback process requires validating the failed deployment, checking recent release notes, running helm rollback, and verifying service health after rollback.",
  "confidence_score": 0.87,
  "hallucination_risk_score": 0.08,
  "grounding_score": 0.91,
  "citations": [
    {
      "citation_id": "citation_uuid",
      "document_id": "document_uuid",
      "document_title": "Kubernetes Deployment Runbook",
      "chunk_id": "chunk_uuid",
      "page_number": 4,
      "quoted_text": "Use helm rollback <release> <revision> after validating failed rollout status.",
      "relevance_score": 0.94
    }
  ],
  "usage": {
    "input_tokens": 2200,
    "output_tokens": 420,
    "cost_usd": 0.0185,
    "latency_ms": 1420
  }
}
```

---

## Get Query Trace

```http
GET /query/{query_session_id}/trace
```

Response:

```json
{
  "query_session_id": "query_session_uuid",
  "query": "What is our rollback process?",
  "retrieval_results": [
    {
      "stage": "bm25",
      "chunk_id": "chunk_uuid",
      "rank": 1,
      "score": 14.2
    },
    {
      "stage": "rerank",
      "chunk_id": "chunk_uuid",
      "rank": 1,
      "score": 0.94
    }
  ],
  "generation": {
    "model": "gpt-4.1-mini",
    "prompt_version_id": "prompt_version_uuid",
    "input_tokens": 2200,
    "output_tokens": 420
  }
}
```

---

# 20. Prompt Registry APIs

## Create Prompt Template

```http
POST /prompts
```

Request:

```json
{
  "name": "default_enterprise_rag_answer",
  "description": "Default grounded answer prompt",
  "task_type": "rag_answer_generation"
}
```

Response:

```json
{
  "prompt_template_id": "prompt_template_uuid"
}
```

---

## Create Prompt Version

```http
POST /prompts/{prompt_template_id}/versions
```

Request:

```json
{
  "system_prompt": "You are an enterprise assistant. Answer only from provided context. If unsupported, say you do not have enough information.",
  "user_prompt_template": "Question: {{query}}\n\nContext:\n{{context}}\n\nAnswer with citations.",
  "parameters": {
    "requires_citations": true,
    "abstain_policy": "strict"
  },
  "model_config": {
    "model": "gpt-4.1-mini",
    "temperature": 0.1
  }
}
```

Response:

```json
{
  "prompt_version_id": "prompt_version_uuid",
  "version_number": 3
}
```

---

# 21. Evaluation APIs

## Create Evaluation Dataset

```http
POST /eval/datasets
```

Request:

```json
{
  "name": "Engineering Runbook Golden Set",
  "description": "Golden test set for engineering operations questions"
}
```

Response:

```json
{
  "dataset_id": "dataset_uuid"
}
```

---

## Add Evaluation Case

```http
POST /eval/datasets/{dataset_id}/cases
```

Request:

```json
{
  "input_query": "How do we rollback a failed Kubernetes deployment?",
  "expected_answer": "Use helm rollback after validating rollout failure and checking revision history.",
  "expected_citation_chunk_ids": ["chunk_uuid"],
  "grading_rubric": {
    "must_include": [
      "validate rollout failure",
      "helm rollback",
      "post-rollback health check"
    ],
    "must_not_include": [
      "delete production namespace"
    ]
  }
}
```

Response:

```json
{
  "case_id": "evaluation_case_uuid"
}
```

---

## Run Evaluation

```http
POST /eval/runs
```

Request:

```json
{
  "dataset_id": "dataset_uuid",
  "name": "Hybrid Search v2 + Prompt v3 Evaluation",
  "prompt_version_id": "prompt_version_uuid",
  "retrieval_config": {
    "mode": "hybrid",
    "top_k_bm25": 20,
    "top_k_vector": 20,
    "top_k_rerank": 8
  },
  "model_config": {
    "model": "gpt-4.1-mini",
    "temperature": 0.1
  }
}
```

Response:

```json
{
  "evaluation_run_id": "eval_run_uuid",
  "status": "queued"
}
```

---

## Get Evaluation Results

```http
GET /eval/runs/{evaluation_run_id}
```

Response:

```json
{
  "evaluation_run_id": "eval_run_uuid",
  "status": "completed",
  "summary": {
    "context_relevance_avg": 0.88,
    "faithfulness_avg": 0.92,
    "answer_correctness_avg": 0.84,
    "citation_accuracy_avg": 0.9,
    "average_latency_ms": 1510,
    "total_cost_usd": 2.84
  }
}
```

---

# 22. Audit APIs

## List Audit Events

```http
GET /audit/events?resource_type=document&limit=50
```

Response:

```json
{
  "items": [
    {
      "id": "audit_event_uuid",
      "event_type": "document.accessed",
      "resource_type": "document",
      "resource_id": "document_uuid",
      "action": "read",
      "actor_user_id": "user_uuid",
      "created_at": "2026-04-26T10:00:00Z"
    }
  ]
}
```

---

# 23. Usage and Billing APIs

## Tenant Usage Summary

```http
GET /usage/summary?from=2026-04-01&to=2026-04-30
```

Response:

```json
{
  "tenant_id": "tenant_uuid",
  "period": {
    "from": "2026-04-01",
    "to": "2026-04-30"
  },
  "totals": {
    "queries": 18420,
    "input_tokens": 18200000,
    "output_tokens": 4600000,
    "embedding_tokens": 7400000,
    "total_cost_usd": 348.77
  },
  "by_model": [
    {
      "model": "gpt-4.1-mini",
      "cost_usd": 220.14
    }
  ]
}
```

---

# 24. Error Response Standard

```json
{
  "error": {
    "code": "RBAC_DENIED",
    "message": "User does not have access to this collection.",
    "request_id": "req_abc123",
    "details": {}
  }
}
```

Common error codes:

```text
AUTH_REQUIRED
RBAC_DENIED
TENANT_NOT_FOUND
DOCUMENT_NOT_FOUND
INGESTION_FAILED
RETRIEVAL_FAILED
GENERATION_FAILED
EVALUATION_FAILED
RATE_LIMIT_EXCEEDED
BUDGET_EXCEEDED
```

---

# 25. FastAPI Router Structure

```text
app/
  api/
    routes/
      health.py
      tenants.py
      users.py
      collections.py
      documents.py
      ingestion.py
      query.py
      prompts.py
      evaluations.py
      audit.py
      usage.py
  core/
    auth.py
    config.py
    security.py
    rbac.py
  services/
    ingestion_service.py
    retrieval_service.py
    rag_orchestrator.py
    evaluation_service.py
    audit_service.py
    cost_service.py
  db/
    models.py
    session.py
    migrations/
```

---

# 26. Production API Design Signals

This API design demonstrates:

* Real multi-tenant architecture
* Query-time RBAC enforcement
* Full retrieval traceability
* Prompt/version governance
* Evaluation-first AI workflow
* Cost observability
* Audit-grade compliance posture
* Cloud-native implementation readiness


