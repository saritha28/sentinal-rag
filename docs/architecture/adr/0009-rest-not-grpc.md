# ADR-0009: REST + Pydantic between services (overrides C4 L4 gRPC)

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** rpc, api, internal-comms

## Context

`Enterprise_RAG_Architecture.md` C4 Level 4 mentions "gRPC internal communication." gRPC is excellent at scale (binary framing, streaming, multiplex over HTTP/2) but adds substantial toolchain complexity:

- Two API contracts (REST for external, gRPC for internal) — drift risk.
- `protoc` + generated stubs in CI.
- Browser/dev tooling worse (curl, Postman, browser inspector all weaker for gRPC).
- Doesn't measurably move the needle below ~1k QPS.

Our cross-service traffic at portfolio scale is hundreds of QPS at best. The `KeywordSearch`, `VectorSearch`, `Reranker`, and `LLM` interfaces are all called per query — but per query, not per millisecond.

## Decision

All inter-service communication uses **REST + JSON with Pydantic v2 contracts** shared via `packages/shared/python/contracts/`. Specifically:

- The API Gateway (`apps/api`) calls `apps/retrieval-service` over HTTP/JSON.
- `apps/retrieval-service` exposes REST endpoints for `POST /retrieve`, `POST /rerank`.
- `apps/evaluation-service` exposes REST endpoints.
- Temporal activities run in-process (no RPC).
- LLM calls go through the LiteLLM gateway (ADR-0005), which handles its own HTTPS to providers.

Cross-service Pydantic models live in `packages/shared/python/contracts/` and are imported by both caller and callee:

```python
# packages/shared/python/contracts/retrieval.py
class RetrieveRequest(BaseModel):
    query: str
    auth_context: AuthContext
    collection_ids: list[UUID]
    top_k_bm25: int = 20
    top_k_vector: int = 20

class RetrieveResponse(BaseModel):
    candidates: list[CandidateChunk]
```

OpenAPI specs are auto-generated from FastAPI; published into `docs/api/openapi/` per service.

## Consequences

### Positive

- One toolchain (FastAPI + httpx + Pydantic).
- Easy to debug — `curl` works. Human-readable wire format.
- TypeScript SDK can be auto-generated from OpenAPI specs (e.g. `openapi-typescript`).
- Lower cognitive load for contributors.

### Negative

- We forfeit gRPC's bidirectional streaming. We don't need it; if we ever do, we add server-sent events for the one streaming path (live query trace).
- ~1–2ms overhead per call vs. gRPC. Negligible at our scale.
- No native typed RPC stubs — we get types via Pydantic contracts shared in the package, which is functionally equivalent.

### Neutral

- We retain freedom to migrate specific hot paths to gRPC later if benchmarks demand. Unlikely.

## Alternatives considered

### Option A — gRPC (per C4)
- **Pros:** Faster, typed stubs, streaming.
- **Cons:** Above. Doesn't earn complexity at this scale.
- **Rejected because:** Scale-mismatch.

### Option B — Connect (Buf) protocol
- **Pros:** Best of both — gRPC and REST over the same handler.
- **Cons:** Another tool to learn; less Python ecosystem traction.
- **Rejected because:** Marginal gains, real cost.

## Trade-off summary

| Dimension | REST | gRPC | Connect |
|---|---|---|---|
| Toolchain count | 1 | 2 (REST external + gRPC internal) | 1 |
| Wire efficiency | JSON | Protobuf (~30% smaller) | Both |
| Streaming | SSE / WebSocket | Native bidi | Native |
| Typing | Pydantic shared models | Generated stubs | Generated stubs |
| Debug ergonomics | Excellent | Mediocre | Good |

## Notes on the design docs

**Overrides** `Enterprise_RAG_Architecture.md` C4 L4 deployment view (the gRPC mention). All internal service-to-service traffic is REST.

## References

- [FastAPI + Pydantic v2](https://fastapi.tiangolo.com/)
