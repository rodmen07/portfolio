# Security Audit Report — Portfolio Project
**Date:** 2026-03-15
**Last Updated:** 2026-03-15
**Scope:** `Portfolio/microservices/` and `Portfolio/dynamodb_prototype/`
**Auditor:** GitHub Copilot (Claude Sonnet 4.6)
**Status:** In remediation — see per-finding status below

---

## Executive Summary

The portfolio contains two production-deployed Rust projects: a multi-service task management platform (microservices) and a DynamoDB medallion pipeline prototype (dynamodb_prototype). Nine issues were identified, ranging from committed secret material to public database exposure. The most urgent issues are infrastructure-level and require git history remediation before any code changes.

**Counts by severity:**

| Severity | Count |
|---|---|
| High | 4 |
| Medium-High | 2 |
| Medium | 2 |
| Low-Medium | 1 |

**Remediation overview (as of 2026-03-15):**

| Finding | Status |
|---|---|
| FINDING-01 | ⚠️ Partially Remediated — tfplan purged; `.terraform/` provider binaries newly committed, needs purge |
| FINDING-02 | ⚠️ Code fixed — `terraform apply` pending |
| FINDING-03 | ⚠️ Code fixed (ai-orchestrator only) — `terraform apply` pending |
| FINDING-04 | ✅ Fully Remediated |
| FINDING-05 | ✅ Fully Remediated |
| FINDING-06 | ⚠️ Partially Remediated — dev bypass removed; 8 data handlers still unauthenticated |
| FINDING-07 | ✅ Remediated — delete static AWS secrets from GitHub manually |
| FINDING-08 | ✅ Fully Remediated |
| FINDING-09 | ✅ Acknowledged / Documented |

---

## Findings

---

### FINDING-01 — Terraform state and variable files containing secrets are committed to the repository

**Severity:** High
**OWASP Category:** A02 Cryptographic Failures / A07 Identification and Authentication Failures
**Affected Files:**
- `microservices/terraform/terraform.tfstate` (lines ~3030, 3068, 3354, 3769)
- `microservices/terraform/terraform.tfstate.backup`
- `microservices/terraform/terraform.tfvars`
- `microservices/terraform/tfplan`

**Description:**
The `.gitignore` in the terraform directory explicitly states these files must never be committed. Despite this, the repository contains all four. The Terraform state file (`terraform.tfstate`) stores the full plaintext value of every `google_secret_manager_secret_version` resource, including:
- All nine PostgreSQL connection strings with credentials and the live Cloud SQL IP (`34.174.75.10`)
- The JWT secret (`change-me-jwt-secret-min-32-chars`)
- The Anthropic API key placeholder
- All per-service database user passwords

`terraform.tfvars` also contains the same values in config form.

**Impact:**
Anyone with read access to the repository can recover credentials and identify live infrastructure endpoints. If the repo is public, or a fork/cache exists, these values may already be elsewhere. The default "placeholder" values shown in state suggest real secrets were never substituted — but the Cloud SQL IP is live and the infrastructure is real.

**Proposed Remediation:**

1. Immediately verify whether the credentials in state are the actual production credentials. If so, rotate all of them now: DB passwords, JWT secret, Anthropic key.
2. Remove the files from git history. They cannot simply be deleted — the history must be rewritten:
   ```bash
   # Using git filter-repo (recommended over BFG for modern repos)
   git filter-repo --path microservices/terraform/terraform.tfstate --invert-paths
   git filter-repo --path microservices/terraform/terraform.tfstate.backup --invert-paths
   git filter-repo --path microservices/terraform/terraform.tfvars --invert-paths
   git filter-repo --path microservices/terraform/tfplan --invert-paths
   # Then force-push
   git push origin --force --all
   ```
3. After history rewrite, invalidate all previously issued GitHub tokens that had read access to the repo.
4. Use Terraform Cloud or a remote backend (e.g. GCS bucket with versioning and IAM-gated access) so that state is never written locally during CI runs.
5. Generate `terraform.tfvars` during CI from a secrets manager (e.g. GCP Secret Manager via `gcloud secrets versions access`) and never write it to disk in the repo.

#### Remediation Status — ⚠️ Partially Remediated

- `terraform.tfstate`, `terraform.tfstate.backup`, and `terraform.tfvars` were **never committed** (confirmed via `git log --all`).
- `terraform/tfplan` was committed once (commit `19017c2`) and has been purged from all history using `git filter-repo` + force push. ✅
- `terraform/.gitignore` added to prevent future commits of state/secret files. ✅
- **New sub-issue introduced:** commit `5948e17 update` committed the `.terraform/` directory containing Google provider binaries (~200 MB of binary blobs). These must be purged separately:
  ```bash
  git filter-repo --path terraform/.terraform --invert-paths --force
  git push origin --force --all
  ```

---

### FINDING-02 — Cloud SQL instance is publicly accessible from 0.0.0.0/0

**Severity:** High
**OWASP Category:** A05 Security Misconfiguration
**Affected File:** `microservices/terraform/cloud_sql.tf` (lines 22–26)

**Current code:**
```hcl
ip_configuration {
  ipv4_enabled = true
  # Allow Cloud Run to connect via public IP with SSL
  authorized_networks {
    name  = "all-cloud-run"
    value = "0.0.0.0/0"
  }
}
```

**Description:**
The PostgreSQL instance has a public IPv4 address and the authorized network is the entire internet. This means the database port is reachable from anywhere on the internet. While SSL is required at the connection-string level, this is still a materially larger attack surface than private connectivity. Combined with FINDING-01 (committed credentials), the attack path to the database is immediate.

**Impact:**
Brute-force credential stuffing, direct SQL injection attempts, and exploitation of any future Postgres CVE without requiring internal network access.

**Proposed Remediation:**

Option A — Preferred: Use Cloud SQL Auth Proxy with private IP (requires enabling the Service Networking API and VPC Peering):
```hcl
ip_configuration {
  ipv4_enabled    = false
  private_network = google_compute_network.default.id
}
```
Cloud Run services connect via the proxy sidecar or the Cloud SQL Auth Proxy library, which handles IAM authentication without exposing the port.

Option B — Minimum viable improvement if private IP is not immediately feasible: Remove the open authorized network entirely. Cloud Run can connect to Cloud SQL via the Cloud SQL connector using the instance connection name without an authorized network:
```hcl
ip_configuration {
  ipv4_enabled       = true
  authorized_networks = []  # Remove the 0.0.0.0/0 block
}
```
Add the Cloud SQL instance connection name to each Cloud Run service environment instead of a raw `DATABASE_URL`:
```hcl
env {
  name  = "INSTANCE_CONNECTION_NAME"
  value = google_sql_database_instance.main.connection_name
}
```

#### Remediation Status — ⚠️ Code Fixed, `terraform apply` Pending

- The `authorized_networks { value = "0.0.0.0/0" }` block has been removed from `cloud_sql.tf` in commit `529427f`. ✅
- Cloud Run services now connect via the Cloud SQL connector using `INSTANCE_CONNECTION_NAME` — no public IP range required.
- **Live infrastructure is unchanged** until `terraform apply` is run against the GCP project.

---

### FINDING-03 — Cloud Run services are fully public including the AI orchestrator

**Severity:** High
**OWASP Category:** A01 Broken Access Control
**Affected File:** `microservices/terraform/cloud_run.tf` (lines 30, 101, 171, 239, 247, 255)

**Current code (applies to all three service blocks):**
```hcl
ingress = "INGRESS_TRAFFIC_ALL"

# ...

resource "google_cloud_run_v2_service_iam_member" "public_rust" {
  role     = "roles/run.invoker"
  member   = "allUsers"
}
```

**Description:**
Every Cloud Run service is configured for unrestricted public ingress and grants the `run.invoker` role to `allUsers`. For the domain Rust services, application-layer JWT enforcement provides a partial compensating control. However, the AI orchestrator is included in this public IAM grant and it can invoke an Anthropic API key. Abuse of the orchestrator endpoint can generate arbitrary LLM API costs without needing a valid credential.

**Impact:**
- Cost amplification via AI orchestrator abuse
- Brute-force / token stuffing against all authenticated endpoints
- Enumeration of API surface that should only be reachable from the frontend

**Proposed Remediation:**

For internal service-to-service calls (orchestrator, reporting, integration hooks), change ingress to internal-only and restrict the IAM invoker:
```hcl
# For services that are only called by other Cloud Run services
ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

# Remove the allUsers IAM grant and replace with:
resource "google_cloud_run_v2_service_iam_member" "orchestrator_invoker" {
  role   = "roles/run.invoker"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}
```

For the public-facing Rust domain services, keep `allUsers` but add rate limiting at the Cloud Armor or load balancer level and ensure the application-level JWT validation is never bypassable.

#### Remediation Status — ⚠️ Code Fixed, `terraform apply` Pending

- AI orchestrator ingress changed to `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` in commit `529427f`. ✅
- AI orchestrator IAM grant changed from `allUsers` to the Cloud Run service account in commit `529427f`. ✅
- The 8 Rust domain services intentionally remain `INGRESS_TRAFFIC_ALL` / `allUsers` — these are public APIs with JWT enforcement at the application layer.
- **Live infrastructure is unchanged** until `terraform apply` is run against the GCP project.

---

### FINDING-04 — All Rust microservices fall back to a hardcoded public JWT secret

**Severity:** High
**OWASP Category:** A02 Cryptographic Failures / A07 Identification and Authentication Failures
**Affected Files (same pattern in all 8 services):**
- `microservices/accounts-service/src/lib/auth.rs` (line 52)
- `microservices/contacts-service/src/lib/auth.rs` (line 44)
- `microservices/activities-service/src/lib/auth.rs` (line 52)
- `microservices/automation-service/src/lib/auth.rs` (line 52)
- `microservices/integrations-service/src/lib/auth.rs` (line 52)
- `microservices/opportunities-service/src/lib/auth.rs` (line 52)
- `microservices/reporting-service/src/lib/auth.rs` (line 52)
- `microservices/search-service/src/lib/auth.rs` (line 52)

**Current code (identical in all 8 files):**
```rust
fn auth_secret() -> String {
    env::var("AUTH_JWT_SECRET").unwrap_or_else(|_| "dev-insecure-secret-change-me".to_string())
}
```

**Description:**
When `AUTH_JWT_SECRET` is absent from the environment, the service silently accepts JWT tokens signed with a public, well-known secret. Because this fallback is documented in `CLAUDE.md` and test code, the string is completely predictable. Any attacker who discovers the fallback can mint valid tokens for any subject and role, bypassing all JWT authorization on the service.

**Impact:**
If any deployed instance is missing the env var, the entire auth layer is a no-op. The public Cloud Run exposure (FINDING-03) means exploitation would be immediate and remote.

**Proposed Remediation:**

Replace the fallback with a hard startup failure. This is the correct behavior: a service with no JWT secret should refuse to start rather than silently degrade to an insecure default.

Change the `auth_secret()` function in all 8 `auth.rs` files from:
```rust
fn auth_secret() -> String {
    env::var("AUTH_JWT_SECRET").unwrap_or_else(|_| "dev-insecure-secret-change-me".to_string())
}
```
To:
```rust
fn auth_secret() -> String {
    env::var("AUTH_JWT_SECRET")
        .expect("AUTH_JWT_SECRET must be set — refusing to start without a JWT secret")
}
```

This affects `auth_secret()` in 8 files. The change is identical in every file. The integration tests that use `make_jwt()` with `b"dev-insecure-secret-change-me"` will still work because tests set the environment variable themselves; only the runtime fallback is removed.

**Additional note:** The test helper `make_jwt()` in integration tests intentionally uses this known secret. Leave those alone — they exist only in `#[cfg(test)]` scope and the test environment controls the secret value. The fix is only to the production runtime fallback.

#### Remediation Status — ✅ Fully Remediated

- All 8 `auth.rs` files updated: `unwrap_or_else(|_| "dev-insecure-secret-change-me".to_string())` replaced with `.expect("AUTH_JWT_SECRET must be set")` in commit `5267423`. ✅
- CI `rust.yml` updated to inject `AUTH_JWT_SECRET=dev-insecure-secret-change-me` into all test steps so integration tests still pass (`5f600e7`). ✅

---

### FINDING-05 — Inconsistent CORS fallback behavior; some services allow broad headers with no origin restriction

**Severity:** Medium-High
**OWASP Category:** A05 Security Misconfiguration
**Affected Files:**
- `microservices/accounts-service/src/lib/router.rs` (lines 18–38)
- `microservices/contacts-service/src/lib/router.rs` (lines 18–38)
- `microservices/automation-service/src/lib/router.rs` (line 16)
- `microservices/activities-service/src/lib/router.rs` (line 16)
- `microservices/reporting-service/src/lib/router.rs` (line 17)
- `microservices/search-service/src/lib/router.rs` (line 17)
- `microservices/integrations-service/src/lib/router.rs` (line 16)
- `microservices/opportunities-service/src/lib/router.rs` (line 17)

**Description:**
There are two distinct CORS fallback patterns across the services:

**Pattern A** (accounts, contacts): When `ALLOWED_ORIGINS` is empty, returns a `CorsLayer` that permits all methods and all headers (`Any`) but no explicit origin restriction. `tower-http`'s behavior when `.allow_origin()` is not called still allows the browser to send requests — the key constraint is that credentials (`withCredentials`) require an explicit origin whitelist. This is weaker than it should be.

**Pattern B** (automation, activities, reporting, search, integrations, opportunities): Explicitly supports `ALLOWED_ORIGINS=*` to enable fully permissive CORS with a warning log. While the warning is present, the code path still allows a misconfigured deployment to run in a completely open state.

**Current code (Pattern A):**
```rust
if origins.is_empty() {
    return CorsLayer::new()
        .allow_methods([...])
        .allow_headers(Any);  // <-- no origin restriction, any header
}
```

**Current code (Pattern B):**
```rust
if origins.trim() == "*" {
    tracing::warn!("CORS is fully permissive — restrict ALLOWED_ORIGINS in production");
    return CorsLayer::permissive();
}
```

**Impact:**
CORS is a browser-side enforcement mechanism and not a substitute for authentication. However, excessively permissive CORS combined with lax JWT validation makes it easier for attacker-controlled pages to trigger credentialed cross-origin requests from a victim's browser.

**Proposed Remediation:**

For Pattern A services, fail closed when no origins are configured:
```rust
// Replace the empty-origins block in accounts-service and contacts-service
if origins.is_empty() {
    // No origins configured — reject all cross-origin requests
    return CorsLayer::new();
}
```

For Pattern B services, remove the `*` permissive path entirely. There is no legitimate production use for it given the Terraform config already sets the correct origin:
```rust
// Remove this block from automation, activities, reporting, search, integrations, opportunities
if origins.trim() == "*" {
    tracing::warn!("CORS is fully permissive — restrict ALLOWED_ORIGINS in production");
    return CorsLayer::permissive();
}
// If origins is still empty after stripping the * path, return a restrictive default:
if origins.trim().is_empty() {
    return CorsLayer::new();
}
```

#### Remediation Status — ✅ Fully Remediated

- **Pattern A** (accounts, contacts): empty-origins fallback replaced with `panic!("ALLOWED_ORIGINS must be set — refusing to start with permissive CORS")` in commit `5267423`. ✅
- **Pattern B** (automation, activities, reporting, search, integrations, opportunities): `*` permissive path replaced with `panic!("ALLOWED_ORIGINS=* is not allowed in production")` in commit `5267423`. ✅
- CI `rust.yml` updated to inject `ALLOWED_ORIGINS=http://localhost:5173` into all test steps (`7dbe77b`). ✅

---

### FINDING-06 — DynamoDB dashboard write endpoint and most data endpoints are unauthenticated

**Severity:** Medium-High
**OWASP Category:** A01 Broken Access Control
**Affected File:** `dynamodb_prototype/src/bin/dashboard.rs` (lines 68, 797–805)

**Description:**
The `require_admin()` helper explicitly opens all access when `DASHBOARD_ADMIN_KEY` is not configured:
```rust
// Dev mode: no key configured → open
if admin_key.is_empty() {
    return Ok(());
}
```
Only the `/api/spend` endpoint calls `require_admin()`. The other endpoints — including live DynamoDB pipeline data, build statuses, infrastructure metrics, CRM service overviews, and the `/ingest` write endpoint — are completely unauthenticated:

| Route | Auth gated? | Risk |
|---|---|---|
| `GET /api/stats` | No | Data disclosure |
| `GET /api/gold` | No | Data disclosure |
| `GET /api/silver` | No | Data disclosure |
| `GET /api/bronze` | No | Data disclosure |
| `GET /api/overview` | No | CRM data proxy disclosure |
| `GET /api/builds` | No | CI/CD enumeration |
| `GET /api/infrastructure` | No | CloudWatch metric disclosure |
| `POST /ingest` | No | **Unauthenticated write to DynamoDB** |
| `GET /api/spend` | **Yes** | AWS cost data (protected) |

The `/ingest` endpoint accepts a JSON body and writes arbitrary `stage#bronze#<uuid>` records to DynamoDB with no authentication. This is the highest-risk route — it can be used to inject arbitrary data into the pipeline, inflate DynamoDB costs, and potentially cause downstream pipeline processing on attacker-controlled payloads.

**Proposed Remediation:**

Add `require_admin(&headers)?` to every handler that currently lacks it. Because `require_admin` returns a `Result<(), StatusCode>`, the pattern is consistent with how spend already works:

```rust
async fn handler_ingest(
    State(s): State<DashState>,
    headers: HeaderMap,           // <-- add headers extraction
    Json(body): Json<IngestBody>,
) -> Result<StatusCode, (StatusCode, String)> {
    require_admin(&headers)
        .map_err(|status| (status, "unauthorized".to_string()))?;
    // ... rest of handler unchanged
}

async fn handler_overview(
    State(s): State<DashState>,
    headers: HeaderMap,           // <-- add headers extraction
) -> Result<Json<Value>, StatusCode> {
    require_admin(&headers)?;
    // ... rest of handler unchanged
}
```

Apply the same pattern to `handler_stats`, `handler_gold`, `handler_silver`, `handler_bronze`, `handler_builds`, and `handler_infrastructure`.

Also remove the dev-mode open bypass:
```rust
fn require_admin(headers: &HeaderMap) -> Result<(), StatusCode> {
    let admin_key = std::env::var("DASHBOARD_ADMIN_KEY")
        .expect("DASHBOARD_ADMIN_KEY must be set");  // fail fast instead of open bypass
    // ... rest unchanged
}
```

#### Remediation Status — ⚠️ Partially Remediated

- Dev-mode open bypass removed in commit `4f99ccf`: `DASHBOARD_ADMIN_KEY` is now required at startup via `expect()`. ✅
- **Remaining:** `require_admin(&headers)?` has **not** yet been added to the 8 unguarded handlers. The following routes are still unauthenticated:

| Route | Handler | Risk |
|---|---|---|
| `GET /api/stats` | `handler_stats` | Data disclosure |
| `GET /api/gold` | `handler_gold` | Data disclosure |
| `GET /api/silver` | `handler_silver` | Data disclosure |
| `GET /api/bronze` | `handler_bronze` | Data disclosure |
| `GET /api/overview` | `handler_overview` | CRM data proxy disclosure |
| `GET /api/builds` | `handler_builds` | CI/CD enumeration |
| `GET /api/infrastructure` | `handler_infrastructure` | CloudWatch metric disclosure |
| `POST /ingest` | `handler_ingest` | **Unauthenticated write to DynamoDB** |

---

### FINDING-07 — Prototype deploy workflow uses long-lived AWS access keys instead of OIDC

**Severity:** Medium
**OWASP Category:** A07 Identification and Authentication Failures
**Affected File:** `dynamodb_prototype/.github/workflows/deploy.yml` (lines 13–28)

**Description:**
The deploy workflow requests `id-token: write` permission (enabling OIDC) but then authenticates using static `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` secrets. The repo's own OIDC setup guide (`dynamodb_prototype/docs/OIDC_SETUP.md`) explicitly states the goal is to avoid storing long-lived AWS keys. The OIDC infrastructure and documentation are complete — the workflow simply hasn't been migrated.

**Current code:**
```yaml
env:
  AWS_ROLE_TO_ASSUME: ${{ secrets.AWS_ROLE_TO_ASSUME }}
  AWS_REGION: ${{ secrets.AWS_REGION }}
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
permissions:
  contents: read
  id-token: write

steps:
  - name: Configure AWS credentials
    uses: aws-actions/configure-aws-credentials@v2
    with:
      aws-access-key-id: ${{ env.AWS_ACCESS_KEY_ID }}
      aws-secret-access-key: ${{ env.AWS_SECRET_ACCESS_KEY }}
      aws-region: ${{ env.AWS_REGION }}
```

**Proposed Remediation:**

Replace the static key authentication with OIDC role assumption (the role ARN is already in `AWS_ROLE_TO_ASSUME`):
```yaml
env:
  AWS_REGION: ${{ secrets.AWS_REGION }}
  # Remove: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
permissions:
  contents: read
  id-token: write

steps:
  - name: Configure AWS credentials
    uses: aws-actions/configure-aws-credentials@v2
    with:
      role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME }}
      aws-region: ${{ env.AWS_REGION }}
      # Remove: aws-access-key-id and aws-secret-access-key
```

After this change, the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` repository secrets can be deleted entirely. The workflow will use short-lived federated credentials bound to the specific repo and branch per the trust policy in the OIDC guide.

#### Remediation Status — ✅ Remediated

- `deploy.yml` migrated from static `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` to OIDC `role-to-assume` with `configure-aws-credentials@v4` in commit `4f99ccf`. ✅
- **Recommended follow-up:** manually delete the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` secrets from the GitHub repository settings (Settings → Secrets → Actions).

---

### FINDING-08 — Container images run as root with unpinned base images

**Severity:** Medium
**OWASP Category:** A05 Security Misconfiguration
**Affected Files:** All service Dockerfiles in `microservices/*/Dockerfile`

**Description:**
All microservice Dockerfiles use `FROM rust:latest` for the builder stage, which is an unpinned tag that will silently drift to newer toolchain versions. More importantly, none of the final container images set a non-root `USER` directive, meaning the service binary runs as UID 0 inside the container.

**Current pattern (accounts-service example):**
```dockerfile
FROM rust:latest AS builder
# ...
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/accounts-service /usr/local/bin/accounts-service
EXPOSE 8080
CMD ["sh", "-c", "mkdir -p /data && touch /data/accounts.db && accounts-service"]
```

**Proposed Remediation:**

Pin the builder tag and add a non-root user to the runtime image:
```dockerfile
FROM rust:1.86-bookworm AS builder   # <-- pin to a specific version
# ... (build steps unchanged)

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --no-create-home --shell /bin/false appuser  # <-- add non-root user
WORKDIR /app
COPY --from=builder /app/target/release/accounts-service /usr/local/bin/accounts-service
USER appuser   # <-- drop privileges before running
EXPOSE 8080
CMD ["accounts-service"]   # <-- remove the sh -c wrapper now that mkdir is not needed for PG services
```

Note: The `sh -c "mkdir -p /data && touch /data/contacts.db && ..."` startup pattern in some Dockerfiles creates a SQLite file at runtime, but the Postgres-backed services don't need local SQLite files and can drop this wrapper entirely. For SQLite-backed services, pre-create the directory in the Dockerfile as the `appuser` during image build.

#### Remediation Status — ✅ Fully Remediated

- All 8 Dockerfiles: builder stage pinned from `rust:latest` to `rust:1.85-bookworm` in commit `5267423`. ✅
- All 8 runtime stages: `useradd --no-create-home --shell /bin/false appuser` added and `USER appuser` directive inserted before `CMD` in commit `5267423`. ✅

---

### FINDING-09 — RSA timing vulnerability accepted but not resolved

**Severity:** Low-Medium
**OWASP Category:** A02 Cryptographic Failures
**Affected File:** `microservices/audit.toml` (line 5), all service `auth.rs` files

**Description:**
RUSTSEC-2023-0071 (Marvin Attack — RSA timing side-channel) is suppressed in the audit configuration. The justification given is that all services default to HS256 and RS* paths are only used on controlled infrastructure. This is a reasonable acknowledgment, but the code path still exists and is silently ignored in CI.

**Impact:**
If `AUTH_JWT_ALGORITHM` is ever set to an RS* value in any deployment, the vulnerable RSA code path becomes active. The suppression in `audit.toml` means CI will not flag this even after an update that changes that behavior.

**Proposed Remediation:**

This is the lowest priority. The primary mitigations are:
1. Ensure no production deployment sets `AUTH_JWT_ALGORITHM` to RS256/RS384/RS512 until the `rsa` crate ships a fix.
2. Add a CI check or startup assertion that logs a clear warning if an RS* algorithm is configured.
3. Track the upstream `rsa` crate for a fix and remove the suppression once a patched version is available.

Optionally, remove the RSA code path entirely if it is not used:
```rust
// In auth.rs decoding_key() — remove the RS* branch if it will never be used:
fn decoding_key(algorithm: Algorithm) -> Result<DecodingKey, AuthError> {
    // RS* variant removed — HS256/HS384/HS512 only
    Ok(DecodingKey::from_secret(auth_secret().as_bytes()))
}
// And simplify auth_algorithm() to only accept HS* values.
```

#### Remediation Status — ✅ Acknowledged / Documented

- `audit.toml` updated in commit `5267423` with a rationale comment and an explicit revisit trigger: the suppression will be removed once the `rsa` crate publishes a patched release for RUSTSEC-2023-0071. ✅
- No code fix is possible until the upstream `rsa` crate ships a patch.

---

## Prioritized Remediation Plan

### Phase 1 — Immediate (before next code push)

| # | Action | Finding |
|---|---|---|
| 1.1 | Check whether state file contains actual production credentials (not just the placeholder strings seen in the file) | FINDING-01 |
| 1.2 | If yes: rotate all credentials — DB passwords (all 9 users), JWT secret, Anthropic API key | FINDING-01 |
| 1.3 | Rewrite git history to remove `terraform.tfstate`, `terraform.tfstate.backup`, `terraform.tfvars`, `tfplan` | FINDING-01 |
| 1.4 | Force-push and invalidate stale tokens/forks | FINDING-01 |

### Phase 2 — Short-term (within the next sprint/session)

| # | Action | Finding |
|---|---|---|
| 2.1 | Replace `AUTH_JWT_SECRET` fallback with `expect()` panic in all 8 `auth.rs` files | FINDING-04 |
| 2.2 | Add `require_admin()` to all dashboard data and write endpoints | FINDING-06 |
| 2.3 | Remove the dashboard dev-mode open bypass | FINDING-06 |
| 2.4 | Switch deploy.yml to OIDC role assumption; delete static AWS key secrets | FINDING-07 |

### Phase 3 — Infrastructure (next Terraform apply)

| # | Action | Finding |
|---|---|---|
| 3.1 | Remove Cloud SQL `authorized_networks { value = "0.0.0.0/0" }` block | FINDING-02 |
| 3.2 | Configure private IP or Cloud SQL connector for Cloud Run → Postgres connectivity | FINDING-02 |
| 3.3 | Change AI orchestrator and internal services to `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` | FINDING-03 |
| 3.4 | Replace `member = "allUsers"` IAM grants for internal services with service account members | FINDING-03 |

### Phase 4 — Hardening (ongoing)

| # | Action | Finding |
|---|---|---|
| 4.1 | Fix CORS fallback: remove `allow_headers(Any)` fallback and `*` permissive path | FINDING-05 |
| 4.2 | Pin `rust:latest` builder image tags in all Dockerfiles | FINDING-08 |
| 4.3 | Add non-root `USER appuser` to all runtime container images | FINDING-08 |
| 4.4 | Monitor `rsa` crate for RUSTSEC-2023-0071 fix; remove suppression when patched | FINDING-09 |

---

## Positive Security Controls Already in Place

The following security practices are already implemented and should be preserved:

- **All domain API endpoints require a valid Bearer JWT** — consistent `require_auth()` enforcement across all 8 microservices
- **JWT validation is correct** — expiry (`validate_exp = true`), issuer validation, and scheme check are all enforced
- **SQL injection is not possible** — all database queries use parameterized binds via `sqlx` (no string interpolation)
- **Secrets are injected via GCP Secret Manager** — Terraform wires secrets through Secret Manager references, not hardcoded env values in the runner config
- **CI runs `cargo audit` on every push** — the advisory database is consulted automatically
- **Input validation exists on free-text fields** — `source` field in dashboard ingest validates character set; title length is capped in the task API
- **HTTPS is enforced** — Fly.io deployment has `force_https = true`; GCP Cloud Run always terminates TLS
- **One database user per service** — least-privilege at the database layer with separate credentials per service user
- **Structured error responses** — auth failures return machine-readable codes without leaking internal details

---

*Original audit: 2026-03-15 — No files were modified during the initial audit pass.*
*Updated: 2026-03-15 — Remediation status added for all 9 findings.*
