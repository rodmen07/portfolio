# Portfolio

A collection of production-grade software engineering projects demonstrating Rust, Python, and TypeScript across cloud-native architectures.

---

## Projects

### 1. [TaskForge — Microservices Platform](./microservices/)

A fully deployed multi-service task management ecosystem. Nine independently deployed services communicate over HTTP with JWT-protected APIs and a React frontend.

**Live site:** https://rodmen07.github.io/frontend-service/

#### Architecture

```
  React/Vite UI (GitHub Pages)
        |
  Rust/Axum task-api (Cloud Run / Fly.io)
        |                    |
  Python AI Orchestrator   Python Auth Service
        |
  Domain microservices (Rust/Axum, SQLite)
  accounts · contacts · activities · automation
  integrations · opportunities · reporting · search
```

#### Services

| Service | Language | Role |
|---|---|---|
| `task-api-service` | Rust / Axum | Core task CRUD, AI planner proxy, admin metrics, audit log |
| `accounts-service` | Rust / Axum | Account and tenant domain |
| `contacts-service` | Rust / Axum | Contact and lead domain, cross-service account validation |
| `activities-service` | Rust / Axum | Activity tracking |
| `automation-service` | Rust / Axum | Automation rules |
| `integrations-service` | Rust / Axum | Third-party integration hooks |
| `opportunities-service` | Rust / Axum | Sales opportunity domain |
| `reporting-service` | Rust / Axum | Aggregated reports |
| `search-service` | Rust / Axum | Cross-domain search |
| `ai-orchestrator-service` | Python / FastAPI | LLM-backed goal-to-task planner (Claude API via OpenRouter) |
| `auth-service` | Python / FastAPI | JWT issuance, verification, Decap CMS GitHub OAuth |
| `frontend-service` | React 19 / Vite / TypeScript | Kanban board, AI planner UI, admin dashboard, CMS integration |

#### Key features

- **Kanban board** with drag-and-drop task management
- **AI goal planner** — describe a goal, generate structured sub-tasks via LLM
- **JWT auth** — role-based access (user / planner / admin)
- **Admin dashboard** — request audit logs, per-user activity, aggregated metrics
- **Story-point gamification** — progression system tied to task completion
- **Decap CMS** — browser-based content editing backed by GitHub
- **Load testing** — k6 harness with latency and error-rate thresholds
- **Terraform** — full IaC for GCP Artifact Registry, Cloud Run, and secrets

#### Tech highlights

- Rust Axum 0.8, sqlx 0.8 (compile-time SQL), SQLite, jsonwebtoken
- Python FastAPI, Anthropic Claude API
- React 19, Vite, Tailwind CSS v3, TypeScript strict mode
- GitHub Actions CI (fmt, clippy, tests, deploy)
- Deployed on Fly.io (backend services) and GitHub Pages (frontend)

---

### 2. [DynamoDB Medallion Pipeline Prototype](./dynamodb_prototype/)

A Rust prototype demonstrating an idempotent CloudTrail-style event ingestion pipeline backed by AWS DynamoDB, with optional Splunk HEC forwarding and a live inspection dashboard.

#### Pipeline

```
Raw JSON event
      |
   Bronze  →  stage#bronze       (raw payload stored in DynamoDB)
      |
   Silver  →  stage#silver       (normalised event shape)
      |
    Gold   →  stage#gold         (derived risk metric + downstream routing)
      |
   Sink    →  Splunk HEC / analytics (optional, configurable)
```

All stages write to a single DynamoDB table using `pk = <event_id>` and `sk = stage#<name>`. Idempotency state is tracked at `sk = state`.

#### Components

| Binary | Role |
|---|---|
| `run_pipeline` | End-to-end medallion flow (Bronze → Silver → Gold) |
| `ingest` | Write raw event as Bronze record |
| `process_bronze` | Promote Bronze → Silver |
| `process_silver` | Promote Silver → Gold |
| `dashboard` | Axum HTTP server — serves static UI + DynamoDB-backed inspection APIs |

#### Key features

- **Idempotent writes** — deterministic sort keys and conditional expressions prevent duplicate processing
- **Pluggable sink** — Splunk HEC forwarding with configurable timeout and retry; skipped gracefully when credentials are absent
- **Dashboard** — containerised Axum service (port 8080) for live event inspection
- **SAM / CloudFormation** — `template.yaml` for Lambda container deployment
- **OIDC setup guide** — docs for keyless CI-to-AWS authentication

#### Tech highlights

- Rust async (Tokio), `aws-sdk-dynamodb`, `reqwest`, Axum 0.6
- Single-table DynamoDB design with stage-prefixed sort keys
- Docker + AWS SAM for Lambda and ECS/Fargate deployment
- Deployable to Cloud Run, ECS/Fargate, or AWS Lambda containers

---

## Repository Layout

```
Portfolio/
├── microservices/          # TaskForge multi-service platform
│   ├── accounts-service/
│   ├── contacts-service/
│   ├── activities-service/
│   ├── automation-service/
│   ├── integrations-service/
│   ├── opportunities-service/
│   ├── reporting-service/
│   ├── search-service/
│   ├── standalones/
│   │   ├── backend-service/        # task-api-service
│   │   ├── frontend-service/       # React UI
│   │   ├── auth-service/           # Python JWT service
│   │   └── ai-orchestrator-service/ # Python LLM planner
│   └── terraform/                  # GCP infrastructure
└── dynamodb_prototype/     # DynamoDB medallion pipeline
    ├── src/                # Rust pipeline + dashboard source
    ├── docs/               # ML pipeline case study, OIDC setup
    └── template.yaml       # AWS SAM / CloudFormation
```
