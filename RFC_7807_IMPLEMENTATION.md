# RFC 7807 Implementation Guide

**Status:** Reference document for future implementation  
**Priority:** Medium (Week 2-3 of improvement plan)  
**Estimated Effort:** 8 hours across all Python services  

---

## Overview

This guide documents how to implement [RFC 7807 Problem Details](https://datatracker.ietf.org/doc/html/rfc7807) error responses across all Portfolio microservices.

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
```

#### 1.2 Add Exception Handler Middleware

In each service's `app/main.py`, add:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with RFC 7807 format"""
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
- [ ] Test with real clients
- [ ] Verify Codecov coverage
- [ ] Document in README files

### Week 3: Go/Rust Services
- [ ] Update Go services with similar approach
- [ ] Document error format for Rust services
- [ ] Update API documentation

---

## Success Criteria

- [ ] All 3 Python services return RFC 7807 format
- [ ] Tests validate RFC 7807 compliance
- [ ] Error codes documented in docs/ERROR_CODES.md
- [ ] Frontend tested with new error format
- [ ] Clients can parse all errors with single handler
- [ ] Coverage maintains or improves
