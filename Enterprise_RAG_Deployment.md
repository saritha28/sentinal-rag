# SentinelRAG — Terraform Infra + Kubernetes Manifests

## 1. Repository Structure

```text
sentinelrag-infra/
  terraform/
    aws/
      environments/
        dev/
        prod/
      modules/
        vpc/
        eks/
        rds/
        opensearch/
        elasticache/
        s3/
        iam/
        secrets/
        monitoring/
    gcp/
      environments/
        dev/
        prod/
      modules/
        network/
        gke/
        cloudsql/
        memorystore/
        storage/
        iam/
        secrets/
  k8s/
    base/
      namespace.yaml
      configmap.yaml
      secrets.yaml
      api-deployment.yaml
      rag-deployment.yaml
      ingestion-worker.yaml
      retrieval-service.yaml
      evaluation-worker.yaml
      audit-service.yaml
      frontend-deployment.yaml
      services.yaml
      ingress.yaml
      hpa.yaml
      pdb.yaml
      networkpolicy.yaml
    overlays/
      dev/
        kustomization.yaml
      prod/
        kustomization.yaml
  helm/
    sentinelrag/
  .github/
    workflows/
      terraform-plan.yml
      terraform-apply.yml
      deploy-k8s.yml
```

---

# 2. AWS EKS Terraform Architecture

## AWS Services

```text
VPC
EKS
RDS PostgreSQL + pgvector
OpenSearch
ElastiCache Redis
S3
Secrets Manager
CloudWatch
IAM Roles for Service Accounts
AWS Load Balancer Controller
```

---

## 2.1 AWS Provider

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "sentinelrag-terraform-state"
    key            = "aws/prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "sentinelrag-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}
```

---

## 2.2 AWS Environment Variables

```hcl
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "project_name" {
  type    = string
  default = "sentinelrag"
}

variable "db_username" {
  type      = string
  sensitive = true
}

variable "db_password" {
  type      = string
  sensitive = true
}
```

---

## 2.3 AWS Main Environment

```hcl
module "vpc" {
  source       = "../../modules/vpc"
  project_name = var.project_name
  environment = var.environment
  cidr_block   = "10.20.0.0/16"
}

module "eks" {
  source          = "../../modules/eks"
  project_name    = var.project_name
  environment     = var.environment
  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnet_ids
}

module "rds" {
  source          = "../../modules/rds"
  project_name    = var.project_name
  environment     = var.environment
  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnet_ids
  db_username     = var.db_username
  db_password     = var.db_password
}

module "opensearch" {
  source       = "../../modules/opensearch"
  project_name = var.project_name
  environment = var.environment
  vpc_id       = module.vpc.vpc_id
  subnet_ids   = module.vpc.private_subnet_ids
}

module "redis" {
  source       = "../../modules/elasticache"
  project_name = var.project_name
  environment = var.environment
  vpc_id       = module.vpc.vpc_id
  subnet_ids   = module.vpc.private_subnet_ids
}

module "s3" {
  source       = "../../modules/s3"
  project_name = var.project_name
  environment = var.environment
}
```

---

# 3. AWS Module Examples

## 3.1 VPC Module

```hcl
resource "aws_vpc" "main" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-vpc"
    Environment = var.environment
  }
}

resource "aws_subnet" "private" {
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.cidr_block, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.project_name}-${var.environment}-private-${count.index}"
  }
}

resource "aws_subnet" "public" {
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.cidr_block, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.project_name}-${var.environment}-public-${count.index}"
  }
}
```

---

## 3.2 EKS Module

```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${var.project_name}-${var.environment}"
  cluster_version = "1.29"

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnets

  enable_irsa = true

  eks_managed_node_groups = {
    general = {
      instance_types = ["m6i.large"]
      min_size       = 2
      max_size       = 6
      desired_size   = 3
    }

    ai_workers = {
      instance_types = ["m6i.xlarge"]
      min_size       = 1
      max_size       = 5
      desired_size   = 2

      labels = {
        workload = "ai"
      }
    }
  }
}
```

---

## 3.3 RDS PostgreSQL

```hcl
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnets"
  subnet_ids = var.private_subnets
}

resource "aws_db_instance" "postgres" {
  identifier = "${var.project_name}-${var.environment}-postgres"

  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.r6g.large"

  allocated_storage     = 100
  max_allocated_storage = 500
  storage_encrypted     = true

  db_name  = "sentinelrag"
  username = var.db_username
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  backup_retention_period = 14
  deletion_protection     = true
  skip_final_snapshot     = false

  performance_insights_enabled = true
}
```

---

## 3.4 S3 Buckets

```hcl
resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-${var.environment}-documents"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id

  versioning_configuration {
    status = "Enabled"
  }
}
```

---

# 4. GCP GKE Terraform Architecture

## GCP Services

```text
VPC Network
GKE
Cloud SQL PostgreSQL
Cloud Storage
Memorystore Redis
Secret Manager
Cloud Logging
Cloud Monitoring
Workload Identity
```

---

## 4.1 GCP Provider

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "sentinelrag-terraform-state"
    prefix = "gcp/prod"
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
```

---

## 4.2 GCP Main Environment

```hcl
module "network" {
  source       = "../../modules/network"
  project_name = var.project_name
  environment = var.environment
  region       = var.gcp_region
}

module "gke" {
  source       = "../../modules/gke"
  project_name = var.project_name
  environment = var.environment
  region       = var.gcp_region
  network      = module.network.network_name
  subnetwork   = module.network.subnetwork_name
}

module "cloudsql" {
  source       = "../../modules/cloudsql"
  project_name = var.project_name
  environment = var.environment
  region       = var.gcp_region
  db_password  = var.db_password
}

module "storage" {
  source       = "../../modules/storage"
  project_name = var.project_name
  environment = var.environment
}
```

---

## 4.3 GKE Module

```hcl
resource "google_container_cluster" "main" {
  name     = "${var.project_name}-${var.environment}"
  location = var.region

  network    = var.network
  subnetwork = var.subnetwork

  remove_default_node_pool = true
  initial_node_count       = 1

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = "REGULAR"
  }

  logging_service    = "logging.googleapis.com/kubernetes"
  monitoring_service = "monitoring.googleapis.com/kubernetes"
}

resource "google_container_node_pool" "general" {
  name       = "general"
  location   = var.region
  cluster    = google_container_cluster.main.name
  node_count = 3

  node_config {
    machine_type = "e2-standard-4"
    disk_size_gb = 100
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}
```

---

## 4.4 Cloud SQL PostgreSQL

```hcl
resource "google_sql_database_instance" "postgres" {
  name             = "${var.project_name}-${var.environment}-postgres"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier = "db-custom-2-8192"

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled = false
      private_network = var.private_network_id
    }
  }

  deletion_protection = true
}

resource "google_sql_database" "sentinelrag" {
  name     = "sentinelrag"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "app" {
  name     = "sentinelrag_app"
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}
```

---

# 5. Kubernetes Base Manifests

## 5.1 Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sentinelrag
  labels:
    app.kubernetes.io/name: sentinelrag
    app.kubernetes.io/part-of: enterprise-rag-platform
```

---

## 5.2 ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sentinelrag-config
  namespace: sentinelrag
data:
  ENVIRONMENT: "prod"
  LOG_LEVEL: "INFO"
  API_BASE_PATH: "/api/v1"
  DEFAULT_EMBEDDING_MODEL: "text-embedding-3-small"
  DEFAULT_GENERATION_MODEL: "gpt-4.1-mini"
  RETRIEVAL_MODE: "hybrid"
  ENABLE_AUDIT_LOGGING: "true"
  ENABLE_EVALUATION_LOGGING: "true"
  ENABLE_COST_TRACKING: "true"
```

---

## 5.3 Secret Placeholder

Use External Secrets in production.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: sentinelrag-secrets
  namespace: sentinelrag
type: Opaque
stringData:
  DATABASE_URL: "postgresql://user:password@postgres:5432/sentinelrag"
  REDIS_URL: "redis://redis:6379/0"
  OPENSEARCH_URL: "https://opensearch:9200"
  OPENAI_API_KEY: "replace-me"
  ANTHROPIC_API_KEY: "replace-me"
  JWT_SECRET: "replace-me"
```

---

# 6. Core Application Deployments

## 6.1 API Service Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sentinelrag-api
  namespace: sentinelrag
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sentinelrag-api
  template:
    metadata:
      labels:
        app: sentinelrag-api
    spec:
      containers:
        - name: api
          image: ghcr.io/your-org/sentinelrag-api:latest
          imagePullPolicy: Always
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: sentinelrag-config
            - secretRef:
                name: sentinelrag-secrets
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 30
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2"
              memory: "2Gi"
```

---

## 6.2 RAG Orchestrator Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-orchestrator
  namespace: sentinelrag
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rag-orchestrator
  template:
    metadata:
      labels:
        app: rag-orchestrator
    spec:
      containers:
        - name: rag-orchestrator
          image: ghcr.io/your-org/sentinelrag-rag:latest
          ports:
            - containerPort: 8010
          envFrom:
            - configMapRef:
                name: sentinelrag-config
            - secretRef:
                name: sentinelrag-secrets
          resources:
            requests:
              cpu: "1"
              memory: "2Gi"
            limits:
              cpu: "4"
              memory: "4Gi"
```

---

## 6.3 Ingestion Worker

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ingestion-worker
  namespace: sentinelrag
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ingestion-worker
  template:
    metadata:
      labels:
        app: ingestion-worker
    spec:
      containers:
        - name: ingestion-worker
          image: ghcr.io/your-org/sentinelrag-ingestion:latest
          envFrom:
            - configMapRef:
                name: sentinelrag-config
            - secretRef:
                name: sentinelrag-secrets
          resources:
            requests:
              cpu: "1"
              memory: "2Gi"
            limits:
              cpu: "4"
              memory: "8Gi"
```

---

## 6.4 Retrieval Service

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: retrieval-service
  namespace: sentinelrag
spec:
  replicas: 3
  selector:
    matchLabels:
      app: retrieval-service
  template:
    metadata:
      labels:
        app: retrieval-service
    spec:
      containers:
        - name: retrieval-service
          image: ghcr.io/your-org/sentinelrag-retrieval:latest
          ports:
            - containerPort: 8020
          envFrom:
            - configMapRef:
                name: sentinelrag-config
            - secretRef:
                name: sentinelrag-secrets
          resources:
            requests:
              cpu: "1"
              memory: "2Gi"
            limits:
              cpu: "4"
              memory: "4Gi"
```

---

## 6.5 Evaluation Worker

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evaluation-worker
  namespace: sentinelrag
spec:
  replicas: 2
  selector:
    matchLabels:
      app: evaluation-worker
  template:
    metadata:
      labels:
        app: evaluation-worker
    spec:
      containers:
        - name: evaluation-worker
          image: ghcr.io/your-org/sentinelrag-evaluation:latest
          envFrom:
            - configMapRef:
                name: sentinelrag-config
            - secretRef:
                name: sentinelrag-secrets
          resources:
            requests:
              cpu: "1"
              memory: "2Gi"
            limits:
              cpu: "4"
              memory: "4Gi"
```

---

# 7. Kubernetes Services

```yaml
apiVersion: v1
kind: Service
metadata:
  name: sentinelrag-api
  namespace: sentinelrag
spec:
  selector:
    app: sentinelrag-api
  ports:
    - name: http
      port: 80
      targetPort: 8000
  type: ClusterIP
---
apiVersion: v1
kind: Service
metadata:
  name: rag-orchestrator
  namespace: sentinelrag
spec:
  selector:
    app: rag-orchestrator
  ports:
    - name: http
      port: 8010
      targetPort: 8010
  type: ClusterIP
---
apiVersion: v1
kind: Service
metadata:
  name: retrieval-service
  namespace: sentinelrag
spec:
  selector:
    app: retrieval-service
  ports:
    - name: http
      port: 8020
      targetPort: 8020
  type: ClusterIP
```

---

# 8. Ingress

## AWS ALB Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sentinelrag-ingress
  namespace: sentinelrag
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80},{"HTTPS":443}]'
spec:
  rules:
    - host: api.sentinelrag.dev
      http:
        paths:
          - path: /api/v1
            pathType: Prefix
            backend:
              service:
                name: sentinelrag-api
                port:
                  number: 80
```

---

## GCP Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sentinelrag-ingress
  namespace: sentinelrag
  annotations:
    kubernetes.io/ingress.class: gce
    networking.gke.io/managed-certificates: sentinelrag-cert
spec:
  rules:
    - host: api.sentinelrag.dev
      http:
        paths:
          - path: /api/v1
            pathType: Prefix
            backend:
              service:
                name: sentinelrag-api
                port:
                  number: 80
```

---

# 9. Autoscaling

## API HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: sentinelrag-api-hpa
  namespace: sentinelrag
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: sentinelrag-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 65
```

---

## RAG Orchestrator HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-orchestrator-hpa
  namespace: sentinelrag
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rag-orchestrator
  minReplicas: 3
  maxReplicas: 30
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

# 10. Pod Disruption Budget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: sentinelrag-api-pdb
  namespace: sentinelrag
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: sentinelrag-api
```

---

# 11. Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sentinelrag-default-deny
  namespace: sentinelrag
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-to-services
  namespace: sentinelrag
spec:
  podSelector:
    matchLabels:
      app: sentinelrag-api
  policyTypes:
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: rag-orchestrator
        - podSelector:
            matchLabels:
              app: retrieval-service
```

---

# 12. External Secrets Pattern

## AWS Secrets Manager

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: sentinelrag
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: sentinelrag-service-account
```

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: sentinelrag-secrets
  namespace: sentinelrag
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: sentinelrag-secrets
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: sentinelrag/prod/database-url
    - secretKey: OPENAI_API_KEY
      remoteRef:
        key: sentinelrag/prod/openai-api-key
```

---

# 13. Service Account

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sentinelrag-service-account
  namespace: sentinelrag
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::<account-id>:role/sentinelrag-prod-irsa
```

For GKE:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sentinelrag-service-account
  namespace: sentinelrag
  annotations:
    iam.gke.io/gcp-service-account: sentinelrag-prod@project-id.iam.gserviceaccount.com
```

---

# 14. Kustomize Overlays

## Base Kustomization

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - namespace.yaml
  - configmap.yaml
  - secrets.yaml
  - api-deployment.yaml
  - rag-deployment.yaml
  - ingestion-worker.yaml
  - retrieval-service.yaml
  - evaluation-worker.yaml
  - services.yaml
  - ingress.yaml
  - hpa.yaml
  - pdb.yaml
  - networkpolicy.yaml
```

---

## Production Overlay

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namespace: sentinelrag

images:
  - name: ghcr.io/your-org/sentinelrag-api
    newTag: v1.0.0
  - name: ghcr.io/your-org/sentinelrag-rag
    newTag: v1.0.0
  - name: ghcr.io/your-org/sentinelrag-ingestion
    newTag: v1.0.0
  - name: ghcr.io/your-org/sentinelrag-retrieval
    newTag: v1.0.0
  - name: ghcr.io/your-org/sentinelrag-evaluation
    newTag: v1.0.0
```

---

# 15. GitHub Actions

## Terraform Plan

```yaml
name: Terraform Plan

on:
  pull_request:
    paths:
      - "terraform/**"

jobs:
  terraform-plan:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init
        working-directory: terraform/aws/environments/prod

      - name: Terraform Validate
        run: terraform validate
        working-directory: terraform/aws/environments/prod

      - name: Terraform Plan
        run: terraform plan
        working-directory: terraform/aws/environments/prod
```

---

## Kubernetes Deploy

```yaml
name: Deploy Kubernetes

on:
  push:
    branches:
      - main
    paths:
      - "k8s/**"

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Configure kubeconfig
        run: aws eks update-kubeconfig --name sentinelrag-prod --region us-east-1

      - name: Deploy
        run: kubectl apply -k k8s/overlays/prod
```

---

# 16. Production Readiness Checklist

## Infrastructure

```text
[ ] Private subnets for app workloads
[ ] Managed PostgreSQL with backups
[ ] Redis cache
[ ] OpenSearch private endpoint
[ ] Object storage encryption
[ ] Terraform remote state locking
[ ] Separate dev/staging/prod environments
```

## Kubernetes

```text
[ ] Readiness probes
[ ] Liveness probes
[ ] HPA
[ ] PDB
[ ] Resource requests/limits
[ ] Network policies
[ ] External secrets
[ ] Service accounts with least privilege
```

## AI Platform

```text
[ ] Model API keys stored securely
[ ] Token usage logging
[ ] Cost limits per tenant
[ ] Eval jobs isolated from online query path
[ ] Retrieval trace logging
[ ] Hallucination score persisted
```

## Observability

```text
[ ] OpenTelemetry tracing
[ ] Prometheus metrics
[ ] Grafana dashboards
[ ] Centralized logs
[ ] Alerting for latency, cost, errors
```

---

# 17. Hiring Signal

This infrastructure package demonstrates:

```text
Cloud-native AI architecture
Kubernetes deployment maturity
Terraform module design
Multi-cloud deployment thinking
Production security posture
Enterprise-grade scalability
Observability and reliability engineering
Cost-aware AI platform operations
```

The next highest-value deliverable is **production folder-by-folder implementation starter code** for the backend services: FastAPI, SQLAlchemy models, Alembic migrations, RAG orchestrator, retrieval service, and evaluation worker.
