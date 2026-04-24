# Roadmap

Shipped versions, most recent first. **Published** means all release locations
were updated (see `microservices/CLAUDE.md` § Release Locations); the lifecycle
is **Planned → Implemented → Published**.

## v1.3 — Autonomous Operations ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.3.1 | Productionizer agent — Gemini 2.5 Flash autonomous agent runs daily, opens PRs to improve Rust microservices (structured logging, dynamic health checks, error details, audit error handling, test coverage) | ✅ Published |

## v1.2 — Operational Maturity ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.2.1 | Data export pipeline — bulk CSV/JSON export from reporting-service; admin export modal | ✅ Published |
| v1.2.2 | Audit trail & compliance — new `audit-service` (Rust/Axum), immutable CRM mutation log, admin audit page | ✅ Published |
| v1.2.3 | Portfolio observability — CRM services emit events to Observaboard; admin service health dashboard | ✅ Published |
| v1.2.4 | Service resilience & testing — integration tests for all 11 services, k6 load testing, chaos engineering runbook | ✅ Published |

## v1.1 — Developer Experience & Portfolio Quality ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.1   | CI/CD pipeline — two-stage runner image build/test across full workspace | ✅ Published |
| v1.1.1 | Gemini API integration — `/consult/gemini` + `/consult/gemini/stream` endpoints; Claude/Gemini toggle in frontend | ✅ Published |
| v1.1.2 | Portfolio narrative fixes — all Dockerfiles cleaned of SQLite deps; all docs corrected to PostgreSQL (Cloud SQL) | ✅ Published |
| v1.1.3 | activities-service cross-service validation — account_id and contact_id validated on create (matches contacts-service pattern) | ✅ Published |

## v1.0 — Client Portal ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.0.1 | `projects-service` — Rust/Axum client portal API (projects, milestones, deliverables) | ✅ Published |
| v1.0.2 | `go-gateway` — Go API gateway deployed to GCP Cloud Run | ✅ Published |
| v1.0.3 | GCP Cloud Run migration — 11 services (OIDC + WIF, Artifact Registry, Secret Manager) | ✅ Published |
| v1.0.4 | OAuth flows — GitHub + Google client portal sign-in with client-role JWT | ✅ Published |
| v1.0.5 | Admin provisioning UI — create projects, milestones, deliverables; assign to client users | ✅ Published |

## v0.5 — Platform Completeness ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v0.5.1 | reporting-service production upgrade (PostgreSQL, JWT auth, saved report CRUD, /dashboard) | ✅ Published |
| v0.5.2 | search-service production upgrade (cross-domain fan-out search, write-through indexing) | ✅ Published |
| v0.5.3 | activities-service production upgrade (PostgreSQL, JWT auth, CRUD) | ✅ Published |
| v0.5.4 | automation-service production upgrade (PostgreSQL, JWT auth, workflow rules) | ✅ Published |
| v0.5.5 | integrations-service production upgrade (PostgreSQL, JWT auth, connection registry) | ✅ Published |
| v0.5.6 | opportunities-service production upgrade (PostgreSQL, JWT auth, stage tracking) | ✅ Published |

## v0.4 — Language Breadth & AI Depth ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v0.4.1 | AI Consulting Feature | ✅ Published |
| v0.4.2 | Django REST API (`observaboard`) | ✅ Published |
| v0.4.3 | Go Service | ✅ Published |
| v0.4.4 | Frontend UI Expansion — CRM CRUD, Live Feed, Search, Reports, Observaboard pages | ✅ Published |

---

## Considered for future versions

These are sketches, not commitments. Listed here so contributors and reviewers
can see the direction.

- **v1.4 — Cost & FinOps.** Cloud Run min-instance tuning, budget alerts via
  Terraform, a Grafana dashboard for per-service cost.
- **v1.5 — Multi-region / HA.** Promote `go-gateway` (or another well-bounded
  service) to multi-region Cloud Run with a global load balancer; document
  failover.
- **v1.6 — Event-driven core.** Replace some HTTP calls with Pub/Sub or NATS;
  the SSE hub already proves the pattern.
- **Distributed tracing.** OpenTelemetry → Tempo / Jaeger / Cloud Trace; start
  by propagating `traceparent` from `go-gateway`.
- **Shared `infraportal-common` crate** for JWT validation, request-id,
  logging, metrics, and error mapping across the Rust services.
- **OpenAPI / gRPC contracts.** Publish per-service specs (utoipa for Axum,
  FastAPI auto-gen, swag for Go) into a shared `contracts/` submodule and
  generate typed clients for the React app.
- **WebAssembly demo.** Compile one Rust service's domain logic to WASM and
  embed it in the React UI.
- **`infractl` CLI.** Rust + clap wrapper around `go-gateway` for ops tasks.
- **Public Postman/Bruno collection** for the gateway, so visitors can poke
  the live deployments.
- **Status page** via Upptime — pure GitHub Actions, no infra.
