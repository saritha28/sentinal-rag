# ADR-0008: Keycloak self-hosted for OAuth2/JWT

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** auth, security, identity

## Context

The PRD requires OAuth2 + JWT. The DB schema (`users`, `roles`, `role_permissions`, `user_roles`) keeps RBAC inside SentinelRAG — auth provider is only the **identity** source, not the authority on application roles.

Choices:

- **Keycloak self-hosted** — Red Hat-backed open-source IdP, runs in K8s, full OAuth2/OIDC/SAML, federation, customizable login UX. Operationally heavy (~1GB pod + Postgres).
- **Auth0 / Clerk** — managed, fast, free tier sufficient for portfolio scale.
- **AWS Cognito / GCP Identity Platform** — cloud-native managed.

## Decision

Run **Keycloak self-hosted** in the same K8s cluster.

- Realm: `sentinelrag`. Clients: `sentinelrag-api` (confidential), `sentinelrag-frontend` (public PKCE).
- JWTs are RS256-signed with Keycloak's realm key; API verifies signatures via JWKS.
- JWT claims include `sub` (user ID), `tenant_id` (custom mapper), `email`, and `kc_roles` (Keycloak realm roles, ignored by our RBAC).
- **Authoritative RBAC stays in our `users` / `roles` / `role_permissions` tables.** On token validation we look up the user by `sub`, set `app.current_tenant_id`, and resolve permissions from our DB. Keycloak roles are NOT used for authorization decisions.
- Frontend auth: NextAuth.js (Auth.js v5) with Keycloak provider; refresh tokens kept in HTTP-only cookies.
- Persistence: Keycloak's own Postgres (separate DB instance from SentinelRAG's app DB).

## Consequences

### Positive

- Zero recurring cost beyond the K8s resources.
- No vendor dependency; works identically on AWS/GCP/Azure.
- Full UX customization for the login page (matches portfolio branding).
- Federation-ready (can plug GitHub/Google OIDC for the demo without changing app code).
- Strong recruiter signal — Keycloak is what most large enterprises actually run.

### Negative

- Heaviest single piece of infra in the auth domain (~1GB pod + small Postgres).
- Operating Keycloak well is a skill — version upgrades have historically been painful (Quarkus migration, etc.). We pin a major version and bump deliberately.
- Token-claim mapping (especially the custom `tenant_id` mapper) is fiddly to set up.

### Neutral

- The "RBAC stays in our DB" rule is a discipline thing — we must never `if jwt.kc_roles.contains(...)` in service code. ADR-rule, enforced by review.

## Alternatives considered

### Option A — Auth0 / Clerk
- **Pros:** Hours to set up; great UX; reliable.
- **Cons:** Vendor lock-in; recurring cost beyond free tier; conflicts with self-hostable narrative.
- **Rejected because:** "I deployed Keycloak" is a stronger enterprise signal.

### Option B — AWS Cognito (or Identity Platform on GCP)
- **Pros:** Fully managed; cheap.
- **Cons:** Cloud-specific (would need a different IdP on GCP/Azure mirrors); less customizable UX; awkward custom-claim story.
- **Rejected because:** Multi-cloud parity hard requirement.

### Option C — Roll our own auth
- **Pros:** Total control.
- **Cons:** Auth bugs are existential. Don't.
- **Rejected because:** Engineering negligence.

## Trade-off summary

| Dimension | Keycloak | Auth0 / Clerk | Cognito |
|---|---|---|---|
| Setup time | ~1 day | ~2 hours | ~3 hours |
| Recurring cost | $0 (infra only) | $0–$25/mo | $0–$5/mo |
| Multi-cloud | Same on all | Same | Per-cloud variant |
| UX customization | Full | High | Limited |
| Enterprise signal | Strong | Pragmatic | Cloud-native |

## References

- [Keycloak](https://www.keycloak.org/)
- [NextAuth.js Keycloak provider](https://next-auth.js.org/providers/keycloak)
