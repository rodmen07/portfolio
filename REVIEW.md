# Portfolio — Code Review & Monetization Analysis

**Scope:** Full-repo review of the Portfolio umbrella (11 submodules + `agents/` + root infra).
Services reviewed: `ai-orchestrator-service`, `auth-service`, `backend-service`,
`event-stream-service`, `go-gateway`, `infraportal`, `microservices/*` (13 crates),
`observaboard`, `projects-service`, `vertexai-secondbrain`, `agents/*`, plus root
Dockerfile/CI/`services.yaml`/`gcp-setup.sh`.

**Method:** Each service group was read in full and its findings verified against the actual
source (and, for the Rust auth issue, against the locked crate versions in `Cargo.lock`). The
highest-severity claims were re-checked by hand before inclusion — where a bug is *latent*
(guarded by current deploy config but fail-open in code), that is called out explicitly rather
than overstated.

> **Note on live status.** The README/CLAUDE.md describe most services as "deployed and
> production-grade." Several findings below (esp. the Rust boot panic and the fail-open auth
> defaults) would prevent a clean boot *from current `main`*. Where a live deployment appears
> to contradict a finding, the most likely explanation is that the running image predates a
> dependency bump or a code divergence — i.e. the bug bites on the **next** redeploy. Confirm
> with a boot/integration test before shipping.

---

## Part 1 — Bug Report

### Severity overview

| Severity | Count | Theme |
|----------|-------|-------|
| Critical | 4 | Boot-panic (8 Rust services), unauthenticated token minting, gateway identity-header spoofing, wide-open spend/search authorization |
| High | 12 | Fail-open auth defaults, default HMAC secret, OAuth open-redirect/XSS, stored XSS in portal, tenant-isolation gaps, channel-close panic |
| Medium | ~18 | Rate-limit spoofing, missing audience validation, CSRF-via-GET, plaintext API keys, replica write routing, unauth paid-LLM endpoints |
| Low | ~20 | Info leaks, unbounded lists, CSV injection, dead code, Dockerfile/pinning, config drift |

### Fix-these-first (ranked)

| # | Service | Finding | Sev |
|---|---------|---------|-----|
| 1 | microservices (8 svcs) | Local JWT decoder panics at startup under locked `axum-jwt-auth 0.6.3` | Critical |
| 2 | auth-service | `POST /auth/token` mints a signed JWT for **any** subject with `user`/`planner`/`client` roles, no caller auth | Critical/High |
| 3 | spend-service / search-service | Zero role/tenant checks — any JWT reads the whole cloud bill / all indexed CRM data and triggers credentialed sync | High |
| 4 | go-gateway | Inbound `X-Auth-*` identity headers never stripped; `X-Auth-Roles` not overwritten for role-less tokens | Critical (latent) |
| 5 | backend-service | `AUTH_ENFORCED` code default is **false** → all protected+admin routes public if env var ever dropped | High (latent) |
| 6 | backend/projects/microservices | Default HMAC secret `dev-insecure-secret-change-me` → forgeable admin tokens if `AUTH_JWT_SECRET` unset | High |
| 7 | infraportal | Stored XSS: inbound `email.body_html` rendered via `dangerouslySetInnerHTML`, no sanitizer/CSP, token in `localStorage` | High |
| 8 | auth-service | Client-portal OAuth open redirect → victim JWT exfiltrated to attacker `redirect_uri` | High |
| 9 | projects-service (std) / microservices | Disabling auth returns a hard-coded **admin** identity, not anonymous | High (latent) |
| 10 | event-stream-service | Send-on-closed-channel panic in hub broadcast on client disconnect | High |

---

### 1. `microservices/*` — Rust CRM services

#### 1.1 CRITICAL — 8 services panic at startup (JWT decoder built without required audience)
**Files:** `activities-service`, `audit-service`, `automation-service`, `contacts-service`,
`integrations-service`, `opportunities-service`, `projects-service`, `spend-service` →
each `src/lib/app_state.rs`, local `build_decoder()` (e.g. `contacts-service/src/lib/app_state.rs:25-54`, `.build().expect(...)` at :52).
**Category:** misconfig / logic bug (total unavailability).

Each of these 8 services carries a *local* `build_decoder()` that calls `Validation::new(alg)`
and **never sets an audience**, then `LocalDecoder::builder()...build().expect("failed to build JWT decoder")`.
Under the locked `axum-jwt-auth 0.6.3` (confirmed in `Cargo.lock`), `LocalDecoder::build()`
returns `Err(Configuration("Validation audience is required"))` when `validation.aud.is_none()` —
so `.expect(...)` **panics before the listener binds**. The shared crate documents this exact
trap and works around it (`shared-auth/src/lib.rs:36-41`: sets a placeholder `aud="unused"` with
`validate_aud=false` and removes `"aud"` from `required_spec_claims`). Only `accounts-service`,
`reporting-service`, and `search-service` were migrated to `shared_auth::build_decoder_from_env()`;
the other 8 kept the stale local copy.
**Verified:** `Cargo.lock` → `axum-jwt-auth 0.6.3`, `jsonwebtoken 10.3.0`; grep confirms all 8
local decoders lack `set_audience`/`validate_aud`/`required_spec_claims`.
**Fix:** Delete each local `build_decoder()` and call `shared_auth::build_decoder_from_env()`
(as the 3 migrated services do). One change removes the panic and re-centralizes auth.

#### 1.2 HIGH — No tenant isolation in `automation-service` and `integrations-service` (IDOR)
**Files:** `automation-service/src/lib/handlers/workflows.rs` (`list`/`get`/`update`/`delete`,
:36-40, :63-68, :178-184, :297-299); `integrations-service/src/lib/handlers/connections.rs`
(:36-40, :63-67, :185-189, :284-287). Neither `workflows` nor `connections` table has an owner column.
**Category:** security (broken access control / tenant isolation).

Unlike accounts/contacts/activities (which correctly filter by `owner_id = claims.sub` with an
admin bypass), these two read `claims.sub` only for logging. Any authenticated principal can list,
read, mutate, or delete **any** tenant's workflow rules and integration connections by id.
**Fix:** Add `owner_id` and filter by `claims.sub` (admin bypass), or gate all mutations behind
`claims.has_role("admin")` if these are meant to be global config.

#### 1.3 HIGH — `search-service` cross-tenant read + unauthenticated writes
**File:** `search-service/src/lib/handlers/documents.rs` — reads (`search`/`list`/`get`,
:29-131) have **no** owner/role filter; writes (`index`/`update`/`delete`/`delete_by_entity`,
:134-332) require only *a* JWT. `SearchDocument` has no owner column.
**Category:** security (tenant isolation + broken access control).

The write-through pipeline indexes CRM content (opportunity names, deal amounts, `account_id`;
project name/status). So `GET /api/v1/search?q=…` returns other tenants' deal data to any
`client`-role portal user, and any user can poison/delete the index for everyone
(`DELETE /api/v1/search/documents/by-entity/{uuid}`). The write-through `SEARCH_SERVICE_TOKEN`
is an ordinary JWT the service can't distinguish from a user token.
**Fix:** Add a tenant/owner column, filter reads by `claims.sub` (admin bypass), and require an
admin/service role on all mutating routes.

#### 1.4 HIGH — `spend-service` has zero authorization on any route
**Files:** `spend-service/src/lib/handlers/spend.rs`, `router.rs:41-50` (no `has_role`/`is_admin`
anywhere — confirmed by grep).
**Category:** security (broken access control).

Every route is open to any authenticated principal, including `client` portal users:
`GET /api/v1/spend[/summary]` exposes the **entire company cloud bill** (AWS/GCP/Fly/GitHub
breakdowns); `POST/PATCH/DELETE` inject/remove spend records; and the four
`POST /api/v1/spend/sync/{gcp,flyio,github,aws}` endpoints (`spend.rs:672+`) trigger outbound,
**credentialed** calls to external billing APIs on demand — a client can drive repeated external
requests using the org's stored SA key/tokens.
**Fix:** Gate all spend routes — especially the `sync_*` endpoints — behind an admin role check.
*(Verified sound: the AWS SigV4 canonical-request construction in `sync.rs` is correct.)*

#### 1.5 MEDIUM — `audit-service` accepts attacker-controlled actor → audit-log forgery
**File:** `audit-service/src/lib/handlers/audit_events.rs:35-217` (`actor_id` from body at :138,
stored at :192; authenticated `claims.sub` only logged at :200, never persisted).
**Category:** security (audit integrity / repudiation).

Any JWT holder can `POST /api/v1/audit-events` and forge entries in the "immutable CRM mutation
log" — attribute a `deleted` action to someone else's `actor_id`, invent events, or flood it. The
real identity is discarded, so the trail is non-repudiable in name only. (Reads are correctly
admin-gated at :269.)
**Fix:** Persist `actor_id` from `claims.sub` (ignore/validate the body value); restrict ingestion
to a trusted service role.

#### 1.6 MEDIUM — `reporting-service` routes writes to the read replica
**File:** `reporting-service/src/lib/app_state.rs:21-27` (`with_read_replica`).
**Category:** logic / misconfig.

The migration pool (write URL) is dropped and the single serving `pool` connects to
`read_url.unwrap_or(write_url)`. When `DATABASE_REPLICA_URL` is set (the documented multi-region
setup), **all** handler queries — including `create/update/delete_report` — run against the
read-only replica and fail (`cannot execute … in a read-only transaction`) → 500s. Report CRUD
writes are fully broken in replica mode. `search-service` does this correctly with separate
`pool`/`read_pool`.
**Fix:** Keep a write `pool` and a separate `read_pool`; send only reads to the replica.

#### 1.7 MEDIUM — `reporting-service` dashboard leaks metric names across tenants
**File:** `reporting-service/src/lib/handlers/reports.rs:173-183` (`get_dashboard`) —
`SELECT DISTINCT metric FROM reports ORDER BY metric` with no owner filter, while the sibling
`get_dashboard_summary` (:57-68) scopes the identical query by `owner_id`. Inconsistency → a
non-admin sees all users' distinct metric names.
**Fix:** Scope by `owner_id` for non-admins.

#### 1.8 MEDIUM — `projects-service` (microservices) allow-by-default read authorization
**File:** `microservices/projects-service/src/lib/handlers/projects.rs:48-65` and
`require_project_access` in milestones/deliverables/emails/links/messages.
**Category:** security (authorization design).

Read access is restricted only by *excluding* `client`; any token lacking the `client` role
(empty/unknown roles, or a service token) gets unrestricted read of every project and sub-resource
— the opposite of the deny-by-default pattern used elsewhere. (Mutations are correctly
`require_admin`.)
**Fix:** Require an explicit allowed role (`admin`/`staff`) for the "see everything" path; treat
unknown/empty-role tokens as no access.

#### 1.9 LOW — Cross-cutting Rust items
- **Fake in-memory fallback panics (all `main.rs`):** on DB init failure services fall back to
  `AppState::from_database_url("sqlite::memory:")`, but the pool is a `PgPool` — the connect fails
  and the following `.expect(...)` panics. The fallback converts a DB outage into a panic; remove it.
- **`/health` leaks DB error detail:** `accounts-service/src/lib/handlers/health.rs:14` returns
  `error: e.to_string()` (raw `sqlx` error, may include host/DB name) to unauthenticated callers.
  Return a generic `{status:"degraded"}`; log the detail server-side. Shared health-handler pattern.
- **Audit emit is awaited in the request path:** `opportunities.rs:259,412` `.await`s `emit_audit`
  with the 5s-timeout client, adding up to 5s latency to every mutating request when the audit
  service is slow. Make it fire-and-forget like the other pipeline calls.
- **Wrong actor in opportunities audit-on-update:** `opportunities.rs:412` passes `updated.owner_id`
  as `actor_id` instead of `claims.sub`; an admin editing another user's opportunity is logged as
  the owner. `snippet` slicing in search is a separate item →

#### 1.10 MEDIUM — `search-service` panic on multibyte UTF-8 snippet
**File:** `search-service/src/lib/handlers/documents.rs:63-64` —
`if doc.body.len() > 140 { &doc.body[..140] }` slices by **byte** index. If byte 140 isn't a char
boundary (emoji/CJK/accented past 140 bytes) this panics; there's no `CatchPanic` layer and
`index_document` doesn't cap/validate `body`, so it's attacker-reachable. Use
`doc.body.chars().take(140).collect::<String>()` (or `floor_char_boundary`) and cap `title`/`body` length.

---

### 2. `auth-service` — Python/FastAPI (JWT + OAuth)

> Verified sound: no SQL injection (all `?`-bound), argon2id password hashing, and decode pins
> `algorithms=[config.algorithm]` (no `alg=none`/HS↔RS confusion). The issues below are the real ones.

#### 2.1 CRITICAL/HIGH — Unauthenticated token minting (impersonate any subject; self-grant non-admin roles)
**File:** `app/main.py:289-302` (`issue_token`), gating in `app/roles.py:24-47`.
**Category:** broken authentication / access control.

`POST /auth/token` has **no caller auth** — only rate limiting. Any anonymous client can request
`{"subject":"<anyone>","roles":["user","planner","client"]}` and receive a validly signed JWT.
`sanitize_roles` blocks only `admin` (verified: `roles.py:44-45` raises 403 for privileged roles
when `subject ∉ AUTH_ADMIN_SUBJECTS`), so `client` (portal access), `user`, and `planner` are
freely self-grantable for an arbitrary `sub`. Downstream `/auth/verify` accepts them.
**Fix:** Require service/client auth on `/auth/token` (mTLS, service API key), or restrict
`subject` to the authenticated principal, or remove the endpoint if superseded by login/OAuth.

#### 2.2 HIGH — Reflected XSS on the auth origin via OAuth error callback
**File:** `app/user_oauth.py:245` (`render_user_popup_error`), reached from `app/main.py:827-829`.
`<p style="margin:0;">Sign in failed: {message}</p>` interpolates the message with no escaping, and
`user_oauth_callback` renders `error_description` through it **before** state verification. Visiting
`…/user/oauth/callback?error=x&error_description=<script>…</script>` runs attacker JS on the JWT-issuing
origin. (The CMS variant keeps the message out of the HTML body and is safe.)
**Fix:** `html.escape(message)` before interpolation.

#### 2.3 HIGH — Open redirect / JWT exfiltration in client-portal OAuth
**File:** `app/main.py:956-984` (guard :964; URL build :976-982). `portal_redirect_uri` comes from
caller-supplied `redirect_uri`, validated only by `startswith(("http://","https://"))` — no host
allowlist. Attacker sends an authorize link with `redirect_uri=https://evil.com`; after the victim
authenticates, the service redirects to `https://evil.com?token=<victim JWT>` (with `client` role
forced on).
**Fix:** Allowlist `redirect_uri` host; don't append the JWT as a query param (see 2.9).

#### 2.4 HIGH — Fail-open admin gate on the dashboard OAuth flow
**File:** `app/main.py:986-995` (condition :989). `if admin_subjects and user.id not in … and user.username not in …`
— when `AUTH_ADMIN_SUBJECTS` is unset, `_admin_subjects()` is empty, the condition short-circuits
false, and the admin check is skipped → **any** GitHub-OAuth user is issued a token for the spend
dashboard.
**Fix:** Fail closed — empty allowlist denies.

#### 2.5 HIGH — Rate-limit bypass via spoofable `X-Forwarded-For`
**File:** `app/main.py:123-129` (`_client_ip` trusts the first XFF entry). Rotating XFF per request
yields a fresh bucket every time, defeating the only brute-force protection on `/auth/login`,
`/auth/register`, `/auth/token`, and OAuth.
**Fix:** Derive client IP from the trusted proxy hop (Fly-Client-IP / rightmost XFF), not client XFF.

#### 2.6 HIGH — Production hardening keyed on `ENVIRONMENT`, which the deployment never sets
**File:** `app/main.py:86-92` (startup secret guard) and `:211-221` (`_set_refresh_cookie`,
`secure=` at :218); `fly.toml` `[env]` sets no `ENVIRONMENT` → defaults to `"development"`. So the
guard that refuses to boot on the default JWT secret **never fires** (only a `logger.warning`), and
the refresh cookie is set with `secure=False` in prod.
**Fix:** Set `ENVIRONMENT="production"` (or invert to fail-closed); always `Secure` the refresh
cookie; enforce a non-default secret regardless of environment.

#### 2.7 MEDIUM — OAuth state secrets default to public hardcoded strings, unenforced
**File:** `app/cms_oauth.py:13`, `app/user_oauth.py:16` — `*_OAUTH_STATE_SECRET` default to
`"*-insecure-default"` with only a warning if unset (no startup enforcement). A known HMAC state
secret lets an attacker forge state, defeating OAuth CSRF (compounds 2.3).
**Fix:** Enforce these at startup in production; set via `fly secrets`.

#### 2.8 MEDIUM — JWT issuer/audience not validated on decode
**File:** `app/jwt_utils.py:126-132` — `require`s `iss` be *present* but never validates it (no
`issuer=`), and no `aud`. Any token signed with the same key is accepted regardless of issuer.
**Fix:** Pass `issuer=config.issuer` and add/verify an `aud` claim.

#### 2.9 MEDIUM — Additional auth-service items
- **User enumeration (`main.py:540-557`):** OAuth-only accounts return a distinct 400
  ("This account uses OAuth sign-in…") and timing differs (argon2 runs only for password users).
  Return uniform "Invalid username or password" and do a dummy hash on the no-user path.
- **OAuth email-linking without verified-email check (`main.py:920-928`, `database.py:245-269`):**
  Google's `verified_email` flag isn't checked before linking an OAuth identity to an existing
  password account by email → potential takeover if a provider asserts an unverified address.
- **Tokens in URL (`main.py:979-982`, :1000):** JWT placed in query/fragment leaks via Referer,
  history, and logs. Use a postMessage/one-time-code handshake.
- **Refresh rotation lacks reuse detection (`main.py:668-688`):** revoke→create without checking
  `revoke` rowcount; no token-family invalidation on replay → two concurrent uses of a stolen token
  both succeed. Treat reuse of a revoked token as theft and invalidate the family.

---

### 3. `go-gateway` + `event-stream-service` — Go

> Verified sound: HS256/RS256 algorithm-confusion is correctly prevented (`auth.go:56-72`),
> `alg:none`/missing-`exp` rejected, HMAC compare is constant-time, and the rate-limiter map access
> is fully mutex-guarded.

#### 3.1 CRITICAL (latent) — Identity-header spoofing at the gateway
**File:** `go-gateway/internal/middleware/auth.go:80-83`; skip paths :34-39; no-op :28-30.
**Category:** security (auth bypass / header injection).

The gateway forwards `X-Auth-Subject`/`X-Auth-Roles` to upstreams but **never strips inbound copies**,
and only *sets* `X-Auth-Roles` when the token carries roles (`if len(roles) > 0`). `parseClaims`
returns `nil` roles when the claim is absent, so a client with a valid **role-less** JWT can send a
forged `X-Auth-Roles: admin` and it passes through untouched. Exempt routes (`/api/auth`, `/health`)
and no-auth mode forward client-supplied `X-Auth-*` verbatim.
**Exploitability nuance:** the current Rust upstreams re-derive roles from the JWT itself (they don't
trust `X-Auth-Roles`), so this is a **latent** privilege-escalation path today — but it's exactly the
header the gateway is *designed* to have upstreams consume, so any future upstream that trusts it is
immediately vulnerable.
**Fix:** Unconditionally `Del` `X-Auth-Subject`/`X-Auth-Roles` on the inbound request at the top of
the middleware (and in the no-op wrapper), then `Set` them only from verified claims (always set
roles, even to `""`).

#### 3.2 HIGH — Send-on-closed-channel panic in the hub broadcast
**File:** `event-stream-service/hub.go:66-78` vs `:41-49`. `Publish` snapshots subscriber channels,
releases the lock, then sends outside it; `Unsubscribe` (via `defer hub.Unsubscribe(id)` on disconnect,
`main.go:197`) `close(ch)` under the lock. A disconnect in the snapshot→send window makes `Publish`
send on a closed channel — which panics even inside `select {…default:}` (default covers *blocking*,
not *closed*). The publish aborts mid-broadcast, remaining subscribers miss the event, and a non-HTTP
caller would crash the process.
**Fix:** Don't `close()` from the writer side — the reader exits via `r.Context().Done()`; just
`delete` from the map. Or do the non-blocking sends under `RLock`.

#### 3.3 MEDIUM — event-stream fail-open + unauthenticated stream
- **`main.go:58-61` (`validateBearer`)** returns `nil` when `AUTH_JWT_SECRET==""`, and nothing in
  `main()` guards against an empty secret (unlike the gateway's fail-fast) → `POST /events/publish`
  accepts unauthenticated injection if the secret is ever unset.
- **`main.go:175-197`** — `/events/stream` never calls `validateBearer` (while `publishHandler` does).
  Any unauthenticated client reads the full live stream + 50-event replay buffer. If CRM mutation
  payloads flow through, that's unauthenticated data disclosure. *Confirm intent* — if not a public
  feed, add the bearer check.

#### 3.4 MEDIUM — Gateway rate-limit bypass via `X-Forwarded-For`
**File:** `go-gateway/internal/middleware/ratelimit.go:124-136` (and `ratelimit_redis.go:34`) —
`extractIP` trusts the leftmost XFF value; rotating it per request defeats the per-IP limit,
including the tight `/api/auth` limit meant to slow credential stuffing.
**Fix:** Use a trusted position (rightmost XFF added by the LB / fixed trusted-proxy depth).

#### 3.5 MEDIUM — Circuit breaker admits unlimited half-open probes
**File:** `go-gateway/internal/proxy/circuitbreaker.go:52-53` — `case cbHalfOpen: return true` lets
*every* concurrent request through on transition, stampeding a possibly-still-down upstream (the
comment claims "one probe"). Gate exactly one probe with a `probeInFlight` flag.

#### 3.6 MEDIUM — CORS wildcard + `Allow-Credentials: true`
**File:** `go-gateway/internal/middleware/cors.go:29-38` — when `ALLOWED_ORIGINS="*"` it emits
`Access-Control-Allow-Origin: *` **and** unconditionally `Allow-Credentials: true` (a contradictory
combo browsers reject; signals intent to allow any origin with credentials). Only emit
`Allow-Credentials` on the reflected-specific-origin path.

#### 3.7 LOW — Go items worth a pass
- **Missing HTTP server timeouts (Slowloris):** both services use bare `http.ListenAndServe`
  (`event-stream main.go:262`, `gateway main.go:191`) — no `ReadHeaderTimeout`/`IdleTimeout`.
- **No request-body size limit:** `event-stream main.go:148` decodes an unbounded body into the ring
  buffer. Wrap with `http.MaxBytesReader`.
- **Response cache ignores `Cache-Control`/`Vary` and clones `Set-Cookie`:** `response_cache.go:151-159`
  caches any 2xx GET regardless of `no-store/private`, keys only on path+query+subject, and replays
  all upstream headers (incl. `Set-Cookie`) to same-subject requests — cache-poisoning/hygiene risk.
- **`Flusher` stripped by recorders** (`logger.go`, `circuitbreaker.go:80-88`, `response_cache.go`) →
  SSE/streaming upstreams get buffered. Implement `Flush()` pass-through.
- **`/health/upstreams` is unauthenticated** (`upstreams.go:24`) and fans out 12 outbound probes with
  no rate limit — discloses internal URLs/state + mild amplification.
- **Redis limiter leaks un-expired keys / fails open** (`ratelimit_redis.go:43-51`): `EXPIRE` runs on
  the 300ms request ctx only when `count==1`; use an atomic `SET … EX 2 NX` + `INCR` Lua script.
- **Swagger UI broken by own CSP** (`openapi.go` loads from `unpkg.com`, blocked by
  `security_headers.go:21` `default-src 'self'`).

---

### 4. `ai-orchestrator-service` + `agents/` + `vertexai-secondbrain` — Python

#### 4.1 MEDIUM — Unauthenticated, unthrottled access to paid LLM APIs
**File:** `ai-orchestrator-service/app/main.py` — `/consult[/stream]`, `/consult/gemini[/stream]`,
`/plan`, `/agent` have no auth dependency and no rate limit (CORS only constrains browsers). A direct
HTTP client can drive unbounded Anthropic/Gemini spend.
**Fix:** Add an API key + per-route rate limit on the LLM-calling routes.

#### 4.2 HIGH — `agents/productionizer/runner.py:290-292` NameError on the PR-limit pause path
`obs.end_run(); obs.save(); obs.print_summary()` but `obs` is never defined/imported in `runner.py`.
The moment any repo hits `MAX_OPEN_PRS_PER_REPO`, the "graceful pause" throws
`NameError: name 'obs' is not defined` and crashes. (The agent is archived, so impact is limited, but
it's a live crash path.) **Fix:** remove the three `obs.*` lines (runner uses the file accumulator).

#### 4.3 HIGH — `agents/productionizer/llm_client.py` OpenAI tool path is non-functional
- `:152` — `tool_call.function.arguments` is always a JSON **string**, but the code keeps it only
  `if isinstance(..., dict)` → every tool call gets `input={}` → `KeyError` in the dispatch. Use
  `json.loads(tool_call.function.arguments or "{}")`.
- `:137` + `main.py:203,250` — the multi-turn loop appends Anthropic-shaped messages and passes them
  straight to `chat.completions.create` → OpenAI 400 on the second turn.
  (Both are dead-ish given the archive status, but they mean the documented GPT provider never worked.)

#### 4.4 MEDIUM — `agents/productionizer/tools.py` sandbox escapes
- **`run_shell` `find` bypass (`:98-161`):** operators/interpreters/`rm`/`git` are blocklisted, but
  `find` is allowed — `find . -delete` / `find . -exec <prog> {} +` runs deletion/arbitrary exec with
  no blocked token. Reject `find` args with `-exec*/-delete/-fprint`.
- **Path traversal (`:48,71,84`):** `target = cfg.path / path` with no containment check; the
  `write_file` secret filter only blocks substrings, not `../`/`.ssh`. Add
  `resolved = (cfg.path / path).resolve()` and assert it stays within `cfg.path.resolve()`.

#### 4.5 MEDIUM — `main.py:399-417` transient-error detection clobbered
Two sequential `try import anthropic … / try import openai …` blocks both assign `is_transient` (`=`
not `|=`); since `openai` is always importable, an Anthropic `RateLimitError`/5xx (set True in the
first block) is reset to False → `EXIT_ERROR` (stop) instead of `EXIT_SKIP` (retry). Use `|=`.

#### 4.6 LOW — Python misc
- **`ai-orchestrator Dockerfile:10,18`** binds `--port ${APP_PORT}` (defaults 8080); Cloud Run injects
  `PORT`, not `APP_PORT` — works only because both are 8080. Use `--port ${PORT:-8080}`.
- **`ai-orchestrator/.env.example`** lists dead `OPENROUTER_*` vars and omits every var the code needs
  (`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `DASHBOARD_URL`, …) → setup from it yields an instant 503.
- **`main.py:8`** imports `CloudTraceExporter` (package exports `CloudTraceSpanExporter`) — swallowed
  by the try/except, so tracing silently never initializes.
- **`openrouter.py:157,225`** fire-and-forget `asyncio.create_task(...)` without retaining the ref →
  task may be GC'd mid-run; dashboard log silently dropped. Keep refs in a module `set`.
- **`gmail-sync/sync_project_emails.py:90`** interpolates unescaped `project_name` into a Gmail
  `subject:"…"` query → query injection via a name containing `"`. Also `:112`/`:71` crash on missing
  header keys / bad base64 padding.
- **`schemas.py:60` / `main.py` LeadRequest** — `email` only length-validated (3-200), no format check;
  malformed emails forwarded to contacts-service.

#### 4.7 INFO — `vertexai-secondbrain/app/{ingest,main}.py` are 0 bytes
Empty stubs (plus empty README/requirements/LICENSE). Anything importing `app.main:app` fails. Either
finish or remove to avoid a misleading "service."

---

### 5. `backend-service` + `projects-service` (standalone) — Rust

#### 5.1 HIGH — Default HMAC JWT secret → forgeable admin tokens
**File:** `backend-service/src/lib/auth.rs:54-56`, `projects-service/src/lib/auth.rs:77-79` —
`env::var("AUTH_JWT_SECRET").unwrap_or_else(|_| "dev-insecure-secret-change-me")`. With HS256 (the
default), if the secret is unset at runtime the signing key is a published constant → anyone can mint
`{"sub":"x","roles":["admin"]}` and pass `require_admin`, defeating auth **even with
`AUTH_ENFORCED=true`**. (Current deploy sets the secret via Secret Manager, so latent — but a single
missing secret binding = full compromise.)
**Fix:** Fail closed at startup — if HMAC and the secret is unset or equals the dev default, refuse to boot.

#### 5.2 HIGH (latent) — `backend-service` `AUTH_ENFORCED` defaults to **false**
**File:** `backend-service/src/lib/router.rs:73-78` (`.unwrap_or(false)`); `require_auth`/`require_admin`
short-circuit to `next.run()` when false (:90-92, :125-127). If the env var is ever missing/misspelled,
**every protected and admin route becomes public**. Current `deploy-cloud-run.yml:128` sets
`AUTH_ENFORCED=true`, so it's latent — but `projects-service` correctly defaults this to `true`
(`auth.rs:74`); backend is the inconsistent, dangerous one.
**Fix:** Default to `true` (fail closed).

#### 5.3 HIGH (latent) — Disabling auth grants admin to everyone (`projects-service` + microservices)
**File:** `projects-service/src/lib/auth.rs:37-43,149-151` — when `AUTH_ENFORCED != "true"` (incl. a
typo like `"1"`/`"yes"`), the extractor returns `dev_claims()` = `roles:["admin"]` for any
missing/invalid token. Disabling auth doesn't degrade to anonymous; it makes every caller a full admin.
**Fix:** Non-enforced mode should use an empty/non-privileged role set, or gate `dev_claims` behind
`#[cfg(debug_assertions)]` so it can't exist in a release binary.

#### 5.4 HIGH — Rate limiter trusts client `X-Forwarded-For` (both) + unbounded map
**File:** `backend-service/src/lib/rate_limit.rs:112-128`, `planner.rs:43-51`,
`projects-service/src/lib/rate_limit.rs:63-78` — leftmost XFF is attacker-controlled → all limits
bypassable, including the 5-per-300s guard on the expensive LLM planner (cost-amplification DoS) and a
targeted-lockout vector (set XFF to a victim IP). Separately, `check_bucket` prunes stale timestamps
but never removes the map entry → unbounded `HashMap` growth (memory DoS, esp. combined with spoofed keys).
**Fix:** Use the platform trusted-client-IP header; drop empty map entries / cap map size.

#### 5.5 MEDIUM — Public lead-intake endpoint: spoofable throttle + weak validation
**File:** `backend-service/src/lib/handlers/lead_intake.rs:21-111` (route `router.rs:64`). The only
unauthenticated write path; its sole protection is the bypassable IP limiter. Can be flooded to fill
`public_lead_intake_submissions` with verbatim attacker JSON and to trigger an outbound POST of the
attacker body to `LEAD_INTAKE_FORWARD_URL` per request (amplification). Email check is only
`value.contains('@')`.
**Fix:** Dedicated strict per-(trusted-)IP limit, payload size/field caps, stronger email validation,
CAPTCHA/proof-of-work.

#### 5.6 LOW — backend/projects misc
- `admin_metrics` 500s on empty table (`admin.rs:27-42`): `SUM(...)` is `NULL` → decode into non-`Option`
  `i64` fails. Use `COALESCE(SUM(...),0)`.
- Comment update/delete do no author check (`comments.rs:138-250`) — `author_id` is recorded but never
  enforced; any user can edit/delete any comment. (OK only if the board is intentionally shared.)
- `projects-service` list endpoints have no `limit`/`offset` → unbounded result sets.
- Deprecated `backend-service/fly.toml:15` sets `DATABASE_URL="sqlite:///data/app.db"` but the code
  builds a `PgPool` (`.expect` panic if reused); `info.rs` still advertises `"sqlite-persistence"`.
- `projects-service/Dockerfile:1` `FROM rust:latest` (unpinned) vs backend's pinned `rust:1.90-bookworm`.

---

### 6. `infraportal` — React 19 / TypeScript

> Verified safe: `MarkdownResponse.tsx` renders via escaped JSX (no `dangerouslySetInnerHTML`);
> checkout is server-authoritative (Stripe Payment Links, `resolvePricingCheckout` requires `https://`);
> `leadScoring.ts` math is bounded/clamped; no committed secrets (`.env.local` gitignored).

#### 6.1 HIGH — Stored XSS via unsanitized inbound email HTML
**File:** `src/pages/PortalPage.tsx:481-484` (data `:933`, type `:82`). `email.body_html`
(from `GET /api/v1/projects/{id}/emails` — attacker-controllable inbound email) is rendered raw via
`dangerouslySetInnerHTML` with no sanitizer (no DOMPurify in `package.json`) and no CSP in `index.html`.
An injected `<img onerror=…>` runs in the authenticated portal origin, and the access token lives in
`localStorage` → token theft / account takeover.
**Fix:** `DOMPurify.sanitize(email.body_html)` (or render plaintext); add a CSP; sanitize server-side too.

#### 6.2 MEDIUM — Auth token accepted from URL and trusted without signature verification
**File:** `src/features/auth/AuthContext.tsx:66-102`; decoder `:22-34`. Reads a JWT from `?token=`/`#token=`
and only base64-decodes the payload (checks `sub`/`exp`, no signature). Enables login CSRF / session
fixation (`…/#token=<attacker JWT>` silently stores the attacker's session) and client-side privilege
spoofing (`roles:['admin']` flips `isAdmin` UI; backend still rejects on real calls). Token also lingers
in the URL until `replaceState` cleanup.
**Fix:** Don't accept bearer tokens from URL for a hash-routed SPA; prefer the existing cookie-based
`/auth/refresh` flow; treat any URL token as untrusted.

#### 6.3 MEDIUM — Client-side admin gate secret shipped in the bundle + `dev-admin` default
**File:** identical pattern in `AuditPage.tsx:9`, `SearchPage.tsx:9`, `ReportsPage.tsx:8`,
`ServiceHealthPage.tsx:7`, `ObservaboardPage.tsx:8`, `ConsultationsPage.tsx:19`, `SupportQueuePage.tsx:14`,
`UserDashboardPage.tsx:5` — `const ADMIN_KEY = import.meta.env.VITE_ADMIN_KEY ?? 'dev-admin'`, gate
`if (input === ADMIN_KEY)`. Any `VITE_*` value is inlined into the built JS (visible to anyone); unset →
falls back to `dev-admin`, unlocking every admin page. Real protection for API-backed pages is the backend
JWT, so impact is mainly the local-data pages (Consultations/Support/UserDashboard).
**Fix:** Remove the shared client-side key; gate on a verified `isAdmin` claim; never use `VITE_*` as a secret.

#### 6.4 MEDIUM — `VITE_ADMIN_JWT` admin bearer can be baked into the public bundle
**File:** `src/config.ts:28,45-52` (preferred source in `resolveAdminToken()`, used by `CrmAdminPage.tsx:1843`).
If set at build time, a long-lived admin JWT ships in the JS → full CRM/audit/spend API access. Empty by
default, but the supported pattern invites a leak. **Fix:** remove the build-time-JWT path; document that
`VITE_ADMIN_JWT` must never be set for deployed builds.

#### 6.5 MEDIUM — Admin routes gate on token *presence*, not admin *role*
**File:** `src/pages/CrmAdminPage.tsx:1830-1834` (`if (!token && !resolveAdminToken()) return <Gate/>`) —
any authenticated `client` passes; `main.tsx:131-144` renders admin pages purely off the URL hash with no
route guard. Authorization is entirely delegated to the backend. **Fix:** check `isAdmin` before rendering.

#### 6.6 LOW — infraportal misc
- Access token in `localStorage` (`AuthContext.tsx:20,81,107`) — XSS-exfiltratable (elevated by 6.1);
  prefer httpOnly cookie.
- `submitPublicLead` result discarded (`ContactCTA.tsx:21-73`, `ContactPage.tsx:34-62`) → the `'error'`
  phase can never fire; a failed delivery shows as success (mitigated by localStorage persistence).
- Free-text referral (possible third-party PII) sent to analytics (`ContactCTA.tsx:59-61`).
- No Content-Security-Policy in `index.html` (amplifies 6.1).

---

### 7. `observaboard` — Django 5

> Verified safe: `SECRET_KEY = config("SECRET_KEY")` (no default, fails loud); `DEBUG` defaults False;
> `ALLOWED_HOSTS` fail-closed; no raw SQL; no `fields='__all__'`; templates autoescape; the empty
> `ENV SECRET_KEY=` in the Dockerfile still fails closed via Django's own empty-key check.

#### 7.1 MEDIUM — CSRF via GET: `key_toggle`/`key_delete` mutate on any method
**File:** `dashboard/views.py:128-146` — neither checks `request.method`; Django's CSRF middleware
exempts GET, so `<img src=".../dashboard/keys/3/delete/">` deletes/toggles an API key when a logged-in
staff user loads an attacker page. (`key_create` correctly guards `if request.method == "POST"`.)
**Fix:** `@require_POST` / `@require_http_methods(["POST","DELETE"])`.

#### 7.2 MEDIUM — API keys stored plaintext and returned verbatim by the admin API
**File:** `events/models.py:10` (plaintext `key`), `events/serializers.py:30-37`, `events/views.py:201-203`.
The serializer comment says the key is masked after creation, but the field is `read_only` (not
`write_only`), so `GET /api/keys/` returns every key's full plaintext on every call. Auth also does a
non-constant-time plaintext equality lookup.
**Fix:** store only a hash; authenticate by hashing the presented key; return the raw key once at creation;
make the list field `write_only`/omit it.

#### 7.3 MEDIUM — Rate throttle collapses all API-key clients into one bucket
**File:** `events/authentication.py:47` (`ApiKeyUser.pk = None`) → `ScopedRateThrottle` keys on
`request.user.pk`, so every API-key request hashes to `throttle_ingest_None` — the `100/min` ingest limit
is a *global* ceiling shared by all clients (one busy client starves the rest).
**Fix:** give the sentinel user a stable identity from the key (or a custom throttle keyed on `request.auth`).

#### 7.4 MEDIUM — Cloud Tasks OIDC verified without audience (+ fail-open if SA email unset)
**File:** `events/views.py:24-48` (`_verify_cloud_tasks_token`), used by `ClassifyCallbackView` (:116).
`verify_oauth2_token(token, request)` with no `audience=` → any Google-signed token bearing that SA's
email (minted for *any* audience) is accepted; and if `CLOUD_TASKS_SA_EMAIL` is unset the function returns
`True` (open). Endpoint is `allUsers`-invocable.
**Fix:** pass `audience=<callback URL>` (matches `tasks.py:126`); fail closed if SA email unconfigured.

#### 7.5 MEDIUM — `seed_demo` creates an `admin/admin` superuser with no guard
**File:** `events/management/commands/seed_demo.py:88-96` — unconditionally creates superuser
`admin`/`admin`, no `DEBUG`/`--force` gate. Running against a real DB plants a trivially guessable admin.
**Fix:** refuse when `not settings.DEBUG`; never set a static password.

#### 7.6 LOW — observaboard misc
- Every active API key satisfies `IsAuthenticated` on the read endpoints (`events/views.py:147,165,180`),
  so an ingest-only key can also read all events. Add a scope/capability field.
- `deploy-cloud-run.yml:167` passes the API key as a CLI `--args` value → visible in the Job spec/process
  args; inject via `--set-secrets` instead.
- Non-UUID `event_id` in the classify callback → unhandled `ValidationError` → 500 (`views.py:130`,
  `tasks.py:66`); catch for a clean 400.
- Every authenticated API request issues a synchronous `UPDATE last_used_at` (`authentication.py:34-35`) —
  hot-row write contention on high-volume ingest; throttle the timestamp write.

---

### 8. Root infra / config

- **`gcp-setup.sh:142,148` — over-broad Workload Identity Federation trust.** Both the provider
  `attribute-condition` and the SA `workloadIdentityUser` binding scope to
  `attribute.repository_owner == 'rodmen07'` rather than a specific `attribute.repository`. Any workflow
  in **any** repo owned by that account can mint deploy-SA tokens (which hold `run.developer`,
  `artifactregistry.writer`, `secretmanager.secretAccessor`). Scope the binding to
  `attribute.repository/rodmen07/<repo>`. **Medium.**
- **`services.yaml` is unfilled + contradicts the README.** Most `platform`/`role`/`url` fields are `~`
  placeholders; `reporting-service`/`search-service` are marked `fly.io` here but GCP Cloud Run in the
  README deployment table; the file omits auth/ai-orchestrator/go-gateway/backend/event-stream/
  infraportal/observaboard entirely, and `discovery.paths` points at non-existent `services/`, `apps/`,
  `packages/`. README says "`services.yaml` is authoritative" — so this drift is user-facing. **Low.**
- **Root `Dockerfile`** installs `golang-go` from apt (often stale) alongside Rust — fine for a CI runner,
  but pin toolchains for reproducibility. **Low.**
- **Secrets scan (whole repo, tracked source):** no live API keys/tokens/private keys committed. The only
  hits are intentional insecure *defaults* — `AUTH_JWT_SECRET=dev-insecure-secret-change-me` (`.env.example`),
  `cms_oauth.py:13`/`user_oauth.py:16` OAuth-state defaults, `DJANGO_SECRET_KEY=dev-insecure-django-secret`
  (template). Good hygiene; the risk is the *fallbacks* firing in prod (see 2.6, 2.7, 5.1), not committed leaks.

---

### Cross-cutting themes

1. **Fail-open instead of fail-closed.** The same anti-pattern recurs: `AUTH_ENFORCED` defaulting false
   (backend), `dev_claims()`→admin when auth is off (projects/microservices), empty-allowlist admin gates
   passing everyone (auth-service dashboard), empty JWT secret disabling verification (event-stream), and
   the `ENVIRONMENT`-gated hardening never activating. Flip every one of these to deny-by-default.
2. **`X-Forwarded-For` trusted verbatim** in every rate limiter (auth-service, go-gateway, backend,
   projects). One shared "trusted client IP" helper (platform header / trusted-proxy depth) fixes all.
3. **Authorization ≠ authentication.** Many Rust handlers authenticate (valid JWT) but don't authorize —
   no owner/tenant scoping (search, spend, automation, integrations, microservices/projects) and forgeable
   actor fields (audit). Adopt the accounts/contacts/activities `owner_id = claims.sub` + admin-bypass
   pattern everywhere, and distinguish service tokens from user tokens.
4. **Divergent copies of shared logic.** The boot-panic (1.1) exists only because 8 services kept a local
   `build_decoder()` instead of `shared-auth`. Centralize auth/decoder/rate-limit/health helpers so a fix
   lands once.
5. **Secrets safe at rest, unsafe in fallback.** No committed secrets, but multiple services silently fall
   back to public dev defaults in production. Enforce required secrets at startup.

---

## Part 2 — Monetization Analysis

**What this project actually is:** the public face of **RM Cloud Consulting LLC** — a solo/boutique cloud
engineering consultancy — *plus* a working multi-service platform that already implements a productized
consulting funnel, a CRM, a client portal, an observability tool, and an LLM consulting assistant. Crucially,
**the monetization primitives are already built**: Stripe Payment Links, tiered pricing, a lead-scoring
engine, a lead magnet with an email sequence, and a client portal. The analysis below ties each strategy to
code that already exists, ordered from "closest to revenue" to "biggest lift."

### Tier A — Already wired; optimize the funnel (near-term revenue)

**A1. Productized consulting with hosted checkout (live today).**
`infraportal/public/content/pricing.json` + `retainers.json` + `stripe_payment_links.json` define real
paid offers with live Stripe links:
- Architecture Review **$100/hr** · Project **$5,200 (4-week sprint, 80 hrs)** · Retainers **$640 / $1,040 /
  $1,200 per week** at 8 / 16 / 24 hrs (Starter/Standard/Premium), i.e. **$80 / $65 / $50 per hour**.
  Repriced 2026-07-29: each step up deepens the discount by a uniform 15 points (20% / 35% / 50% off),
  bottoming at half the base rate.
  The prior ladder was an ANTI-discount (hour ranges put the bulk tiers at $100–$150/hr against a
  $125/hr base); `contentContract.test.ts` contract F now guards the property.
- `pricingCheckout.ts::resolvePricingCheckout` already routes a tier's CTA to its Stripe link (HTTPS-gated)
  and fires a `pricing_checkout_click` analytics event.

*Leverage:* This is the primary, realistic revenue engine and it's already deployable. The highest-ROI work
is **funnel optimization, not new product**: wire the `pricing_checkout_click`/`pricing_cta_click` events
(`utils/analytics.ts`) to a real analytics/attribution sink; A/B the `scarcity` copy ("Retainer slots fill
2-3 months ahead"); and add a deposit/checkout for the "Project" tier so discovery→paid has less friction.
The retainer tiers are the recurring-revenue backbone — push them (they're already `highlighted`).

**A2. Lead capture → scoring → CRM (built, underused).**
`leadScoring.ts` computes a 0-100 score from engagement type, budget band, timeline, and message detail, and
buckets to **hot/warm/nurture**; `leadIntake.ts::submitPublicLead` posts to a public intake endpoint; the
backend `lead_intake.rs` persists and forwards leads. The 11-service CRM
(`accounts`/`contacts`/`opportunities`/`activities`) can track the pipeline end-to-end.

*Leverage:* Route scored leads into `opportunities-service` with the score as the initial stage weight, so
"hot" leads get same-day follow-up (the differentiator the retainer tiers already promise). This directly
raises consulting close rates — the money is in *acting* on the score, which isn't automated yet.
*(Fix 5.5 first — the intake endpoint is currently floodable.)*

**A3. Lead magnet → email nurture → paid engagement.**
`lead-magnet.json` + `buildLeadMagnetIntakePayload` already implement an "Infrastructure Audit Checklist"
with a hybrid delivery and a 3-email sequence (`sequence_days: [0,3,7,14]`).

*Leverage:* This is a classic top-of-funnel. Productize the checklist into a **paid "Infrastructure Audit"**
(the `discovery audit` engagement already exists in `leadScoring.ts` weights) — a fixed-scope $500–$1,500
deliverable that converts nurture leads into paid discovery, then into retainers.

### Tier B — Reusable assets you can package (moderate lift)

**B1. SOC 2 baseline Terraform as a paid template.**
`microservices/terraform-soc2-baseline/` implements 9 SOC 2 Type II controls cloud-agnostically (GCP + AWS),
and the repo already has case-study pages (`Soc2CaseStudyPage.tsx`) and additional modules
(`terraform/soc2-cc9-vendor-risk/`, SLOs, Cloud Armor WAF, uptime checks).

*Monetization:* Sell the module as a **paid IaC template / starter kit** (one-time license) or as the
artifact bundled into a fixed-price **"SOC 2 readiness sprint"** — a high-value, well-scoped consulting
engagement that maps exactly to the `security review` engagement weight in `leadScoring.ts`. Gumroad/GitHub
Sponsors-style distribution needs almost no new code.

**B2. Client portal as a white-label offering.**
`projects-service` + the portal UI (`PortalPage.tsx`, milestones/deliverables/effort-tracking/progress feed/
Gmail sync) is a complete client-facing project-tracking portal with OAuth sign-in.

*Monetization:* Offer "**managed delivery + a branded client portal**" as a retainer upsell (clients see
burn-down, deliverables, and progress in real time — a tangible reason to stay on retainer), or license the
portal to *other* freelancers/agencies as a hosted product. It's differentiated because most consultants
deliver via email/Notion, not a purpose-built portal.

**B3. Observaboard as a standalone observability product.**
`observaboard` (Django 5 + DRF) is a webhook/event ingestion service with API-key auth, PostgreSQL full-text
search, classification, and a live event stream — plus the Go `event-stream-service` SSE hub and the
`go-gateway` mutation observer already feed it.

*Monetization:* Package as a **self-hostable "webhook/audit event dashboard"** (open-core: free core, paid
retention/alerting/multi-tenant) or a hosted micro-SaaS. Realistically this is a lead-gen/credibility asset
more than a standalone business for a solo operator — but it's a strong portfolio proof point that *sells the
consulting*. *(Gate the API keys and stream first — fixes 7.2, 3.3.)*

### Tier C — Platform-as-product (largest lift; strategic, not near-term)

**C1. The CRM itself as a niche SaaS.**
The 11 Rust microservices *are* a functioning CRM (accounts, contacts, opportunities, activities, automation,
integrations, reporting, search, audit, spend) with JWT auth, multi-region Terraform, SLOs, tracing, and a
gateway.

*Honest assessment:* Competing head-on with HubSpot/Pipedrive as a solo founder is not realistic. The
credible wedge is **vertical**: a CRM pre-wired for *cloud consultants/agencies* — because `spend-service`
already syncs AWS/GCP/Fly/GitHub billing, and `projects-service` already does client delivery. "CRM +
cloud-cost tracking + client portal for infra consultancies" is a differentiated niche no incumbent serves
well. This is a multi-quarter bet; the security/authorization gaps in Part 1 (tenant isolation in
search/spend/automation/integrations, the boot panic) are **hard blockers** — a multi-tenant SaaS cannot ship
with cross-tenant reads.

**C2. AI cloud-architecture review as a service.**
`ai-orchestrator-service` already exposes `/consult`, `/plan`, and `/agent` over Claude **and** Gemini, with
a consulting-persona prompt and guardrails.

*Monetization:* A **freemium "AI infra advisor"** — free single question to capture leads (feeding A2's
scoring), paid tier for deeper multi-turn reviews or a repo/architecture audit. It's a natural demo that both
showcases skill *and* qualifies leads for the human consulting tiers. *(Add auth + rate limiting first — fix
4.1; the endpoints currently allow unbounded paid-LLM spend.)*

### Recommended sequence

1. **Harden then amplify the existing funnel (A1–A3).** Fix the intake flood (5.5) and the paid-LLM exposure
   (4.1), then instrument analytics and push retainers + the paid audit. This is real money with code that
   already exists.
2. **Package one reusable asset (B1 SOC 2 template or B3 Observaboard open-core).** Low marginal effort, high
   credibility, feeds consulting leads.
3. **Treat C1/C2 as strategic bets** contingent on closing the tenant-isolation and availability bugs — those
   are non-negotiable prerequisites for anything multi-tenant.

The throughline: **this repo's best monetization is as a lead-generation and delivery engine for a
high-margin consulting practice** (the offers, checkout, scoring, and portal are already built), with select
reusable components (SOC 2 IaC, portal, observability) packaged as productized add-ons — not as a from-scratch
SaaS competing with funded incumbents.

---

*Report generated from a full read of the repository. Latent findings (guarded by current deploy config) are
labelled as such; confirm the boot-panic (1.1) and fail-open defaults with an integration/boot test before the
next redeploy.*
