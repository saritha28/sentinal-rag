# ADR-0017: Next.js 15 App Router for frontend

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** frontend, ui, framework

## Context

`Enterprise_RAG_Folder_Structure.md` shows a frontend with `app/` directory, `components/`, `lib/`, `tests/` (unit + e2e). The `app/` directory naming implies Next.js App Router. The portfolio dashboard needs:

- Server-rendered pages for fast first paint (recruiter on a slow connection should not stare at a spinner).
- API routes for things like NextAuth callbacks.
- Real-time updates for query traces and ingestion-job progress.
- Heavy data tables (audit log, eval scores, usage records).
- A query-playground with streaming output.

## Decision

- **Next.js 15** (App Router, React 19, RSC).
- **TypeScript 5.x strict**.
- **shadcn/ui + Radix primitives** for component library (copy-in, no runtime lib bloat).
- **Tailwind CSS** for styling.
- **TanStack Query** for client-side data fetching (server-state cache, optimistic updates).
- **NextAuth.js v5** (Auth.js) bound to Keycloak (ADR-0008).
- **biome** for lint/format (faster than eslint+prettier; one tool).
- **vitest** for unit tests; **playwright** for e2e.
- API client: TypeScript SDK auto-generated from OpenAPI specs (`packages/sentinelrag-sdk/typescript`).
- Streaming: server-sent events for query streaming and ingestion-job progress.

## Consequences

### Positive

- React Server Components let us render heavy tables without shipping the data + table lib to the client. Audit log views in particular benefit.
- App Router's nested layouts simplify the dashboard shell + per-section navigation.
- shadcn/ui means we own the component code — no runtime dep we can't fix.
- Next.js has the best deployment story across multiple clouds (Vercel, but also runs as a plain Node container — which is what we ship).

### Negative

- App Router has a steeper learning curve than Pages Router (server vs. client component boundaries; cache semantics).
- Bundling on every dev change is sometimes slow on Windows. We accept this.
- Streaming with SSE behind ALB / GCP LB requires explicit timeouts and ingress annotations.

### Neutral

- We deploy as a containerized Node app (`output: 'standalone'`), not on Vercel — Vercel hosting would be faster but adds another vendor and breaks the "all on K8s" parity.

## Alternatives considered

### Option A — Vite + React SPA
- **Pros:** Simpler; faster dev rebuilds.
- **Cons:** No SSR; first paint slower; no built-in API routes; weaker portfolio signal.
- **Rejected because:** Below the bar for a 2026 portfolio.

### Option B — Remix
- **Pros:** Excellent loader pattern.
- **Cons:** Less recruiter-recognized; Vercel acquired Remix and is folding parts into Next.
- **Rejected because:** Strategic uncertainty; weaker mindshare.

### Option C — SvelteKit
- **Pros:** Modern, fast.
- **Cons:** Smaller ecosystem; weaker recruiter recognition for a JS/React portfolio.
- **Rejected because:** Audience optimization.

## Trade-off summary

| Dimension | Next.js App Router | Vite SPA | Remix |
|---|---|---|---|
| First paint | Fast (SSR) | Slow | Fast |
| Dev experience | Good | Best | Good |
| Recruiter signal | Strong | Standard | Niche |
| Deploy story | K8s container or Vercel | Static + CDN | K8s container |

## References

- [Next.js 15 App Router](https://nextjs.org/docs/app)
- [shadcn/ui](https://ui.shadcn.com/)
- [TanStack Query](https://tanstack.com/query/latest)
