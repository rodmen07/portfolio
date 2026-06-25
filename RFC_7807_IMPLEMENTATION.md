# RFC 7807 Implementation Guide

**Status:** Reference document for future implementation  
**Priority:** Medium (Week 2-3 of improvement plan)  
**Estimated Effort:** 8 hours across all Python services  

---

## Overview

This guide documents how to implement [RFC 7807 Problem Details](https://datatracker.ietf.org/doc/html/rfc7807) error responses across all Portfolio microservices. RFC 7807 provides a standardized format for HTTP error responses, making it easier for clients to parse and handle errors consistently.

### Why RFC 7807?

**Current State:** Services return inconsistent error formats
```python
# auth-service
{"detail": "Invalid token"}

# ai-orchestrator-service
{"error": "LLM timeout", "code": 504}

# Rust services
JSON with service-specific structure
```

**Target State:** Consistent RFC 7807 format
```json
{
  "type": "https://infraportal.dev/errors/unauthorized",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Token has expired",
  "instance": "/api/v1/contacts?account_id=acct_123"
}
```

---

## Implementation Steps

### Phase 1: Create Shared Error Module (2 hours)

#### 1.1 Python - Create `shared_errors.py`

Create a new file in each service: `app/errors.py`

```python
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import HTTPException


class ErrorType(str, Enum):
    """Error type URIs following RFC 7807 pattern"""
    UNAUTHORIZED = "https://infraportal.dev/errors/unauthorized"
    FORBIDDEN = "https://infraportal.dev/errors/forbidden"
    NOT_FOUND = "https://infraportal.dev/errors/not_found"
    VALIDATION_ERROR = "https://infraportal.dev/errors/validation_error"
    DUPLICATE_KEY = "https://infraportal.dev/errors/duplicate_key"
    RATE_LIMIT = "https://infraportal.dev/errors/rate_limit"
    INTERNAL_ERROR = "https://infraportal.dev/errors/internal_error"


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details response model"""
    type: str
    title: str
    status: int
    detail: str
    instance: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "https://infraportal.dev/errors/validation_error",
                "title": "Validation Error",
                "status": 422,
                "detail": "Email must be valid format",
                "instance": "/api/v1/accounts/register"
            }
        }


def create_problem_detail(
    error_type: ErrorType,
    title: str,
    status: int,
    detail: str,
    instance: Optional[str] = None
) -> dict:
    """Create an RFC 7807 problem detail response"""
    return {
        "type": error_type.value,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance
    }


def unauthorized_error(detail: str = "Invalid or missing credentials") -> HTTPException:
    """Create RFC 7807 unauthorized error"""
    return HTTPException(
        status_code=401,
        detail=create_problem_detail(
            error_type=ErrorType.UNAUTHORIZED,
            title="Unauthorized",
            status=401,
            detail=detail
        )
    )


def forbidden_error(detail: str = "Insufficient permissions") -> HTTPException:
    """Create RFC 7807 forbidden error"""
    return HTTPException(
        status_code=403,
        detail=create_problem_detail(
            error_type=ErrorType.FORBIDDEN,
            title="Forbidden",
            status=403,
            detail=detail
        )
    )


def not_found_error(resource: str, identifier: Any) -> HTTPException:
    """Create RFC 7807 not found error"""
    return HTTPException(
        status_code=404,
        detail=create_problem_detail(
            error_type=ErrorType.NOT_FOUND,
            title="Not Found",
            status=404,
            detail=f"{resource} with ID '{identifier}' not found"
        )
    )


def validation_error(detail: str, instance: Optional[str] = None) -> HTTPException:
    """Create RFC 7807 validation error"""
    return HTTPException(
        status_code=422,
        detail=create_problem_detail(
            error_type=ErrorType.VALIDATION_ERROR,
            title="Unprocessable Entity",
            status=422,
            detail=detail,
            instance=instance
        )
    )


def duplicate_key_error(field: str, value: str) -> HTTPException:
    """Create RFC 7807 duplicate key error"""
    return HTTPException(
        status_code=409,
        detail=create_problem_detail(
            error_type=ErrorType.DUPLICATE_KEY,
            title="Conflict",
            status=409,
            detail=f"Unique constraint violation: '{field}' = '{value}' already exists"
        )
    )
```

#### 1.2 Add Exception Handler Middleware

In each service's `app/main.py`, add:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.errors import ProblemDetail, create_problem_detail, ErrorType
import logging

logger = logging.getLogger(__name__)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with RFC 7807 format"""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:])
        errors.append(f"{field}: {error['msg']}")
    
    detail = " | ".join(errors) if errors else "Invalid request data"
    
    return JSONResponse(
        status_code=422,
        content=create_problem_detail(
            error_type=ErrorType.VALIDATION_ERROR,
            title="Unprocessable Entity",
            status=422,
            detail=detail,
            instance=str(request.url.path)
        )
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with RFC 7807 format"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content=create_problem_detail(
            error_type=ErrorType.INTERNAL_ERROR,
            title="Internal Server Error",
            status=500,
            detail="An unexpected error occurred. Check request ID in logs.",
            instance=str(request.url.path)
        )
    )
```

### Phase 2: Apply to auth-service (2 hours)

#### 2.1 Replace Error Responses

**Before:**
```python
@app.post("/auth/token", response_model=TokenResponse)
async def issue_token(request: TokenRequest) -> TokenResponse:
    try:
        token = build_access_token(request.subject, request.roles)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=3600
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**After:**
```python
from app.errors import validation_error, forbidden_error

@app.post("/auth/token", response_model=TokenResponse)
async def issue_token(request: TokenRequest) -> TokenResponse:
    try:
        if not request.subject:
            raise validation_error("Subject is required", "/auth/token")
        
        token = build_access_token(request.subject, request.roles)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=3600
        )
    except ValueError as e:
        raise validation_error(str(e), "/auth/token")
```

#### 2.2 Test Coverage

Add test case:
```python
def test_auth_token_returns_rfc7807_format():
    client = TestClient(app)
    response = client.post(
        "/auth/token",
        json={"subject": "", "roles": []}
    )
    
    assert response.status_code == 422
    body = response.json()
    
    # Verify RFC 7807 format
    assert "type" in body
    assert "title" in body
    assert "status" in body
    assert body["status"] == 422
    assert "detail" in body
    assert body["type"].startswith("https://infraportal.dev/errors/")
```

### Phase 3: Apply to ai-orchestrator-service (2 hours)

#### 3.1 Update LLM Error Handling

**Before:**
```python
@app.post("/plan")
async def create_plan(request: PlanRequest):
    try:
        tasks = await llm_client.generate_tasks(request.goal)
        return {"tasks": tasks}
    except TimeoutError:
        raise HTTPException(status_code=504, detail="LLM response timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")
```

**After:**
```python
from app.errors import validation_error
import logging

logger = logging.getLogger(__name__)

@app.post("/plan")
async def create_plan(request: PlanRequest):
    try:
        tasks = await llm_client.generate_tasks(request.goal)
        return {"tasks": tasks}
    except TimeoutError:
        # 504 Gateway Timeout but with RFC 7807 format
        raise HTTPException(
            status_code=504,
            detail=create_problem_detail(
                error_type=ErrorType.INTERNAL_ERROR,
                title="Gateway Timeout",
                status=504,
                detail="LLM service did not respond within 300 seconds",
                instance="/plan"
            )
        )
    except ValueError as e:
        raise validation_error(str(e), "/plan")
    except Exception as e:
        logger.error(f"LLM error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=create_problem_detail(
                error_type=ErrorType.INTERNAL_ERROR,
                title="Internal Server Error",
                status=500,
                detail="Failed to generate plan. Check logs for details.",
                instance="/plan"
            )
        )
```

### Phase 4: Apply to observaboard (2 hours)

#### 4.1 Update Django REST Framework Error Handling

Create `app/exceptions.py`:
```python
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is not None:
        # Convert DRF exception to RFC 7807 format
        error_data = response.data
        
        status_code = response.status_code
        
        rfc7807_response = {
            "type": f"https://infraportal.dev/errors/{get_error_type(status_code)}",
            "title": get_error_title(status_code),
            "status": status_code,
            "detail": error_data.get("detail") or str(error_data),
            "instance": context.get("request").path if context.get("request") else None
        }
        
        return Response(rfc7807_response, status=status_code)
    
    return response


def get_error_type(status_code):
    """Map HTTP status to error type"""
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        422: "validation_error",
        429: "rate_limit",
        500: "internal_error",
    }
    return mapping.get(status_code, "internal_error")


def get_error_title(status_code):
    """Map HTTP status to error title"""
    mapping = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
    }
    return mapping.get(status_code, "Internal Server Error")
```

Configure in `settings.py`:
```python
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'app.exceptions.custom_exception_handler',
}
```

---

## Testing Strategy

### Unit Tests

```python
def test_unauthorized_error_format():
    """Verify unauthorized error follows RFC 7807"""
    exc = unauthorized_error("Token expired")
    assert exc.status_code == 401
    assert exc.detail["type"] == "https://infraportal.dev/errors/unauthorized"
    assert exc.detail["title"] == "Unauthorized"
    assert exc.detail["detail"] == "Token expired"


def test_validation_error_format():
    """Verify validation error follows RFC 7807"""
    exc = validation_error("Email is invalid", "/register")
    assert exc.status_code == 422
    assert exc.detail["type"] == "https://infraportal.dev/errors/validation_error"
    assert exc.detail["instance"] == "/register"
```

### Integration Tests

```python
def test_api_error_consistency():
    """Verify all API errors follow RFC 7807 format"""
    client = TestClient(app)
    
    # Test various error scenarios
    responses = [
        client.get("/api/v1/nonexistent"),  # 404
        client.post("/auth/token", json={}),  # 422
        client.get("/api/v1/protected"),  # 401
    ]
    
    for response in responses:
        body = response.json()
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body
        assert body["type"].startswith("https://infraportal.dev/errors/")
```

---

## Rollout Plan

### Week 1: Implementation
- [ ] Create shared error modules across all 3 Python services
- [ ] Add exception handlers
- [ ] Apply to auth-service endpoints
- [ ] Update tests

### Week 2: Verification
- [ ] Run comprehensive test suite
- [ ] Test with real clients (frontend, CLI)
- [ ] Verify Codecov doesn't flag coverage regressions
- [ ] Document in README files

### Week 3: Go/Rust Services
- [ ] Update Go services (event-stream-service, go-gateway) with similar approach
- [ ] Document error format for Rust services (via axum response types)
- [ ] Update API documentation

---

## Backward Compatibility

### Migration Strategy

During transition period, support both formats:
```python
@app.middleware("http")
async def add_legacy_error_format(request: Request, call_next):
    """Add legacy error format for backward compatibility"""
    response = await call_next(request)
    
    if response.status_code >= 400:
        if isinstance(response.body, dict) and "type" in response.body:
            # Already RFC 7807, add legacy field
            response.body["error_code"] = response.body["type"].split("/")[-1]
    
    return response
```

Remove legacy format after 2-4 week deprecation period (announce in CHANGELOG).

---

## Related Files

- [docs/ERROR_CODES.md](docs/ERROR_CODES.md) - Error code reference
- [RFC 7807 Specification](https://datatracker.ietf.org/doc/html/rfc7807)
- auth-service: Will have comprehensive error handling after implementation
- ai-orchestrator-service: Currently using non-standard format
- observaboard: Using default Django REST Framework format

---

## Success Criteria

- [ ] All 3 Python services return RFC 7807 format
- [ ] Tests validate RFC 7807 compliance
- [ ] Error codes documented in docs/ERROR_CODES.md
- [ ] Frontend tested with new error format
- [ ] Clients can parse all errors with single handler
- [ ] Coverage maintains or improves

