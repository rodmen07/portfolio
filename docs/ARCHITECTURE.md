# Architecture

This document is the long-form architecture reference for the Portfolio
workspace. The short pitch lives in the root [README](../README.md); the
day-to-day contributor workflow lives in [CONTRIBUTING.md](./CONTRIBUTING.md);
historical version-by-version progress lives in [ROADMAP.md](./ROADMAP.md).

The canonical machine-readable list of services is
[`services.yaml`](../services.yaml). When the table below disagrees with
`services.yaml`, the YAML wins.

---

## Projects

### 1. [InfraPortal — Microservices Platform](../microservices/)

CRM platform with PostgreSQL (Cloud SQL) persistence, JWT authentication, and
AI integration. All backend services deployed on GCP Cloud Run (scale-to-zero,
us-central1) with GitHub Actions OIDC CI/CD. Includes a client portal with
GitHub + Google OAuth and an admin provisioning UI.

#### Services

| Service | Language | Deployment | Role |
|---------|----------|-----------|------|
| `task-api-service` | Rust / Axum | Fly.io | Core task CRUD, AI planner proxy, audit log |
| `accounts-service` | Rust / Axum | GCP Cloud Run | Account and tenant domain |
| `contacts-service` | Rust / Axum | GCP Cloud Run | Contact and lead domain, cross-service account validation |
| `activities-service` | Rust / Axum | GCP Cloud Run | Activity tracking |
| `automation-service` | Rust / Axum | GCP Cloud Run | Automation rules |
| `integrations-service` | Rust / Axum | GCP Cloud Run | Third-party integration hooks |
| `opportunities-service` | Rust / Axum | GCP Cloud Run | Sales opportunity domain |
| `reporting-service` | Rust / Axum | GCP Cloud Run | Aggregated reports |
| `search-service` | Rust / Axum | GCP Cloud Run | Cross-domain search |
| `audit-service` | Rust / Axum | GCP Cloud Run | Immutable CRM mutation log |
| `projects-service` | Rust / Axum | GCP Cloud Run | Client portal data — projects, milestones, deliverables |
| `ai-orchestrator-service` | Python / FastAPI | Fly.io | LLM-backed goal-to-task planner (Claude + Gemini) |
| `auth-service` | Python / FastAPI | GCP Cloud Run | JWT issuance, GitHub + Google OAuth |
| `event-stream-service` | Go | Fly.io | SSE hub — real-time event fan-out with ring buffer replay |
| `go-gateway` | Go | GCP Cloud Run | API gateway — rate limiting, reverse proxy to all microservices |
| `infraportal` | React 19 / Vite / TypeScript | GitHub Pages | Portfolio site, admin dashboard, client portal |

#### Architecture diagram

```
  React/Vite UI (GitHub Pages)
        │
   Go API Gateway (rate limiting, reverse proxy)
        │
  Rust/Axum task-api  ──  Python AI Orchestrator (Claude + Gemini)
        │
  Domain microservices (Rust/Axum, PostgreSQL via Cloud SQL)
  accounts · contacts · activities · automation
  integrations · opportunities · reporting · search · audit

  Client Portal
  Rust projects-service (projects · milestones · deliverables · messages)
```

#### Key features

- AI goal planner — describe a goal, generate structured sub-tasks via LLM
- JWT auth with cross-service token validation (role-based: user / planner / admin)
- Admin dashboard — request audit logs, per-user activity, aggregated CRM metrics
- Full CI/CD via GitHub Actions — per-service Docker builds, automated deploys to Cloud Run
- Terraform IaC for GCP baseline: Cloud Run, Cloud SQL, Artifact Registry, Secret Manager

#### Tech

Rust Axum 0.8 · sqlx 0.8 · PostgreSQL · Python FastAPI · Go · Anthropic Claude API · Google Gemini API · React 19 · Vite · Tailwind CSS v3 · TypeScript · Terraform · GitHub Actions · Docker · OIDC (Workload Identity Federation)

---

### 2. [SOC 2 Baseline — Terraform Module](../microservices/terraform-soc2-baseline/)

Cloud-agnostic GCP + AWS Terraform module implementing 9 SOC 2 Type II controls
as reusable infrastructure code. Extracted from InfraPortal's security hardening
and designed to be forked.

#### Controls implemented

| Control | GCP | AWS |
|---------|-----|-----|
| CC6.1 — Logical access | Per-service service accounts, no owner/editor roles | Per-service IAM roles, resource-scoped ARNs |
| CC6.2 — Authentication | Workload Identity Federation (OIDC), no SA key files | OIDC role assumption only |
| CC6.3 — Privileged access | Minimum required roles only | Inline policies, no wildcard actions |
| CC6.7 — Secrets management | Secret Manager, SA-bound IAM | Secrets Manager, KMS CMK encryption |
| CC7.2 — System monitoring | Cloud Audit Logs + GCS sink | CloudTrail multi-region + S3 |
| CC7.3 — Incident detection | Cloud Logging alert skeleton | CloudWatch root login alarm |
| CC8.1 — Change management | `prevent_destroy` on secrets | S3 versioning + DynamoDB state lock |
| CC6.8 — Non-root containers | USER directive requirement documented | ECS task def `user: "65534"` |
| A1.2 — Availability | Cloud Run `min_instances`, Cloud SQL backups | Multi-AZ subnets, ECS `desired_count ≥ 1` |

**Tech:** Terraform · GCP · AWS · Secret Manager · Secrets Manager · KMS · CloudTrail · VPC · IAM · OIDC

---

### 3. [CI/CD Pipeline Template](../microservices/.github/workflows/deploy-pipeline.yml)

Cloud-agnostic GitHub Actions reference architecture for multi-environment
deployments. Extends InfraPortal's existing CI/CD with full promotion gates and
automated rollback on both GCP and AWS.

#### Promotion flow

```
test  →  deploy-staging (auto, OIDC)  →  ⏸ approval  →  deploy-prod (OIDC)
          ↓ health-check /health                         ↓ health-check /health
          ↓ rollback on failure                          ↓ rollback on failure
```

- **Environment-scoped OIDC** — staging and production each hold isolated credential sets; GitHub injects the correct set automatically
- **Manual approval gate** — production environment requires reviewer approval before deploy job runs
- **Automated rollback** — GCP via `gcloud run services update-traffic --to-revisions PREVIOUS=100`; AWS via `aws ecs update-service --task-definition <previous-ARN>`
- **Dockerfile lint** — blocks deploy if any service image is missing a `USER` directive (CC6.8)

**Tech:** GitHub Actions · GCP Cloud Run · AWS ECS / Fargate · OIDC · Rust · Python · Docker · Bash

---

### 4. [Observaboard — Django REST API](../observaboard/)

Webhook event ingestion and classification API demonstrating Django REST
Framework, Celery async workers, PostgreSQL full-text search, and dual
authentication (JWT + API key).

#### Architecture

```
External source  →  POST /api/ingest/  (API key auth)
                         │
                   Celery worker  →  classify(event)  →  FTS index update
                         │
               GET /api/events/search/?q=  (JWT auth)
               Django Admin  →  browse / manage events
```

#### Key features

- Webhook ingestion with API key authentication
- Celery async classification — assigns category (deployment / security / alert / metric / info) and severity (low / medium / high / critical) from raw payload
- PostgreSQL `SearchVectorField` + `GinIndex` — full-text search over event summaries
- Django Admin — browse, filter, and manage ingested events
- Dual auth — JWT (`djangorestframework-simplejwt`) for API consumers, API key for ingest sources

#### Tech

Django 5 · Django REST Framework · Celery · Redis · PostgreSQL · `djangorestframework-simplejwt` · Docker · Fly.io

---

### 5. [DynamoDB Medallion Pipeline Prototype](../dynamodb_prototype/)

Rust + Go prototype demonstrating exactly-once cloud audit log delivery via
DynamoDB conditional writes, with a live inspection dashboard and Go pipeline
monitor deployed on Fly.io.

#### Pipeline

```
Raw event (CloudTrail / GCP Cloud Logging / arbitrary JSON)
      │
   Bronze  →  stage#bronze#<uuid>      raw payload, immutable
      │
   Silver  →  stage#silver#<uuid>      normalised, typed, PII-safe
      │
    Gold   →  stage#gold#<uuid>        aggregated metrics, downstream-ready
      │
   Sink    →  Splunk HEC / analytics   configurable, skipped gracefully if absent
```

#### Components

| Binary / Service | Language | Role |
|-----------------|----------|------|
| `ingest` | Rust | Write raw event as Bronze record |
| `process_bronze` | Rust | Promote Bronze → Silver |
| `process_silver` | Rust | Promote Silver → Gold |
| `dashboard` | Rust / Axum | HTTP server — DynamoDB inspection APIs + admin UI |
| `go-pipeline-monitor` | Go | Pipeline stage counts + upstream service health checks |

#### Key features

- **Idempotent writes** — `begins_with(sk, "stage#<tier>#")` scan + conditional PutItem prevents duplicate processing
- **`/promote` endpoint** — advance any record Bronze → Silver → Gold via REST (`POST /promote`)
- **Go pipeline monitor** — parallel DynamoDB scans with paginated `Scan`, structured JSON error responses, CORS origin allowlist
- **Pluggable sink** — Splunk HEC with configurable timeout and retry
- **Security-hardened** — pipeline endpoints gated behind `require_admin`; OIDC CI migration; dev bypass removed
- **Contact form inbox** — portfolio contact form POSTs to `/api/contact`; messages stored in DynamoDB and readable in the admin dashboard (no third-party email service)

#### Tech

Rust async (Tokio) · `aws-sdk-dynamodb` · Axum 0.8 · Go 1.22 · AWS SDK for Go v2 · Single-table DynamoDB design · Docker · Fly.io · AWS SAM / CloudFormation

---

## Repository layout

```
portfolio/
├── observaboard/                         # Django REST API (Fly.io)
│   ├── observaboard/                     #   Django project (settings, urls, celery)
│   ├── events/                           #   App: models, views, tasks, serializers
│   ├── requirements.txt
│   ├── Dockerfile
│   └── fly.toml
├── microservices/                        # InfraPortal platform (submodule)
│   ├── accounts-service/                 #   Rust/Axum, PostgreSQL
│   ├── contacts-service/                 #     ↳ cross-service account validation
│   ├── activities-service/               #   Rust/Axum, PostgreSQL
│   ├── automation-service/               #     ↳ workflow rules
│   ├── integrations-service/             #     ↳ third-party hooks
│   ├── opportunities-service/            #     ↳ sales pipeline
│   ├── reporting-service/                #     ↳ aggregated reports
│   ├── search-service/                   #     ↳ cross-domain search
│   ├── audit-service/                    #     ↳ immutable CRM mutation log
│   ├── terraform-soc2-baseline/          #   Cloud-agnostic SOC 2 module
│   │   ├── modules/gcp/                  #     GCP sub-module (8 .tf files)
│   │   └── modules/aws/                  #     AWS sub-module (8 .tf files)
│   ├── docs/cicd-template/               #   CI/CD reference docs
│   │   └── scripts/                      #     health-check, rollback-gcp, rollback-aws
│   ├── .github/workflows/
│   │   ├── rust.yml                      #   Primary CI (test, audit, deploy)
│   │   └── deploy-pipeline.yml           #   Reference multi-env promotion template
│   └── scripts/
│       └── run-checks.ps1                #   Full microservices test runner (Windows)
├── backend-service/                      # task-api (Rust/Axum, Fly.io)
├── go-gateway/                           # Go API gateway (GCP Cloud Run)
├── projects-service/                     # Client portal data service (Rust/Axum, GCP Cloud Run)
├── infraportal/                          # React 19 UI + client portal (GitHub Pages)
├── auth-service/                         # Python JWT service
├── ai-orchestrator-service/              # Python / Claude + Gemini
├── event-stream-service/                 # Go SSE hub (Fly.io)
├── dynamodb_prototype/                   # DynamoDB medallion pipeline
│   ├── src/bin/                          #   Rust pipeline binaries + dashboard
│   ├── go-pipeline-monitor/              #   Go service (Fly.io)
│   ├── docs/                             #   Case study, OIDC setup guide
│   └── template.yaml                     #   AWS SAM / CloudFormation
├── agents/
│   └── productionizer/                   # Gemini 2.5 Flash autonomous coding agent
├── docs/                                 # ARCHITECTURE, CONTRIBUTING, ROADMAP, images
├── .devcontainer/                        # Codespaces / VS Code dev container
├── services.yaml                         # Source-of-truth service inventory
└── run_workspace_tests.sh                # Cross-repo workspace test runner
```

---

## Deployment summary

| App | Platform | URL |
|-----|----------|-----|
| infraportal | GitHub Pages | https://rodmen07.github.io/infraportal/ |
| auth-service | GCP Cloud Run | https://auth-service-5gcrg4oiza-uc.a.run.app |
| go-gateway | GCP Cloud Run | https://go-gateway-5gcrg4oiza-uc.a.run.app |
| projects-service | GCP Cloud Run | https://projects-service-5gcrg4oiza-uc.a.run.app |
| accounts-service | GCP Cloud Run | https://accounts-service-5gcrg4oiza-uc.a.run.app |
| contacts-service | GCP Cloud Run | https://contacts-service-5gcrg4oiza-uc.a.run.app |
| activities-service | GCP Cloud Run | https://activities-service-5gcrg4oiza-uc.a.run.app |
| automation-service | GCP Cloud Run | https://automation-service-5gcrg4oiza-uc.a.run.app |
| integrations-service | GCP Cloud Run | https://integrations-service-5gcrg4oiza-uc.a.run.app |
| opportunities-service | GCP Cloud Run | https://opportunities-service-5gcrg4oiza-uc.a.run.app |
| reporting-service | GCP Cloud Run | https://reporting-service-5gcrg4oiza-uc.a.run.app |
| search-service | GCP Cloud Run | https://search-service-5gcrg4oiza-uc.a.run.app |
| task-api-service | Fly.io | https://backend-service-rodmen07-v2.fly.dev |
| ai-orchestrator | Fly.io | https://ai-orchestrator-service-rodmen07.fly.dev |
| dashboard (Rust) | Fly.io | https://dynamodb-dashboard-rodmen07.fly.dev |
| observaboard | Fly.io | https://observaboard-rodmen07.fly.dev |
| event-stream-service | Fly.io | https://event-stream-service.fly.dev |
