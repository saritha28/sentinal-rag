Below is a **complete C4 architecture package (Levels 1–4) + detailed system design** for **SentinelRAG**. The XML is compatible with **draw.io / diagrams.net** (import via *File → Import From → Device*).

---

# 🧭 C4 LEVEL 1 — SYSTEM CONTEXT

## Purpose

Defines how SentinelRAG interacts with external actors and systems.

## Key Elements

* Users (AI Engineers, Enterprise Users)
* External Identity Provider (OAuth2)
* Cloud Storage / Data Sources
* LLM Providers (OpenAI / Anthropic)
* Monitoring Systems

---

### 📥 draw.io XML (Level 1)

```xml
<mxfile host="app.diagrams.net">
  <diagram name="C4 Level 1 - System Context">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>

        <!-- Users -->
        <mxCell id="user" value="Enterprise Users / AI Engineers" style="shape=actor;" vertex="1" parent="1">
          <mxGeometry x="50" y="200" width="120" height="60" as="geometry"/>
        </mxCell>

        <!-- SentinelRAG -->
        <mxCell id="system" value="SentinelRAG Platform" style="shape=rectangle;fillColor=#dae8fc;" vertex="1" parent="1">
          <mxGeometry x="300" y="150" width="250" height="120" as="geometry"/>
        </mxCell>

        <!-- External Systems -->
        <mxCell id="idp" value="Identity Provider (OAuth2)" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="650" y="50" width="200" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="llm" value="LLM Providers (OpenAI / Anthropic)" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="650" y="150" width="200" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="storage" value="Enterprise Data Sources (S3, DBs)" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="650" y="250" width="200" height="60" as="geometry"/>
        </mxCell>

        <!-- Edges -->
        <mxCell edge="1" parent="1" source="user" target="system"/>
        <mxCell edge="1" parent="1" source="system" target="idp"/>
        <mxCell edge="1" parent="1" source="system" target="llm"/>
        <mxCell edge="1" parent="1" source="system" target="storage"/>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

# 🏗️ C4 LEVEL 2 — CONTAINER DIAGRAM

## Core Containers

| Container         | Responsibility             |
| ----------------- | -------------------------- |
| API Gateway       | Entry point, routing, auth |
| Auth Service      | RBAC + token validation    |
| Ingestion Service | Document processing        |
| Retrieval Service | Hybrid search              |
| RAG Orchestrator  | Query pipeline             |
| Evaluation Engine | Metrics + scoring          |
| Prompt Registry   | Version control            |
| Audit Service     | Logging + compliance       |
| Cost Service      | Token/cost tracking        |
| Frontend          | Dashboard                  |

---

### 📥 draw.io XML (Level 2)

```xml
<mxfile host="app.diagrams.net">
  <diagram name="C4 Level 2 - Containers">
    <mxGraphModel dx="1200" dy="800">
      <root>
        <mxCell id="0"/><mxCell id="1" parent="0"/>

        <mxCell id="api" value="API Gateway" style="shape=rectangle;fillColor=#d5e8d4;" vertex="1" parent="1">
          <mxGeometry x="100" y="200" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="auth" value="Auth Service (RBAC)" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="250" y="100" width="150" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="rag" value="RAG Orchestrator" style="shape=rectangle;fillColor=#fff2cc;" vertex="1" parent="1">
          <mxGeometry x="250" y="250" width="150" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="retrieval" value="Retrieval Service" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="450" y="250" width="150" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="eval" value="Evaluation Engine" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="650" y="250" width="150" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="audit" value="Audit Service" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="450" y="350" width="150" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="cost" value="Cost Service" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="650" y="350" width="150" height="60" as="geometry"/>
        </mxCell>

        <!-- Edges -->
        <mxCell edge="1" parent="1" source="api" target="rag"/>
        <mxCell edge="1" parent="1" source="rag" target="retrieval"/>
        <mxCell edge="1" parent="1" source="rag" target="eval"/>
        <mxCell edge="1" parent="1" source="rag" target="audit"/>
        <mxCell edge="1" parent="1" source="rag" target="cost"/>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

# 🔬 C4 LEVEL 3 — COMPONENT DIAGRAM (RAG CORE)

## Pipeline Breakdown

1. Query Intake
2. Auth Context Injection
3. Query Rewriting
4. Hybrid Retrieval
5. Reranking
6. Context Assembly
7. LLM Generation
8. Hallucination Detection
9. Response Packaging

---

### 📥 draw.io XML (Level 3)

```xml
<mxfile host="app.diagrams.net">
  <diagram name="C4 Level 3 - RAG Components">
    <mxGraphModel dx="1200" dy="800">
      <root>
        <mxCell id="0"/><mxCell id="1" parent="0"/>

        <mxCell id="q" value="Query Handler" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="50" y="200" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="rewrite" value="Query Rewriter" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="200" y="200" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="bm25" value="BM25 Search" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="350" y="150" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="vector" value="Vector Search" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="350" y="250" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="rerank" value="Reranker" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="500" y="200" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="llm" value="LLM Generator" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="650" y="200" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="hallucination" value="Hallucination Detector" style="shape=rectangle;" vertex="1" parent="1">
          <mxGeometry x="800" y="200" width="150" height="60" as="geometry"/>
        </mxCell>

        <!-- Edges -->
        <mxCell edge="1" parent="1" source="q" target="rewrite"/>
        <mxCell edge="1" parent="1" source="rewrite" target="bm25"/>
        <mxCell edge="1" parent="1" source="rewrite" target="vector"/>
        <mxCell edge="1" parent="1" source="bm25" target="rerank"/>
        <mxCell edge="1" parent="1" source="vector" target="rerank"/>
        <mxCell edge="1" parent="1" source="rerank" target="llm"/>
        <mxCell edge="1" parent="1" source="llm" target="hallucination"/>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

# ⚙️ C4 LEVEL 4 — CODE/DEPLOYMENT VIEW

## Microservices

* FastAPI services
* gRPC internal communication
* Redis cache
* PostgreSQL (pgvector)
* OpenSearch
* Kafka (optional)

---

### 📥 draw.io XML (Level 4)

```xml
<mxfile host="app.diagrams.net">
  <diagram name="C4 Level 4 - Deployment">
    <mxGraphModel dx="1200" dy="800">
      <root>
        <mxCell id="0"/><mxCell id="1" parent="0"/>

        <mxCell id="k8s" value="Kubernetes Cluster (EKS/GKE)" style="shape=rectangle;fillColor=#e1d5e7;" vertex="1" parent="1">
          <mxGeometry x="100" y="100" width="700" height="400" as="geometry"/>
        </mxCell>

        <mxCell id="api" value="API Pod" style="shape=rectangle;" vertex="1" parent="k8s">
          <mxGeometry x="150" y="150" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="rag" value="RAG Pod" style="shape=rectangle;" vertex="1" parent="k8s">
          <mxGeometry x="300" y="150" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="db" value="Postgres + pgvector" style="shape=cylinder;" vertex="1" parent="1">
          <mxGeometry x="850" y="150" width="120" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="search" value="OpenSearch" style="shape=cylinder;" vertex="1" parent="1">
          <mxGeometry x="850" y="250" width="120" height="60" as="geometry"/>
        </mxCell>

        <!-- Edges -->
        <mxCell edge="1" parent="1" source="api" target="rag"/>
        <mxCell edge="1" parent="1" source="rag" target="db"/>
        <mxCell edge="1" parent="1" source="rag" target="search"/>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

# 🧠 DETAILED SYSTEM DESIGN (WHAT INTERVIEWERS CARE ABOUT)

## 1. End-to-End Query Flow

```text
User Query
→ Auth (JWT + RBAC context)
→ Query Rewrite (optional)
→ Hybrid Retrieval (BM25 + Vector)
→ Reranking
→ Context Assembly
→ LLM Generation
→ Hallucination Check
→ Evaluation Logging
→ Response + Citations
```

---

## 2. Key Design Decisions

### Why Hybrid Search?

* BM25 → keyword precision
* Vector → semantic recall
* Reranker → final relevance

👉 This mirrors real-world systems (Google/Amazon search stacks)

---

### Why RBAC at Retrieval Layer?

* Prevents leakage BEFORE context reaches LLM
* Safer than filtering after generation

---

### Why Evaluation Pipeline Inline?

* Enables continuous improvement
* Required for production AI systems

---

## 3. Scalability Strategy

* Stateless services → horizontal scaling
* Retrieval layer optimized separately
* Async ingestion pipelines
* Caching:

  * embedding cache
  * response cache

---

## 4. Failure Handling

| Failure                 | Strategy         |
| ----------------------- | ---------------- |
| LLM timeout             | fallback model   |
| low retrieval quality   | expand search    |
| hallucination risk high | abstain response |
| cost spike              | downgrade model  |

---

## 5. Security Architecture

* OAuth2 + JWT
* Row-level security (Postgres)
* Encryption (TLS + KMS)
* Audit logs immutable

---

## 6. Observability

* Distributed tracing (OpenTelemetry)
* Metrics:

  * latency per stage
  * token usage
  * retrieval accuracy

---

## 7. Tradeoffs

| Choice               | Tradeoff             |
| -------------------- | -------------------- |
| pgvector vs Pinecone | cost vs scalability  |
| OpenSearch           | operational overhead |
| LLM-as-judge         | cost vs quality      |
| reranker             | latency vs accuracy  |

---

# 🚀 What You Now Have (Portfolio Impact)

This package demonstrates:

* System design depth
* Distributed architecture
* Production AI engineering
* Security + compliance awareness
* Evaluation-first thinking

👉 This is exactly what differentiates candidates in FAANG interviews.

---
