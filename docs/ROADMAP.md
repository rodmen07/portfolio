# Roadmap

Shipped versions, most recent first. Published means all release locations
were updated (see microservices/CLAUDE.md, Release Locations); lifecycle is
Planned -> Implemented -> Published.

Last synchronized: 2026-05-17

## v1.15 - Deployment Safety, SLO Monitoring & Distributed State ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.15.1 | go-gateway Cloud Run canary rollout workflow - deploys revision with no traffic, runs smoke gate, shifts to 10/90 split, then promotes to 100 percent on success | ✅ Published |
| v1.15.2 | smoke-test.sh deployment gate - validates /health body contract and /health/upstreams reachability with bounded retries | ✅ Published |
| v1.15.3 | reusable rollback composite action - restores 100 percent traffic to stable revision on canary smoke failure and posts rollback summary | ✅ Published |
| v1.15.4 | terraform/slos module - custom monitoring service plus availability and latency SLO resources for go-gateway | ✅ Published |
| v1.15.5 | SLO burn-rate alert policies - fast and slow burn alerts with configurable notification channel | ✅ Published |
| v1.15.6 | configurable uptime checks - per-service uptime checks with sustained-failure alert policies | ✅ Published |
| v1.15.7 | terraform/memorystore module - provisions Redis and exports REDIS_URL with optional Secret Manager write path | ✅ Published |
| v1.15.8 | distributed Redis-backed rate limiter - go-gateway uses INCR+EXPIRE fixed windows across instances when REDIS_URL is configured | ✅ Published |
| v1.15.9 | gateway response cache - in-process LRU cache for read endpoints with per-subject keying and X-Cache MISS/HIT headers | ✅ Published |
| v1.15.10 | patch notes and release wrap-up - patch notes and README updated; validations rerun before publish | ✅ Published |

## v1.14 - Security Depth, Cost Efficiency & E2E Quality ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.14.1 | go-gateway security response headers middleware (HSTS, nosniff, DENY, strict referrer policy, CSP, Permissions-Policy) | ✅ Published |
| v1.14.2 | auth-service refresh token rotation with replay protection | ✅ Published |
| v1.14.3 | go-gateway scanner path blocking middleware for common probe paths | ✅ Published |
| v1.14.4 | Cloud Armor WAF support in go-gateway-ha module | ✅ Published |
| v1.14.5 | Infracost estimate comments in Terraform PR workflow | ✅ Published |
| v1.14.6 | BigQuery daily aggregate scheduled query in pubsub-ingest module | ✅ Published |
| v1.14.7 | go-gateway /health/upstreams fan-out endpoint | ✅ Published |
| v1.14.8 | Cloud Run gen2 plus concurrency tuning in gateway deploy workflow | ✅ Published |
| v1.14.9 | go-gateway circuit breaker plus retry transport | ✅ Published |
| v1.14.10 | auth-service integration test suite | ✅ Published |
| v1.14.11 | go-gateway integration test suite | ✅ Published |
| v1.14.12 | patch notes, README, and final publish commit | ✅ Published |

## v1.13 - Production Hardening, IaC Completeness & Observaboard Depth ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.13.1 | JWT middleware unit tests in go-gateway | ✅ Published |
| v1.13.2 | RS256 JWT support in go-gateway and JWKS endpoint in auth-service | ✅ Published |
| v1.13.3 | structured slog logging in go-gateway | ✅ Published |
| v1.13.4 | Terraform apply workflow with PR plan comments | ✅ Published |
| v1.13.5 | Terraform drift detection workflow with issue creation | ✅ Published |
| v1.13.6 | deploy workflow wiring for AUTH_JWT_SECRET | ✅ Published |
| v1.13.7 | dead-letter replay script for pubsub-ingest | ✅ Published |
| v1.13.8 | BigQuery analytics sink for pubsub-ingest | ✅ Published |
| v1.13.9 | ingest spike alert policy for pubsub-ingest | ✅ Published |

## v1.12 - IaC Root Module, JWT Auth at Gateway & CI/CD ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.12.1 | terraform/envs/prod root module wiring with GCS backend and aggregated outputs | ✅ Published |
| v1.12.2 | go-gateway JWT auth middleware with health/auth route bypass | ✅ Published |
| v1.12.3 | go-gateway CI workflow and Terraform lint workflow | ✅ Published |
| v1.12.4 | dead-letter Cloud Monitoring alert in pubsub-ingest module | ✅ Published |

## v1.11 - Multi-Region HA, Cloud SQL Read Replica & Pub/Sub Ingest ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.11.1 | multi-region go-gateway behind global HTTPS load balancer with serverless NEGs and HTTP->HTTPS redirect | ✅ Published |
| v1.11.2 | Cloud SQL cross-region read replica module plus reporting/search read-path wiring | ✅ Published |
| v1.11.3 | event-driven batch path via pubsub-ingest module plus go-gateway observer publish path | ✅ Published |

## v1.10 - Gateway Rate Limiting ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.10.0 | go-gateway per-client-IP token-bucket rate limiting with route tiers and headers | ✅ Published |

## v1.9 - Distributed Tracing & Observability ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.9.0 | OpenTelemetry integration across services and security fix for rustls-webpki | ✅ Published |

## v1.8 - Real-Time Feedback Loop ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.8.0 | observaboard stream publisher to event-stream-service with short-lived JWT and deploy wiring | ✅ Published |

## v1.7 - CRM Event Pipeline ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.7.0 | go-gateway mutation observer and observaboard ingest integration | ✅ Published |

## v1.6 - Observability & Compliance ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.6.0 | observaboard Cloud Tasks callback flow and SOC 2 CC9.2 module | ✅ Published |

## v1.5 - DB Migration & Live Events ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.5.0 | backend-service SQLite to PostgreSQL migration and CRM notification SSE bell | ✅ Published |

## v1.4 - Cloud Consolidation ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.4.0 | Fly.io to GCP Cloud Run migration for ai-orchestrator-service and event-stream-service | ✅ Published |

## v1.3 - Autonomous Operations ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.3.1 | Productionizer autonomous improvement cycle | ✅ Published |
| v1.3.2 | client portal dashboard expansion - deliverable effort tracking, curated project links, progress updates, and Gmail sync support | ✅ Published |
| v1.3.2 | client portal dashboard expansion: deliverable effort tracking, curated project links, progress updates, and Gmail sync support | ✅ Published |

## v1.2 - Operational Maturity ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.2.1 | Data export pipeline | ✅ Published |
| v1.2.2 | Audit trail and compliance service | ✅ Published |
| v1.2.3 | Portfolio observability integrations | ✅ Published |
| v1.2.4 | resilience and testing expansion | ✅ Published |

## v1.1 - Developer Experience & Portfolio Quality ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.1 | workspace CI/CD runner pipeline | ✅ Published |
| v1.1.1 | Gemini API integration endpoints and UI toggle | ✅ Published |
| v1.1.2 | documentation and Dockerfile narrative corrections | ✅ Published |
| v1.1.3 | activities-service cross-service validation | ✅ Published |

## v1.0 - Client Portal ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v1.0.1 | projects-service client portal API | ✅ Published |
| v1.0.2 | go-gateway deployment to Cloud Run | ✅ Published |
| v1.0.3 | 11-service Cloud Run migration with OIDC and Secret Manager | ✅ Published |
| v1.0.4 | GitHub and Google OAuth flows for client portal | ✅ Published |
| v1.0.5 | admin provisioning UI for project management | ✅ Published |

## v0.5 - Platform Completeness ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v0.5.1 | reporting-service production upgrade | ✅ Published |
| v0.5.2 | search-service production upgrade | ✅ Published |
| v0.5.3 | activities-service production upgrade | ✅ Published |
| v0.5.4 | automation-service production upgrade | ✅ Published |
| v0.5.5 | integrations-service production upgrade | ✅ Published |
| v0.5.6 | opportunities-service production upgrade | ✅ Published |

## v0.4 - Language Breadth & AI Depth ✅ Complete

| Sub-version | Feature | Status |
|-------------|---------|--------|
| v0.4.1 | AI consulting feature | ✅ Published |
| v0.4.2 | Django REST API observaboard | ✅ Published |
| v0.4.3 | Go service addition | ✅ Published |
| v0.4.4 | frontend UI expansion across CRM and observability pages | ✅ Published |

---

## Planned next (PR-ready)

- v1.16.0 - source-of-truth synchronization hardening:
  - keep README, ROADMAP, and patch notes aligned via automated checks
  - keep release chronology synchronized on every release PR
- v1.16.1 - production enablement of shipped gateway performance features:
  - staged enablement of Redis-backed rate limiting
  - staged enablement of gateway response caching
- v1.17.0 - reliability verification expansion:
  - automated HA failover drills and rollback drills
  - broader smoke-test coverage for auth and critical upstream dependencies
- v1.17.1 - API contract layer:
  - publish OpenAPI specs from Go, Rust, and FastAPI services
  - generate typed clients for infraportal and enforce contract drift checks
- v1.18.0 - platform DX and differentiation:
  - shared Rust utility crate for auth, request-id, and observability helpers
  - infractl CLI for health/canary/rollback workflows
  - one WASM-powered domain logic demo in infraportal
