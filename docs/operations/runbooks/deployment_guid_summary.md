 Below is a distilled step-by-step deploy guide pulled from the three canonical runbooks (deployment-aws.md, deployment-gcp.md, cluster-bootstrap.md). The runbooks remain authoritative — this is the on-ramp.                                                                                                    
                                                                                                                                                                                                                                                                                                                    
  Shared overview                                                                         
                                                                                                                                                                                                                                                                                                                    
  What you are deploying. One Helm chart (infra/helm/sentinelrag/) running 3 workloads — api, temporal-worker, frontend — plus a pre-upgrade Alembic migration Job. Cloud differences live in:                                                                                                                      
  - Terraform under infra/terraform/{aws,gcp}/environments/dev/
  - Helm value overlays values-{dev,gcp-dev}.yaml                                                                                                                                                                                                                                                                   
  - Bootstrap chart values under infra/bootstrap/           

  Time / cost. AWS ~90 min, ~$200–$300/mo idle. GCP ~75 min, ~$250–$350/mo idle.

  Tools required (both clouds). Terraform ≥ 1.7, kubectl, Helm ≥ 3.14, jq, a domain you control DNS for, plus aws CLI ≥ 2.15 (AWS) or gcloud (GCP).

  One-time prerequisite (both clouds). Push a git tag like v0.1.0 to fire .github/workflows/build-images.yml, which builds + pushes sentinelrag-{api,temporal-worker,frontend} to GHCR. Make them public or create a pull secret in the cluster.

  ---
  AWS deploy — 12 steps

  1. Bootstrap remote state — create the S3 state bucket (sentinelrag-tfstate-${ACCOUNT_ID}, versioned, KMS-encrypted, public-access blocked) and the DynamoDB lock table (sentinelrag-tfstate-locks, PAY_PER_REQUEST). Wait for TableStatus=ACTIVE.
  2. Apply Terraform in infra/terraform/aws/environments/dev:
    - copy terraform.tfvars.example → terraform.tfvars, fill in region, name_prefix, rds_master_password, redis_auth_token (use openssl rand -base64 32)
    - terraform init with -backend-config="bucket=…",dynamodb_table=…,region=…
    - terraform plan -out tf.plan && terraform apply tf.plan (~15 min, EKS dominates)
    - Capture outputs: kubectl_config_command, irsa_role_arns, documents_bucket, audit_bucket, rds_*, redis_*.
  3. Wire kubectl — run the one-liner from terraform output -raw kubectl_config_command. kubectl get nodes should show 2 t3.large nodes Ready.
  4. Publish images to GHCR — git tag v0.1.0 && git push origin v0.1.0, wait ~10 min for the workflow.
  5. DNS + ACM — aws acm request-certificate for sentinelrag.example.com + *.dev.sentinelrag.example.com (DNS validation). Create the validation CNAMEs at your DNS provider; defer the public A records until step 10.
  6. Bootstrap the cluster (follow cluster-bootstrap.md, in order):
    a. cert-manager v1.16.2 → add a letsencrypt-prod ClusterIssuer with class: alb
    b. AWS Load Balancer Controller 1.10.1 → paste irsa_role_arns.alb_controller into infra/bootstrap/aws-load-balancer-controller/values.yaml
    c. External Secrets Operator 0.10.7 → paste ESO IRSA ARN into values, then kubectl apply -f infra/bootstrap/external-secrets/secret-store-aws.yaml
    d. Temporal 0.55.0 (bundled Postgres for dev)
    e. ArgoCD 7.7.5 → first create K8s secret argocd-secret with the Keycloak SSO client secret
    f. kubectl apply -f infra/bootstrap/argocd/applications/sentinelrag-dev.yaml
  7. Stamp real IRSA ARNs into Helm values — sed the placeholders in infra/helm/sentinelrag/values-dev.yaml with the real ARNs from terraform output -json irsa_role_arns | jq -r .{api,worker,frontend}. Commit + push; ArgoCD auto-syncs within 3 min.
  8. Seed Secrets Manager — overwrite the placeholder JSON in sentinelrag-dev/{api,temporal-worker,frontend} with real values (DATABASE_URL built from RDS outputs, REDIS_URL from ElastiCache outputs, Keycloak issuer/audience/JWKS, Unleash token). Force ESO refresh:
  kubectl -n sentinelrag annotate externalsecret sentinelrag-{api,worker,frontend}-secrets force-sync=$(date +%s) --overwrite
  9. Watch the first sync — kubectl -n argocd get application sentinelrag-dev -w and kubectl -n sentinelrag get pods -w. Order: migration Job (30–60s) → Deployments → Ingresses → ALBs (3–5 min).
  10. Point DNS at the ALB — kubectl -n sentinelrag get ingress to read each ALB hostname. Create A records api.dev… and app.dev… to those hostnames.
  11. Smoke test — mint a Keycloak token, hit GET /api/v1/health, then POST /api/v1/query.
  12. Optional — enable DR backup verifier. Set SENTINELRAG_AWS_ENABLED=true plus AWS_DR_VERIFY_ROLE_ARN in repo Variables/Secrets to activate .github/workflows/dr-backup-verify.yml.

  OpenSearch is opt-in. Don't enable in step 2. Add a module "opensearch" block separately and flip the Unleash flag keyword_backend=opensearch (~$300+/mo extra).

  Tear-down note. terraform destroy will fail on the audit bucket — Object Lock COMPLIANCE 7y is non-revocable by design (ADR-0016). That's expected.

  ---
  GCP deploy — 12 steps

  1. Project + APIs — gcloud projects create, link billing, enable: compute, container, sqladmin, redis, secretmanager, servicenetworking, iam, cloudresourcemanager, artifactregistry, certificatemanager.
  2. Bootstrap remote state — create a versioned GCS bucket sentinelrag-tfstate-${PROJECT} with uniform-bucket-level access.
  3. Apply Terraform in infra/terraform/gcp/environments/dev:
    - fill in project_id, region, name_prefix, cloudsql_master_password
    - terraform init -backend-config="bucket=${STATE_BUCKET}"
    - terraform plan && terraform apply (~12 min)
    - Capture outputs: kubectl_config_command, wi_gsa_emails, buckets, cloudsql_private_ip, redis_host/port/auth_string.
  4. Wire kubectl — run terraform output -raw kubectl_config_command.
  5. Publish images — same git tag v0.1.0 flow as AWS.
  6. DNS + ManagedCertificate prep — reserve global static IPs:
  gcloud compute addresses create sentinelrag-dev-api  --global
  gcloud compute addresses create sentinelrag-dev-app  --global
  6. Create api.dev… and app.dev… A records pointing to those IPs. The chart will create the ManagedCertificate resources in step 9; Google validates via DNS-01 once records resolve.
  7. Bootstrap the cluster — follow cluster-bootstrap.md with these GCP edits:
    a. cert-manager — install, but skip the letsencrypt-prod ClusterIssuer (ManagedCertificate handles certs)
    b. Skip AWS Load Balancer Controller (GCE Ingress is built into GKE)
    c. External Secrets Operator — in external-secrets/values.yaml, swap the eks.amazonaws.com/role-arn annotation for iam.gke.io/gcp-service-account: <eso GSA email>. Edit secret-store-gcp.yaml to set projectID, then apply.
    d. Temporal — same chart, same values
    e. ArgoCD — same, but in infra/bootstrap/argocd/values.yaml set Ingress class to gce and use kubernetes.io/ingress.global-static-ip-name + networking.gke.io/managed-certificates annotations
    f. kubectl apply -f infra/bootstrap/argocd/applications/sentinelrag-gcp-dev.yaml
  8. Stamp real Workload Identity emails into Helm values — sed the placeholders in values-gcp-dev.yaml with terraform output -json wi_gsa_emails | jq -r .{api,worker,frontend}. Commit + push.
  9. Seed Secret Manager — gcloud secrets versions add sentinelrag-dev-{api,temporal-worker,frontend} with the same JSON shape as AWS (DATABASE_URL built from CloudSQL outputs, REDIS_URL from Memorystore outputs). Force ESO refresh with the same annotation trick.
  10. Watch the first sync — kubectl -n argocd get application sentinelrag-gcp-dev -w. Order: migration Job → Pods → GCE LB (5–10 min) → ManagedCertificate Provisioning → Active (5–30 min after DNS resolves). Verify kubectl -n sentinelrag get managedcertificate.
  11. Smoke test — same Keycloak token + health + query as AWS.
  12. Optional — DR backup verifier — set SENTINELRAG_GCP_ENABLED=true, SENTINELRAG_GCP_PROJECT, GCP_WIF_PROVIDER, GCP_DR_VERIFY_SA. WIF provider + dr-verify SA are operator-provisioned (not in Terraform today).

  Tear-down. Same audit-bucket caveat — locked retention is non-revocable for 7 years.

  ---
  AWS ↔ GCP differences at a glance

  ┌────────────────────┬──────────────────────────────────────────┬──────────────────────────────────────────────────────┐
  │      Concern       │                   AWS                    │                         GCP                          │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ State backend      │ S3 + DynamoDB lock                       │ GCS (versioned)                                      │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Cluster            │ EKS 1.30, t3.large × 2-6                 │ GKE Standard 1.30 private nodes, e2-standard-4 × 1-3 │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Postgres           │ RDS db.t4g.medium + pgvector PG          │ Cloud SQL db-custom-2-4096 + pgvector + PSA peering  │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Redis              │ ElastiCache 7.1 cache.t4g.small          │ Memorystore 7.2 BASIC, 1 GB                          │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Object storage     │ S3 versioned + Object Lock COMPLIANCE 7y │ GCS versioned + locked retention 7y                  │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Pod identity       │ IRSA via OIDC                            │ Workload Identity                                    │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Ingress            │ AWS LB Controller + ALB + ACM            │ GCE Ingress + global static IP + ManagedCertificate  │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Cert provisioning  │ cert-manager + ACM                       │ ManagedCertificate (skip cert-manager ClusterIssuer) │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ State backend      │ S3 + DynamoDB lock                       │ GCS (versioned)                                      │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Cluster            │ EKS 1.30, t3.large × 2-6                 │ GKE Standard 1.30 private nodes, e2-standard-4 × 1-3 │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Postgres           │ RDS db.t4g.medium + pgvector PG          │ Cloud SQL db-custom-2-4096 + pgvector + PSA peering  │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Redis              │ ElastiCache 7.1 cache.t4g.small          │ Memorystore 7.2 BASIC, 1 GB                          │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Object storage     │ S3 versioned + Object Lock COMPLIANCE 7y │ GCS versioned + locked retention 7y                  │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Pod identity       │ IRSA via OIDC                            │ Workload Identity                                    │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Ingress            │ AWS LB Controller + ALB + ACM            │ GCE Ingress + global static IP + ManagedCertificate  │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Cert provisioning  │ cert-manager + ACM                       │ ManagedCertificate (skip cert-manager ClusterIssuer) │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ Secrets backend    │ Secrets Manager + ESO                    │ Secret Manager + ESO                                 │
  ├────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────┤
  │ ArgoCD Application │ sentinelrag-dev.yaml                     │ sentinelrag-gcp-dev.yaml                             │
  └────────────────────┴──────────────────────────────────────────┴──────────────────────────────────────────────────────┘

  ---
  Recurring traps to avoid

  - Out-of-order bootstrap applies fail webhook handshakes. Stick to the cluster-bootstrap order; cert-manager → ALB controller (AWS) → ESO → Temporal → ArgoCD.
  - GHCR images private by default. Either flip visibility to public or wire an imagePullSecrets in the chart.
  - Helm 4 + dependency tarballs. helm template requires helm dependency build and tarball extraction (deployment runbook documents this).
  - Don't enable OpenSearch by default (ADR-0026). It's a deliberate scale opt-in.
  - Audit buckets survive destroy. This is the durability guarantee, not a bug (ADR-0016).
  - Never enable the Bearer dev bypass against a deployed env. It's gated by ENVIRONMENT=local AND AUTH_ALLOW_DEV_TOKEN=true; both default to false.

  For module-by-module specifics see infra/terraform/{aws,gcp}/README.md. For incident response after you're live: disaster-recovery.md.
