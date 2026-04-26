# ADR-0001: Monorepo with uv workspaces

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** repo, tooling, python

## Context

SentinelRAG ships ~5 Python services (api, retrieval-service, ingestion-service, evaluation-service, temporal-worker), 1 Next.js frontend, 2 SDKs (Python + TypeScript), and shared contract packages. Choices:

1. **Polyrepo** — one repo per service.
2. **Monorepo, one big package** — every service in one `pyproject.toml`.
3. **Monorepo, workspace** — root manifest references per-service manifests with shared lockfile and shared internal packages.

The PRD/Folder Structure already specify a monorepo layout, so the decision narrows to *how* the monorepo is composed.

## Decision

Single Git monorepo at the project root, organized as a **uv workspace** for Python and a **pnpm workspace** for TypeScript. Each service has its own `pyproject.toml` (or `package.json`) declaring its own deps. Internal shared packages (`packages/shared/python`, `packages/sentinelrag-sdk`) are workspace members and consumed via `[tool.uv.sources]` workspace references. A single `uv.lock` at the root pins everything.

## Consequences

### Positive

- One PR can change a service AND the contract that another service consumes — atomic refactors.
- Shared lockfile prevents version drift between services.
- `uv sync` once at the root sets up all venvs.
- CI can detect which services changed (path filters) and only build/test those.

### Negative

- All services share the Python version floor (we picked 3.12). A future service that needs 3.13-only features forces a global bump.
- Repo grows large; clones get slower over time.
- Requires discipline on dependency boundaries (services must import from `packages/shared/`, not from each other).

### Neutral

- Onboarding requires `uv` (not pip) — small learning curve.

## Alternatives considered

### Option A — Polyrepo
- **Pros:** Clean blast radius per repo; independent release cadence; smaller clones.
- **Cons:** Cross-cutting changes require N PRs; shared types drift; dev tooling gets duplicated; harder to demonstrate "this is one platform" in a portfolio.
- **Rejected because:** Portfolio narrative + cross-service refactors during build favor monorepo. Independent release cadence isn't a real constraint at our scale.

### Option B — Single big package (no workspace)
- **Pros:** Simplest mental model.
- **Cons:** Every service deploys with every dep; image sizes balloon; `pip install` on the API pod pulls in `torch` because the reranker needs it. Unacceptable.
- **Rejected because:** Image bloat and circular import risk.

## Trade-off summary

| Dimension | uv workspace | Polyrepo |
|---|---|---|
| Setup time | Low | Medium (per repo) |
| Cross-service refactor cost | Low | High (N PRs) |
| Image size | Per-service deps | Per-service deps |
| Onboarding ceremony | One clone | N clones |
| Recruiter signal | Modern (uv is current standard) | Conventional |

## Notes on the design docs

`Enterprise_RAG_Folder_Structure.md` already specifies a monorepo. This ADR commits to **uv workspace** specifically (not `poetry`, not `pip-tools`, not `rye`).

## References

- [uv workspaces](https://docs.astral.sh/uv/concepts/workspaces/)
- [pnpm workspaces](https://pnpm.io/workspaces)
