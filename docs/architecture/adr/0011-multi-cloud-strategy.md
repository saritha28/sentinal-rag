# ADR-0011: Multi-cloud strategy — AWS primary, GCP mirror, Azure ADR-only

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** infra, multi-cloud, terraform

## Context

The portfolio brief targets AWS, GCP, and Azure deploy-readiness. Truly portable across all three is 3× the infra effort. The realistic options are:

- **All three with verified deploys** — strongest possible multi-cloud claim; halves the time available for the actual product.
- **AWS only** — fastest to ship; weakens the multi-cloud signal.
- **AWS primary + GCP mirror + Azure documented** — credible multi-cloud story without sinking the timeline.

## Decision

Three-tier cloud strategy:

### Tier 1: AWS — primary, live deployment
- Full Terraform module set under `infra/terraform/aws/`.
- VPC, EKS, RDS PostgreSQL (with pgvector), ElastiCache Redis, S3, Secrets Manager, IAM, ALB Ingress Controller, External Secrets, ACM cert.
- Live `dev.<domain>` deployed and reachable.
- Demo video records against this environment.

### Tier 2: GCP — mirror, verified deployment
- Full Terraform module set under `infra/terraform/gcp/`.
- VPC, GKE Autopilot (or Standard), Cloud SQL PostgreSQL (with pgvector extension enabled), Memorystore Redis, Cloud Storage, Secret Manager, Workload Identity, GCP Load Balancer.
- Same Helm chart deploys (no chart fork).
- Verified by deploying to a GCP project once, capturing screenshots, then **destroying** to control cost.
- An ADR (this one) and `docs/deployment/gcp/` document the deploy path.

### Tier 3: Azure — ADR mapping, no code
- This ADR captures the Azure mapping:
  - VPC → **Azure VNet**
  - EKS → **AKS** (Azure Kubernetes Service)
  - RDS PostgreSQL → **Azure Database for PostgreSQL — Flexible Server** (pgvector preview enabled)
  - ElastiCache → **Azure Cache for Redis**
  - S3 → **Azure Blob Storage**
  - Secrets Manager → **Azure Key Vault**
  - ALB → **Azure Application Gateway** + AGIC ingress controller
  - IRSA / Workload Identity → **Azure AD Workload Identity**
  - ACM → **Azure Front Door / Key Vault certificate**
- The Helm chart's values structure (object-storage backend, secrets backend, ingress class) is parameterized so adding Azure later is a Terraform exercise, not an app rewrite.

## Consequences

### Positive

- Realistic multi-cloud delivery in finite time.
- The AWS↔GCP parity proves the abstraction; Azure mapping is a credible doc.
- Cost-controlled (GCP destroyed after verification; Azure never provisioned).
- The Helm chart has to actually be cloud-agnostic — design pressure is good.

### Negative

- We can't truthfully claim "deployed on Azure" — we claim "designed deployable to Azure." The portfolio language has to be precise.
- A future Azure deploy is real work (~3–5 days for the missing Terraform modules).

### Neutral

- The ADR is a living doc — if a reviewer asks "show me Azure," we extend the ADR with the missing Terraform sketch but it's still not deployed code.

## Cloud-portability rules (enforced in code)

These are the design rules that make the abstraction real:

1. **Object storage** is accessed via an `ObjectStorage` interface with `S3Storage`, `GcsStorage`, `AzureBlobStorage`, `MinioStorage` adapters. Service code never imports `boto3` directly.
2. **Secrets** are accessed via `SecretsProvider` interface (`AwsSecretsManager`, `GcpSecretManager`, `AzureKeyVault`, `EnvVarProvider` for dev). External Secrets Operator handles the K8s side regardless.
3. **DB connection strings** come from secrets; pgvector is the assumed DB extension on every cloud.
4. **The Helm chart** has a `cloud:` value (`aws | gcp | azure | local`) that switches Ingress class, ServiceAccount annotations, and storage class — nothing else changes between clouds.

## Alternatives considered

### Option A — All three deployed
- **Pros:** Strongest multi-cloud claim.
- **Cons:** Triples infra cost AND infra surface area; less product to ship.
- **Rejected because:** Optimizing for the multi-cloud bullet point hurts the AI/RAG bullet points which are the real differentiators.

### Option B — AWS only
- **Pros:** Cleanest scope.
- **Cons:** Loses the "I can think across clouds" signal entirely.
- **Rejected because:** Cheap to add the GCP mirror because the abstraction work is needed regardless.

## Trade-off summary

| Dimension | This | All three | AWS only |
|---|---|---|---|
| Eng cost | Medium | High | Low |
| Cloud coverage claim | "AWS prod, GCP verified, Azure designed" | "All three" | "AWS" |
| Ongoing cost | AWS only | Three clouds | AWS only |
| Helm-chart pressure | Real (must be cloud-agnostic) | Real | None |

## References

- [GKE pgvector enablement](https://cloud.google.com/sql/docs/postgres/extensions#pgvector)
- [Azure DB for PostgreSQL pgvector](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-extensions)
