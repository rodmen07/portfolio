# Copilot Instructions — Portfolio Repository

This repository contains two independent projects sharing a home directory. Future Copilot sessions should use this file as the primary reference, supplemented by project-specific CLAUDE.md files.

---

## Repository Structure

| Path | Purpose |
|------|---------|
| `Projects/Portfolio/` | Multi-service cloud engineering platform (16 services, Rust/Python/Go/TypeScript, GCP/Fly.io) |
| `Projects/new_game/` | Bevy ECS life-sim game, Rust Edition 2024, Browser-native (wasm) |
| `Projects/SpendSteward/` | DECOMMISSIONED 2026-07-21. Retired side project, hosted infra deleted, repo archived. Do not deploy or extend; see its DECOMMISSION.md |

When asked to work on code, confirm which project is in scope before proceeding.

---

## Portfolio: Build, Test, and Lint

### Using `just` (recommended)

```bash
just                    # List all available recipes
just test              # Run cross-repo workspace tests (writes test_results.json + test_logs/)
just lint              # Run pre-commit hooks on all files
just lint-staged       # Run pre-commit hooks on staged changes only
just rust-test <service>  # Test a single Rust service (e.g., just rust-test reporting-service)
```

### Without `just`

```bash
# Cross-repo workspace tests
bash ./run_workspace_tests.sh

# Pre-commit (requires: pip install pre-commit && pre-commit install)
pre-commit run --all-files
pre-commit run             # staged files only

# Single Rust service
cd microservices/<service>
AUTH_JWT_SECRET=dev-insecure-secret-change-me \
  TEST_DATABASE_URL=sqlite::memory: \
  cargo test
```

### Pre-commit hooks (automatic on commit)

`.pre-commit-config.yaml` enforces:
- **Rust:** cargo fmt (per-service, deeper linting in service CI)
- **Python:** ruff format + ruff lint
- **Go:** gofmt
- **Terraform:** terraform fmt
- **Node/TypeScript:** prettier (frontend-service, separate repo)
- **General:** trailing whitespace, merge conflict markers, JSON/YAML/TOML validation, Dockerfile USER directive (SOC 2 CC6.8)

---

## Portfolio: High-Level Architecture

### System Overview

16-service microservices platform deployed across **GCP Cloud Run (us-central1)** and **Fly.io**:

```
React 19 / Vite UI (GitHub Pages: infraportal)
        │
   Go API Gateway  ←  rate limiting, reverse proxy
        │
  Rust/Axum task-api  ──  Python AI Orchestrator (Claude + Gemini)
        │
  Rust/Axum domain services (PostgreSQL on Cloud SQL):
   accounts · contacts · activities · automation · integrations
   opportunities · reporting · search · audit · projects
```

**Non-Rust services:**
- **auth-service** — Python/FastAPI, JWT issuance, GitHub + Google OAuth
- **event-stream-service** — Go, SSE fan-out with ring-buffer replay
- **ai-orchestrator-service** — Python/FastAPI, internal-only, calls Anthropic Claude API
- **observaboard** — Django 5 + Celery, webhook ingestion, FTS, dual JWT/API-key auth
- **dynamodb_prototype** — Rust + Go, exactly-once DynamoDB medallion pipeline
- **agents/productionizer** — Gemini 2.5 Flash autonomous agent, opens daily PRs

**Infrastructure:**
- **Cloud SQL:** PostgreSQL 16 instance `microservices-489413:us-south1:microservices-pg`
- **Service inventory:** `services.yaml` (machine-readable, canonical source of truth)
- **Terraform SOC 2 baseline:** 9 SOC 2 Type II controls, cloud-agnostic (GCP + AWS)

---

## Portfolio: Rust Service Standard Pattern

### File Structure

All Rust services follow this layout (reference: `task-api-service`):

```
<service>/
  Cargo.toml
  migrations/
    0001_create_<table>.sql
  src/
    main.rs           # entrypoint: read env, init AppState, bind listener
    lib.rs            # #[path] declarations + pub use re-exports
    lib/
      app_state.rs    # PgPool (+ reqwest::Client if cross-service calls)
      auth.rs         # JWT validation (identical across all services)
      models.rs       # domain models, request/response DTOs, ApiError, HealthResponse
      router.rs       # build_router(), build_cors_layer()
      handlers/
        mod.rs        # pub mod declarations + pub use re-exports
        health.rs     # health() handler
        <resource>.rs # CRUD handlers
```

### lib.rs `#[path]` Declarations

Must use `#[path]` attribute to reference `src/lib/` instead of `src/`:

```rust
#[path = "lib/app_state.rs"]
pub mod app_state;
#[path = "lib/auth.rs"]
pub mod auth;
#[path = "lib/handlers/mod.rs"]
pub mod handlers;
#[path = "lib/models.rs"]
pub mod models;
#[path = "lib/router.rs"]
pub mod router;

pub use app_state::AppState;
pub use router::build_router;
```

Without `#[path]`, Rust looks for `src/app_state.rs`, not `src/lib/app_state.rs`.

### Dependency Versions (use these exactly)

```toml
axum = { version = "0.8", features = ["macros"] }
tower-http = { version = "0.6", features = ["cors", "trace"] }
sqlx = { version = "0.8", features = ["runtime-tokio-rustls", "postgres", "macros", "migrate"] }
jsonwebtoken = "8.3.0"
chrono = { version = "0.4", features = ["clock"] }
reqwest = { version = "0.12", default-features = false, features = ["json", "rustls-tls"] }
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
serde = { version = "1", features = ["derive"] }
uuid = { version = "1", features = ["v4", "serde"] }
tracing-subscriber = { version = "0.3", features = ["env-filter", "fmt"] }
```

### HTTP and Routing (Axum 0.8)

- **Path parameters** use `{id}` not `:id`: `.route("/api/v1/things/{id}", ...)`
- **Request extractor** is `Path<String>` for path params
- **Middleware** uses `from_fn` / `from_fn_with_state` from `axum::middleware`
- **Request type** is `axum::extract::Request` (not `http::Request<Body>`)
- **Status codes** use constants (`StatusCode::BAD_REQUEST`, etc.), never raw numbers

### Error Envelope

All errors return `{ code, message, details? }`:

```rust
#[derive(Serialize)]
pub struct ApiError {
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

// Usage
error_response(StatusCode::NOT_FOUND, "NOT_FOUND", "Resource not found")
```

### Authentication

All protected endpoints validate JWT in the handler directly (not middleware):

```rust
fn require_auth(headers: &HeaderMap) -> Result<(), Response> {
    let header_value = headers.get("Authorization").and_then(|v| v.to_str().ok());
    validate_authorization_header(header_value)
        .map(|_| ())
        .map_err(|err| error_response(StatusCode::UNAUTHORIZED, err.code(), err.message()))
}
```

**Auth environment variables:**
- `AUTH_JWT_SECRET` (default: `dev-insecure-secret-change-me`)
- `AUTH_JWT_ALGORITHM` (default: `HS256`; supports RS256/RS384/RS512/HS384/HS512)
- `AUTH_ISSUER` (default: `auth-service`)

The `auth.rs` module is identical across all services — copy verbatim.

### Database Pattern

```rust
// app_state.rs
pub async fn from_database_url(database_url: &str) -> Result<Self, sqlx::Error> {
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(database_url)
        .await?;
    sqlx::migrate!("./migrations").run(&pool).await?;
    Ok(Self { pool })
}
```

**Conventions:**
- **IDs** are `TEXT` (UUID v4 strings), never integer autoincrement
- **Timestamps** are `TEXT` in `"%Y-%m-%dT%H:%M:%SZ"` format via `chrono::Utc`
- **FromRow** derive on domain models; SELECT column order must match struct field order
- **Placeholders** are numbered (`$1`, `$2`, ...) — not `?` (SQLite syntax)
- **Upsert** uses `INSERT ... ON CONFLICT DO NOTHING` (not `INSERT OR IGNORE`)
- **Migration timestamps:** `DEFAULT (to_char(timezone('UTC', now()), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'))`
- **Default DATABASE_URL:** `postgres://postgres:postgres@localhost:5432/<service-name>` (local)
- **Cloud SQL (production):** `postgres://user:pass@/<dbname>?host=/cloudsql/PROJECT:REGION:INSTANCE`

### Cross-Service Calls

When a service validates a foreign key from another service (e.g., contacts → accounts):

1. Add `reqwest::Client` to `AppState`
2. Read `ACCOUNTS_SERVICE_URL` (or equivalent) from env
3. **Fail-open** if the env var is not set (local dev without all services running)
4. Pass the caller's Bearer token through to the upstream service

### CORS

`ALLOWED_ORIGINS` env var — comma-separated list. Empty = no cross-origin. `*` = permissive.

---

## Portfolio: Key Conventions

### services.yaml (Authoritative Inventory)

`services.yaml` is the machine-readable source of truth for the service topology. When `docs/ARCHITECTURE.md` and `services.yaml` disagree, **services.yaml wins**.

### Git Submodule Workflow

Each service is an independently-versioned repository (git submodule):

```bash
git submodule update --init --recursive        # after clone
git submodule update --remote --recursive      # update to latest
git submodule status --recursive               # inspect status
cd <submodule> && git pull origin main && cd .. && git add <submodule>
git commit -m "Update <submodule> pointer"
```

### Environment Setup

```bash
cp .env.example .env    # then fill in real values for integrations you plan to exercise
```

Local-only test runs typically only need:
- `AUTH_JWT_SECRET=dev-insecure-secret-change-me`
- `TEST_DATABASE_URL=sqlite::memory:`

### GCP Cloud Run Deployment

- **CI/CD:** OIDC/WIF GitHub Actions, deploys to Artifact Registry
- **Database:** Cloud SQL PostgreSQL 16, instance `microservices-489413:us-south1:microservices-pg`
- **Region:** us-central1 (GCP), Fly.io for task-api, ai-orchestrator, event-stream, observaboard, DynamoDB
- **Configuration:** GCP_PROJECT_ID, GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_SERVICE_ACCOUNT (GitHub secrets/variables)
- **Per-service secrets:** ACCOUNTS_DB_URL, CONTACTS_DB_URL, etc. (GCP Secret Manager)
- **Roles required:** Artifact Registry Writer, Cloud Run Developer, Cloud SQL Client, Secret Manager Secret Accessor

---

## Portfolio: Testing Strategy

### Local Testing (SQLite in-memory)

For rapid iteration without database setup:

```bash
cd microservices/<service>
TEST_DATABASE_URL=sqlite::memory: \
  AUTH_JWT_SECRET=dev-insecure-secret-change-me \
  cargo test
```

SQLite tests run synchronously, no migrations needed. Good for unit/integration tests of handler logic.

### Integration Tests (PostgreSQL)

For testing cross-service contracts and real database behavior:

```bash
# Start local PostgreSQL (via docker-compose in microservices/)
cd microservices && docker-compose up -d postgres

# Run tests against real database
cd <service>
TEST_DATABASE_URL=postgres://postgres:postgres@localhost:5432/<service> \
  AUTH_JWT_SECRET=dev-insecure-secret-change-me \
  cargo test
```

Migrations are auto-run from `migrations/` folder; no manual setup required.

### Testing Cross-Service Calls

Mock or disable upstream service calls in tests by not setting env vars (fail-open pattern):

```bash
# Omit ACCOUNTS_SERVICE_URL; contacts-service will skip cross-service validation
cargo test
```

For explicit integration tests, override with `http://localhost:3010` (local service).

### Health Check Endpoint

Every service exposes `GET /health`:

```bash
curl http://localhost:3010/health
# { "status": "healthy" }
```

Use this to verify service startup and readiness in CI.

---

## Portfolio: Database Migrations

### Migration File Naming

Migrations live in `<service>/migrations/` and follow a numeric prefix pattern:

```
0001_create_accounts.sql
0002_add_tenant_id_index.sql
```

Start at `0001` for each service. Prefix with zero-padded numbers.

### Migration Content (PostgreSQL)

All migrations target PostgreSQL 16 (Cloud SQL). Use:

```sql
CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (to_char(timezone('UTC', now()), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
  updated_at TEXT NOT NULL DEFAULT (to_char(timezone('UTC', now()), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'))
);
```

Key conventions:
- **Timestamps** are `TEXT`, not `TIMESTAMP` — ISO 8601 format
- **UUIDs** are `TEXT`, not native UUID type
- **Default values** use `to_char(timezone(...))` for consistency across services
- **No migration rollback** — migrations are append-only; undo via new migration

### Running Migrations Locally

Migrations auto-run on service startup via `sqlx::migrate!("./migrations").run(&pool)`.

To test migrations without starting the service:

```bash
cd microservices/<service>
sqlx database create --database-url $TEST_DATABASE_URL
sqlx migrate run --database-url $TEST_DATABASE_URL
```

### Production Migrations

Cloud SQL is managed by GCP. Migrations run automatically when services deploy via Cloud Run. **No manual intervention needed.**

---

## Portfolio: Frontend Integration

### infraportal (React 19 / Vite)

The React UI is in `infraportal/` and deploys to GitHub Pages (`rodmen07.github.io/infraportal`).

**Connection to backend:**

- **Dev:** Points to `localhost:3010` (go-gateway default)
- **Production:** Points to `https://accounts-service-5gcrg4oiza-uc.a.run.app` (via go-gateway)
- **Env var:** `VITE_API_BASE_URL` (set during build)

**Building locally:**

```bash
cd infraportal
npm install
npm run dev          # http://localhost:5173
npm run build        # dist/ for GitHub Pages deploy
```

**CORS:** Infraportal is on a different origin; services must have `ALLOWED_ORIGINS=https://rodmen07.github.io` set in prod.

---

## Portfolio: Observaboard (Django + Celery)

Non-Rust service; distinct from the Rust/Axum microservices.

### Architecture

- **Framework:** Django 5 + Django REST Framework
- **Queue:** Celery with Redis backend
- **Search:** PostgreSQL full-text search
- **Auth:** Dual JWT + API-key per-account

### Key Patterns

**Webhook ingestion:**
```python
POST /api/v1/webhooks/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{ "provider": "stripe", "event_type": "charge.succeeded", "payload": {...} }
```

**Celery tasks:**

Tasks run async and log to the same PostgreSQL database. Check logs via Django admin or task status endpoint.

**FTS Queries:**

```python
Model.objects.filter(
    body__search='search term'
).order_by('-ts_rank')
```

---

## Portfolio: Database Selection — PostgreSQL vs. SQLite

### Use SQLite for:

- **Unit/integration tests** — `TEST_DATABASE_URL=sqlite::memory:` (no setup, fast)
- **Local development without Docker** — Quick iteration loop
- **Temporary debugging** — Rapid test writes

### Use PostgreSQL for:

- **Integration tests requiring real database behavior** — Indexes, constraints, full-text search
- **Production deployments** — All Cloud Run services use Cloud SQL PostgreSQL 16
- **Cross-service contract testing** — Ensures schema compatibility
- **Performance profiling** — SQLite has different query plans

**Trade-off:** SQLite tests are 10–100× faster but miss schema/constraint bugs caught by PostgreSQL.

---

## Portfolio: Common Debugging Scenarios

### JWT Validation Failure

**Symptom:** `401 Unauthorized` on every protected endpoint

**Causes:**
1. `AUTH_JWT_SECRET` mismatch (dev token signed with different secret)
2. `Authorization: Bearer <token>` header missing or malformed
3. Token expired (check `exp` claim in JWT payload)

**Debug:**
```bash
# Decode JWT (no verification)
echo $TOKEN | cut -d'.' -f2 | base64 -d | jq .

# Check secret matches
echo "AUTH_JWT_SECRET=$AUTH_JWT_SECRET"

# Try with fresh token from auth-service
curl -X POST http://localhost:3001/auth/token ...
```

### CORS Rejection

**Symptom:** Browser console: `Access to XMLHttpRequest blocked by CORS policy`

**Causes:**
1. `ALLOWED_ORIGINS` not set or mismatch (infraportal on `https://`, backend on `http://`)
2. Credentials mode mismatch (frontend sends `credentials: 'include'` but backend doesn't allow)

**Debug:**
```bash
# Check service env
curl -i http://localhost:3010/health
# Look for Access-Control-Allow-Origin header

# Set ALLOWED_ORIGINS explicitly
export ALLOWED_ORIGINS="http://localhost:5173,https://rodmen07.github.io"
cargo run
```

### Database Connection Refused

**Symptom:** `Error: connect: connection refused` or `SQLSTATE[08001]`

**Causes:**
1. PostgreSQL not running (local or Cloud SQL inaccessible)
2. `DATABASE_URL` or `TEST_DATABASE_URL` incorrect
3. Network/firewall blocking port 5432

**Debug:**
```bash
# Test local PostgreSQL
psql postgres://postgres:postgres@localhost:5432/test

# For Cloud SQL, check IAM + workload identity
gcloud sql connect microservices-pg --user=postgres

# Override database URL temporarily
export TEST_DATABASE_URL=sqlite::memory:
cargo test
```

### Cross-Service Call Timeout

**Symptom:** `Error: request timeout` in contacts-service when validating account

**Causes:**
1. Upstream service (accounts-service) not running
2. `ACCOUNTS_SERVICE_URL` set to wrong hostname/port
3. Network latency or firewall

**Debug:**
```bash
# Check if accounts-service is running
curl http://localhost:3010/health

# Verify URL env var
echo $ACCOUNTS_SERVICE_URL

# If service not running, disable validation (fail-open for local dev)
unset ACCOUNTS_SERVICE_URL
cargo test
```

### Schema Mismatch on Deploy

**Symptom:** Service panics on startup: `column "foo" not found`

**Causes:**
1. Migration not run before deploy (rare; auto-migrations should catch this)
2. Stale code reading renamed/deleted column

**Debug:**
```bash
# Check migrations are in git
ls microservices/<service>/migrations/

# Inspect Cloud SQL schema
gcloud sql connect microservices-pg --user=postgres
\d <table>

# Local test with real schema
TEST_DATABASE_URL=postgres://... cargo test
```

---

## new_game: Build, Test, and Lint

### Native Desktop

```bash
cargo run                     # native
cargo run --release
cargo test
cargo clippy -- -D warnings   # must pass before submitting
cargo fmt
```

### Browser (Primary Target)

```bash
rustup target add wasm32-unknown-unknown
cargo install trunk --locked
trunk serve --release          # http://127.0.0.1:8080
trunk build --release --public-url /new_game/   # deploy
```

**Linux prerequisites:**
```bash
libudev-dev libasound2-dev libxkbcommon-dev
```

---

## new_game: High-Level Architecture

**Bevy 0.15 Edition 2024** real-time 2D life-sim. ECS architecture with global state in Resources and local player state on Components.

```
src/
├── main.rs        # App entry, system scheduling
├── components.rs  # ECS components (LocalPlayer, TypingOverlay*, Skill*, Furnishings…)
├── constants.rs   # All gameplay tuning constants, zone bounds
├── resources.rs   # Shared Resources and SystemParam bundles
├── setup.rs       # World/NPC/HUD spawn
├── menu.rs        # Menu / Pause / Settings screens
├── save.rs        # JSON persistence + GameStartKind
├── audio.rs       # SFX and ambient audio
├── settings.rs    # config.toml load/save
└── systems/       # player, collision, npc, interaction, stats, time,
                   # goals, hud, visual, narrative, vehicle, crisis, festival
```

---

## new_game: Key Conventions

### Deterministic RNG

Day-seeded LCG; use seeded logic for crises/events so tests are reproducible.

### Bevy Wasm Constraint

Overlapping `Query<Transform>` access causes a **B0001 startup panic on wasm**. All queries must be disjoint with `With`/`Without` filters.

### Deprecated Pattern

`get_single_mut()` is deprecated — use `iter_mut().next()` pattern throughout.

### SystemParam Bundles

Keep large systems under Bevy's parameter count limit by bundling related params.

### Save Data

`SaveData` must mirror all gameplay state. When adding new persistent fields, also update `sample_save()` in tests (T-04 audit rule).

### Typing Overlay

`TypingOverlay*` components drive the full-screen word-challenge UI. Actions auto-confirm when the typed word is complete.

### Wasm-Specific

- Settings and save data use browser `localStorage` instead of config.toml / save.json
- Audio requires a user-gesture event to resume the AudioContext (browser autoplay policy)
- CI includes a wasm startup smoke test — a **B0001 query conflict fails the deploy check**

---

## Detailed Project Documentation

For deeper guidance on each project, consult:

- **Portfolio microservices:** `Projects/Portfolio/microservices/CLAUDE.md` (JWT auth, database patterns, deployment, release checklist)
- **new_game:** Referenced sections above (Bevy ECS patterns, deterministic RNG, wasm constraints)

---

## Before You Start

1. **Clarify scope:** Ask which project is in focus (Portfolio vs. new_game)
2. **Read project CLAUDE.md:** If working on microservices, read `microservices/CLAUDE.md` first
3. **Check services.yaml:** For Portfolio topology questions, consult `services.yaml` (not just docs)
4. **Environment:** Set `AUTH_JWT_SECRET` and `TEST_DATABASE_URL` for local Rust tests
5. **Pre-commit hooks:** Run `just lint` before committing (or `pre-commit run` if `just` unavailable)
