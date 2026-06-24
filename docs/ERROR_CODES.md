# API Error Codes Reference

This document provides a comprehensive reference for all error codes used across the Portfolio microservices. All error responses should follow [RFC 7807 - Problem Details](https://datatracker.ietf.org/doc/html/rfc7807) format.

---

## Error Response Format

All error responses use the standard RFC 7807 Problem Details format:

```json
{
  "type": "https://infraportal.dev/errors/validation_error",
  "title": "Validation Error",
  "status": 422,
  "detail": "Email address is invalid",
  "instance": "/api/v1/accounts/register"
}
```

**Fields:**
- `type` - URI identifying the error type (URL to error documentation)
- `title` - Human-readable error category
- `status` - HTTP status code
- `detail` - Specific error message for this occurrence
- `instance` - URI of the request that caused the error (optional)

---

## Authentication & Authorization Errors

| Code | Status | Title | Detail Example | Recovery Action |
|------|--------|-------|-----------------|------------------|
| `UNAUTHORIZED` | 401 | Unauthorized | Invalid or expired token | Obtain new token from `/auth/token` endpoint |
| `INVALID_TOKEN` | 401 | Unauthorized | Token signature verification failed | Request new token with valid credentials |
| `EXPIRED_TOKEN` | 401 | Unauthorized | Token has expired | Refresh token or re-authenticate |
| `MISSING_AUTH` | 401 | Unauthorized | Missing Authorization header | Add `Authorization: Bearer <token>` header |
| `FORBIDDEN` | 403 | Forbidden | User lacks required role 'admin' | Request access from administrator |
| `INSUFFICIENT_PERMISSIONS` | 403 | Forbidden | Endpoint requires 'planner' role | Contact system administrator |
| `TOKEN_REVOKED` | 401 | Unauthorized | Token has been revoked | Obtain new token from `/auth/token` |

---

## Input Validation Errors

| Code | Status | Title | Detail Example | Recovery Action |
|------|--------|-------|-----------------|------------------|
| `VALIDATION_ERROR` | 422 | Unprocessable Entity | Email must be valid format | Correct input and retry |
| `INVALID_EMAIL` | 422 | Unprocessable Entity | Email address is invalid | Provide valid email address |
| `INVALID_UUID` | 422 | Unprocessable Entity | ID must be valid UUID | Use valid UUID format (e.g., 550e8400-e29b-41d4-a716-446655440000) |
| `MISSING_FIELD` | 400 | Bad Request | Required field 'email' is missing | Include all required fields |
| `INVALID_JSON` | 400 | Bad Request | Request body is not valid JSON | Fix JSON syntax and retry |
| `FIELD_TOO_LONG` | 422 | Unprocessable Entity | Field 'name' exceeds max length 255 | Shorten field value to 255 characters |
| `FIELD_TOO_SHORT` | 422 | Unprocessable Entity | Password must be at least 8 characters | Provide longer value |
| `INVALID_ENUM` | 422 | Unprocessable Entity | Status must be one of: active, inactive, pending | Use valid enum value |

---

## Resource Errors

| Code | Status | Title | Detail Example | Recovery Action |
|------|--------|-------|-----------------|------------------|
| `NOT_FOUND` | 404 | Not Found | Account with ID 'abc123' not found | Verify resource exists or use correct ID |
| `RESOURCE_DELETED` | 404 | Not Found | Resource has been deleted | Use archived resource endpoint or create new |
| `ACCOUNT_NOT_FOUND` | 404 | Not Found | Account 'acct_12345' does not exist | Use correct account ID |
| `CONTACT_NOT_FOUND` | 404 | Not Found | Contact 'contact_99999' does not exist | Verify contact ID is correct |
| `ALREADY_EXISTS` | 409 | Conflict | Email 'user@example.com' already registered | Use different email or recover existing account |
| `DUPLICATE_KEY` | 409 | Conflict | Unique constraint violation on field 'email' | Use unique value for this field |
| `VERSION_CONFLICT` | 409 | Conflict | Resource version mismatch; expected v2 but got v1 | Refresh resource and retry |

---

## Business Logic Errors

| Code | Status | Title | Detail Example | Recovery Action |
|------|--------|-------|-----------------|------------------|
| `INVALID_STATE_TRANSITION` | 422 | Unprocessable Entity | Cannot transition from 'active' to 'draft' | Check workflow rules for valid transitions |
| `QUOTA_EXCEEDED` | 429 | Too Many Requests | Account has exceeded monthly API call limit | Upgrade account tier or wait until reset |
| `RATE_LIMIT_EXCEEDED` | 429 | Too Many Requests | Too many requests; limit is 100/min | Wait and retry; implement exponential backoff |
| `INVALID_OPERATION` | 422 | Unprocessable Entity | Cannot archive account with active projects | Complete or transfer active projects first |
| `INSUFFICIENT_BALANCE` | 402 | Payment Required | Insufficient credits to complete operation | Add credits to account |
| `OPERATION_FAILED` | 422 | Unprocessable Entity | Account validation failed; contact support | Verify account details match requirements |

---

## Integration & External Service Errors

| Code | Status | Title | Detail Example | Recovery Action |
|------|--------|-------|-----------------|------------------|
| `OAUTH_FAILED` | 401 | Unauthorized | GitHub OAuth token exchange failed | Re-initiate OAuth login flow |
| `OAUTH_USER_NOT_FOUND` | 404 | Not Found | OAuth user not found in our system | Complete account registration |
| `EXTERNAL_SERVICE_ERROR` | 502 | Bad Gateway | GitHub API returned 500 error | Retry later; contact support if persists |
| `INTEGRATION_ERROR` | 502 | Bad Gateway | Webhook delivery failed after 3 retries | Check webhook endpoint availability |
| `PAYMENT_GATEWAY_ERROR` | 502 | Bad Gateway | Payment processor returned error | Retry payment or use different payment method |
| `EMAIL_DELIVERY_FAILED` | 502 | Bad Gateway | Email delivery service error | Retry; check email address validity |

---

## Rate Limiting Errors

| Code | Status | Title | Detail Example | Recovery Action |
|------|--------|-------|-----------------|------------------|
| `RATE_LIMIT` | 429 | Too Many Requests | Rate limit exceeded: 100 requests/min | Wait 60 seconds and retry |
| `QUOTA_LIMIT` | 429 | Too Many Requests | Monthly quota exhausted (10,000 requests) | Upgrade plan or wait until reset |
| `CONCURRENT_REQUESTS_EXCEEDED` | 429 | Too Many Requests | Too many concurrent connections (max 10) | Reduce concurrent requests |

**Response headers:**
```
Retry-After: 60
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1719259200
```

---

## Debugging Guide

### Example 1: User gets 401 Unauthorized

Token expired. Call `/auth/token` with current credentials to get new token.

### Example 2: Validation fails with 422

User provided invalid email. Validate input client-side before sending.

### Example 3: Rate limit hit with 429

Implement exponential backoff. Use `Retry-After` header before retrying.

---

## Adding New Error Codes

When adding a new error code to a service:

1. **Add to this file** with code name, HTTP status, title, detail example, and recovery action
2. **Implement in code** using RFC 7807 format
3. **Document in service README** with example curl commands
4. **Update type stubs** if using TypeScript/mypy
