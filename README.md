# SentinelRAG

> Multi-tenant, RBAC-aware, evaluation-driven enterprise RAG platform.

**Status:** under active development. See [`docs/architecture/PHASE_PLAN.md`](docs/architecture/PHASE_PLAN.md) for the live build status.

This README is intentionally a placeholder during construction. It will be replaced with the public-facing portfolio README in Phase 9.

## Where to start (for engineers and reviewers)

- **What is this?** [`Enterprise_RAG_PRD.md`](Enterprise_RAG_PRD.md) — full product requirements.
- **How is it built?** [`Enterprise_RAG_Architecture.md`](Enterprise_RAG_Architecture.md) — C4 diagrams (L1–L4) and system design.
- **Why is it built that way?** [`docs/architecture/adr/README.md`](docs/architecture/adr/README.md) — accepted architectural decisions.
- **What's next?** [`docs/architecture/PHASE_PLAN.md`](docs/architecture/PHASE_PLAN.md) — live phase plan.
- **Working with Claude Code in this repo?** [`CLAUDE.md`](CLAUDE.md) — locked stack + override notes.

## Quick start (after Phase 0 completes)

```bash
# Install uv (one time): https://docs.astral.sh/uv/
uv sync                 # install Python deps for the whole workspace
make up                 # bring up local stack (Postgres, Redis, MinIO, Keycloak, Temporal, Ollama, observability)
make seed               # populate demo tenant + sample documents (after Phase 2)
make api                # run apps/api locally with hot reload
```

## License

MIT — see [LICENSE](LICENSE).
