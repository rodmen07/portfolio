# InfraPortal API Documentation

**Live API Docs:** https://go-gateway-5gcrg4oiza-uc.a.run.app/api/docs (Swagger UI)

**OpenAPI Spec:** https://go-gateway-5gcrg4oiza-uc.a.run.app/api/openapi.json

## Overview

InfraPortal is a 15-service CRM platform deployed across GCP Cloud Run and Fly.io. All requests flow through the **go-gateway** reverse proxy, which handles authentication, rate limiting, logging, and distributed tracing.

```
Client
  ↓
go-gateway (auth, rate limits, circuit breaker)
  ↓
[11 services] (accounts, contacts, activities, automation, integrations, 
               opportunities, reporting, search, audit, projects + 2 others)
  ↓
PostgreSQL (Cloud SQL) + Redis (Memorystore)
```

## Authentication

### Get a Token

#### Option 1: Interactive Login
Visit https://rodmen07.github.io/infraportal/#/portal and sign in with GitHub or Google.

#### Option 2: API Login
```bash
curl -X POST https://go-gateway-5gcrg4oiza-uc.a.run.app/api/auth/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user@example.com", "password": "your-password"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Use the Token

Include the token in the `Authorization` header:
```bash
curl https://go-gateway-5gcrg4oiza-uc.a.run.app/api/accounts/api/v1/accounts \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR..."
```

### Token Expiry & Refresh

- Access tokens expire after **1 hour**
- On 401, call `/api/auth/auth/refresh` with your token to get a new one
- The refresh endpoint uses the same Bearer header; the client SDK (v1.16.2) handles this automatically

## Rate Limiting

All requests are rate-limited per client IP and route tier:

| Tier | Limit | Applies to |
|------|-------|-----------|
| Auth | 5 rps | `/api/auth/*` |
| Write | 30 rps | `POST/PATCH/PUT/DELETE` on CRM routes |
| Read | 60 rps | `GET` on reporting, search, events |

### Rate Limit Headers

Every response includes:
```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 27
X-RateLimit-Reset: 1622505600
Retry-After: 5        (only on 429)
```

On **429 Too Many Requests**, wait for `Retry-After` seconds before retrying.

## Services

| Service | Base Path | Primary Resources | Authenticated |
|---------|-----------|-------------------|---------------|
| Accounts | `/api/accounts` | `/api/v1/accounts` | Yes |
| Contacts | `/api/contacts` | `/api/v1/contacts` | Yes |
| Activities | `/api/activities` | `/api/v1/activities` | Yes |
| Opportunities | `/api/opportunities` | `/api/v1/opportunities` | Yes |
| Automation | `/api/automation` | `/api/v1/workflows` | Yes |
| Integrations | `/api/integrations` | `/api/v1/integrations/connections` | Yes |
| Search | `/api/search` | `/api/v1/search` | Yes |
| Reporting | `/api/reporting` | `/api/v1/reports`, `/api/v1/dashboard` | Yes |
| Projects | `/api/v1/projects` | `/api/v1/projects`, `/milestones`, `/deliverables` | Yes |
| Audit | `/api/v1/audit-events` | Read-only mutation log | Yes |
| System | `/health` | Gateway health | No |

## Error Format

All errors return a standard envelope:

```json
{
  "code": "validation_error",
  "message": "Field 'email' is required",
  "details": {
    "field": "email",
    "constraint": "required"
  }
}
```

**Common codes:**
- `validation_error` — 400 Bad Request (missing/invalid field)
- `not_found` — 404 Not Found
- `unauthorized` — 401 Unauthorized (bad/missing token)
- `forbidden` — 403 Forbidden (insufficient permissions)
- `internal_server_error` — 500 Server Error

## Common Patterns

### Pagination

List endpoints support `limit` and `offset`:

```bash
curl "https://go-gateway-5gcrg4oiza-uc.a.run.app/api/accounts/api/v1/accounts?limit=50&offset=100" \
  -H "Authorization: Bearer ..."
```

Response:
```json
{
  "data": [...],
  "total": 1250,
  "limit": 50,
  "offset": 100
}
```

### Filtering

Many endpoints support query params for filtering:

```bash
curl "https://go-gateway-5gcrg4oiza-uc.a.run.app/api/contacts/api/v1/contacts?lifecycle_stage=customer&account_id=abc123" \
  -H "Authorization: Bearer ..."
```

### Batch Operations

Use SDK or TypeScript client library (v1.16.2) for bulk inserts/updates. The API itself doesn't have a batch endpoint; iterate over individual creates.

## Client Libraries

**TypeScript/JavaScript SDK** (v1.16.2) — auto-generated from this spec:
```bash
npm install @rodmen07/infraportal-sdk
```

**Postman Collection** (v1.16.4) — import from:
https://rodmen07.github.io/infraportal/postman-collection.json

## Support

- **Swagger UI** — Try endpoints live (read-only): https://go-gateway-5gcrg4oiza-uc.a.run.app/api/docs
- **API Reference** — Full schema: https://rodmen07.github.io/infraportal/api-reference/
- **Issues** — https://github.com/rodmen07/portfolio/issues
