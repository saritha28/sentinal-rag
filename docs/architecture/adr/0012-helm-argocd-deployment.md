# ADR-0012: Helm chart + ArgoCD GitOps for K8s deployment

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** k8s, deployment, gitops, helm

## Context

`Enterprise_RAG_Deployment.md` shows two deployment styles:

- §15 GitHub Actions running `kubectl apply -k k8s/overlays/prod` from CI.
- §1 mentions both `k8s/` (Kustomize) and `helm/sentinelrag/` (Helm).

`kubectl apply -k` from CI is a development pattern, not a production pattern. It creates several real problems:

- No declarative source-of-truth in the cluster — drift is invisible.
- Rollbacks require reverting Git + re-running CI; no `helm rollback`.
- No automatic sync; secrets refresh is manual.
- No dry-run with diff against live state.
- One CI failure mid-rollout leaves the cluster in a partial state.

## Decision

Two-tool approach:

### Helm — packaging
- Single Helm chart at `infra/helm/sentinelrag/`.
- One chart for the whole platform; sub-charts for major components (`api`, `retrieval-service`, `ingestion-service`, `evaluation-service`, `temporal-worker`, `frontend`).
- Dependency charts pulled in: `bitnami/postgresql` (dev only), `bitnami/redis` (dev only), `temporalio/temporal`, `keycloak/keycloak`, `unleash/unleash`.
- Production values per environment: `values.yaml`, `values-dev.yaml`, `values-prod.yaml`.
- Cloud switch: `cloud: aws | gcp | azure | local` controls Ingress class, ServiceAccount annotations, storage class.

### ArgoCD — delivery
- ArgoCD installed in each cluster (or `argocd-cli` driven from a meta-cluster — for portfolio scale, in-cluster is simplest).
- One `Application` per environment pointing at `infra/helm/sentinelrag` with the right values overlay.
- Automatic sync on `main` branch with prune + self-heal.
- ArgoCD Image Updater watches GHCR for new image tags matching `^v[0-9]+\.[0-9]+\.[0-9]+$` and bumps the chart values.

### CI's job
- Build images on every commit; tag `:sha-<short>` and on tagged release `:vX.Y.Z`.
- Push to GHCR.
- On a Git tag, run `helm lint`, `helm template`, `helm diff` against the prod values to surface what's changing.
- ArgoCD does the actual apply.

### CD's job
- ArgoCD reconciles cluster state against Git within 3 minutes.
- Rollback = revert Git commit (or `helm rollback` via `argocd app rollback`).

## Consequences

### Positive

- Single source of truth (Git) — the cluster state is auditable.
- No CI credentials with cluster admin scope (smaller blast radius).
- Visual diff of pending changes via the ArgoCD UI before sync.
- Drift detection and auto-correction.
- Rollbacks are first-class.

### Negative

- Two extra moving parts (Helm + ArgoCD) on top of plain `kubectl`.
- ArgoCD itself needs to be installed and updated — but its Helm chart handles that.
- Initial setup is ~half a day vs. ~an hour for `kubectl apply`.

### Neutral

- The `k8s/base` and `k8s/overlays` directories from the deployment doc are *replaced* by the Helm chart. We don't maintain both.

## Alternatives considered

### Option A — Plain Kustomize + `kubectl apply` from CI (per spec)
- **Pros:** Lightweight; matches the deployment doc.
- **Cons:** Above. Anti-pattern for prod.
- **Rejected because:** Production deployment maturity is a key portfolio signal.

### Option B — Helm + `helm upgrade` from CI (no ArgoCD)
- **Pros:** Less infra than ArgoCD.
- **Cons:** Still has the credential blast radius and "drift after manual change" problem.
- **Rejected because:** Half-measure.

### Option C — Flux instead of ArgoCD
- **Pros:** GitOps-native, simpler.
- **Cons:** Less recruiter-visible than ArgoCD.
- **Acceptable alternative:** if ArgoCD becomes painful, Flux is a 1-day swap. For now, ArgoCD's UI is the recruiter signal.

## Trade-off summary

| Dimension | Helm + ArgoCD | kubectl apply -k from CI | Helm from CI |
|---|---|---|---|
| Source of truth | Git (with reconciliation) | Git (without reconciliation) | Git |
| Drift detection | Automatic | Manual | Manual |
| Rollback | First-class | Re-run CI | `helm rollback` (CI) |
| Setup | ~half day | ~1 hour | ~2 hours |
| Recruiter signal | Strong | Weak | Medium |

## Notes on the design docs

**Overrides** `Enterprise_RAG_Deployment.md` §15 (the `kubectl apply -k` GitHub Actions step). The CI workflow does build + push + chart-lint; ArgoCD does deploy.

## References

- [ArgoCD](https://argo-cd.readthedocs.io/)
- [Helm chart best practices](https://helm.sh/docs/chart_best_practices/)
