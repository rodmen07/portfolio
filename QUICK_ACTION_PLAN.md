# Portfolio Code Quality - Quick Action Plan

**Date Created:** June 24, 2026  
**Status:** Ready for implementation  
**Estimated Effort:** 16 hours (High Priority), 20 hours (Medium Priority)

---

## Top 5 Issues to Fix First

### 1. **Missing Type Checking in Python CI** ⚠️ CRITICAL
- **What:** No mypy/pyright validation in GitHub Actions CI
- **Impact:** Type errors discovered at runtime instead of in CI
- **Fix:** Add 2-line step to Python service workflows
  ```yaml
  - name: Type check
    run: mypy app/ --strict
  ```
- **Services affected:** auth-service, ai-orchestrator-service, observaboard
- **Effort:** 2 hours
- **ROI:** 8/10 - Catches type errors before deployment

### 2. **Inconsistent Error Response Formats** ⚠️ HIGH
- **What:** Services return different error formats; no RFC 7807 compliance
- **Impact:** Clients must handle multiple error formats; hard to build generic error handlers
- **Fix:** 
  - Create `docs/ERROR_CODES.md` catalog (2 hours)
  - Implement RFC 7807 in all 3 Python services (4 hours)
  - Document pattern in microservices/CLAUDE.md for Rust services (1 hour)
- **Example standardized response:**
  ```json
  {
    "type": "https://infraportal.dev/errors/validation_error",
    "title": "Validation Error",
    "status": 422,
    "detail": "Email already registered"
  }
  ```
- **Effort:** 7 hours
- **ROI:** 9/10 - Directly improves API usability

### 3. **No Code Coverage Enforcement** ⚠️ HIGH
- **What:** Tests run but coverage not tracked or enforced
- **Impact:** Coverage regressions go unnoticed
- **Fix:**
  - Rust: Add `cargo tarpaulin --out Xml` to microservices CI
  - Python: Add `pytest --cov app --cov-report=term-missing`
  - Go: Add `go test -cover ./...`
  - All: Upload to codecov.io and require >60% threshold
- **Effort:** 3 hours
- **ROI:** 8/10 - Prevents coverage debt accumulation

### 4. **Submodule Pointer Validation Missing** ⚠️ MEDIUM-HIGH
- **What:** Can push broken submodule commits to Portfolio without detection
- **Impact:** CI failures in dependent repos; wasted debugging time (per portfolio-notes: go-gateway commit was incomplete)
- **Fix:** Create `.github/workflows/submodule-integrity.yml` that verifies each submodule commit builds in isolation
- **Effort:** 3 hours
- **ROI:** 9/10 - Prevents production incidents

### 5. **No Structured Logging / Correlation IDs** ⚠️ MEDIUM
- **What:** Logs are unstructured; no correlation IDs for tracing requests across services
- **Impact:** Debugging cross-service issues is hard; can't aggregate logs by request
- **Fix:**
  - Add `structlog` to Python services (2 hours per service)
  - Use `tracing` crate in Rust with context (2 hours)
  - Use context + slog in Go (1 hour per service)
  - Inject correlation ID in API gateway + all downstream calls
- **Effort:** 10 hours
- **ROI:** 9/10 - Massive debugging improvement

---

## Implementation Roadmap

### Week 1: Immediate Wins (5 hours)
- [x] Type checking to Python CI (30 min per service × 3 = 1.5 hours)
- [x] Code coverage setup (1 hour setup + 1 hour per service CI = 3 hours)
- [x] Create ERROR_CODES.md reference (30 min)
- **Total:** ~5.5 hours

### Week 2-3: Error Handling (8 hours)
- [x] Create RFC 7807 shared error module for Python (1 hour)
- [x] Apply to auth-service (1.5 hours)
- [x] Apply to ai-orchestrator-service (1.5 hours)
- [x] Apply to observaboard (1 hour)
- [x] Document pattern in microservices/CLAUDE.md + Go services (1 hour)
- [x] Update docs/CONTRIBUTING.md with error handling guide (1 hour)
- **Total:** ~7.5 hours

### Week 4: Stability & Observability (8 hours)
- [x] Add submodule integrity CI (1.5 hours)
- [x] Implement structured logging across all services (5 hours)
- [x] Create docs/OBSERVABILITY.md (1.5 hours)
- **Total:** ~8 hours

### Weeks 5-6: Documentation (6 hours)
- [x] Create docs/SECURITY.md (2 hours)
- [x] Create docs/TESTING.md (1.5 hours)
- [x] Create docs/DEPLOYMENT.md (1.5 hours)
- [x] Update README with link to CODE_QUALITY_REVIEW.md (0.5 hours)
- **Total:** ~5.5 hours

---

## File Changes Required

### Immediate (Week 1)

**1. microservices/.github/workflows/rust.yml**
```yaml
- name: Test coverage
  run: cargo tarpaulin --out Xml --exclude-files tests/
- name: Upload coverage
  uses: codecov/codecov-action@v4
```

**2. auth-service/.github/workflows/python.yml** (if exists) or create
```yaml
- name: Type check
  run: mypy app/ --strict
- name: Test coverage
  run: pytest --cov app --cov-report=term-missing --cov-report=xml
- name: Upload coverage
  uses: codecov/codecov-action@v4
```

**3. create `docs/ERROR_CODES.md`**
```markdown
# API Error Codes Reference

| Code | Status | Description | Recovery |
|------|--------|-------------|----------|
| `VALIDATION_ERROR` | 422 | Invalid input data | Fix inputs; see `detail` field |
| `UNAUTHORIZED` | 401 | Invalid/missing token | Get new token from /auth/token |
| `FORBIDDEN` | 403 | Insufficient permissions | Check JWT roles or contact admin |
| ...
```

### Medium Priority (Weeks 2-3)

**4. Create `auth-service/app/errors.py`**
```python
from pydantic import BaseModel
from typing import Optional

class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: Optional[str] = None

@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    # Return RFC 7807 format
    return JSONResponse(
        status_code=500,
        content=ProblemDetail(...).model_dump()
    )
```

**5. Create `.github/workflows/submodule-integrity.yml`**
```yaml
name: Submodule Integrity Check

on: pull_request

jobs:
  check-submodules:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          submodules: recursive
      
      - name: Verify submodule commits build
        run: |
          for submodule in $(git config --file .gitmodules --name-only | grep path | cut -d. -f2); do
            path=$(git config --file .gitmodules --get "submodule.$submodule.path")
            echo "Checking $path..."
            if [ -f "$path/Cargo.toml" ]; then
              cd "$path" && cargo check && cd - || exit 1
            elif [ -f "$path/go.mod" ]; then
              cd "$path" && go build ./... && cd - || exit 1
            fi
          done
```

### High Priority (Weeks 4+)

**6. Create `docs/SECURITY.md`**
- JWT auth flow
- Role-based access control (RBAC)
- OAuth patterns (GitHub + Google)
- CORS configuration
- Secrets management
- Input validation strategies
- SQL injection prevention

**7. Create `docs/TESTING.md`**
- Unit test patterns per language
- Integration test structure
- Test naming conventions
- Coverage expectations
- Local test execution

**8. Create `docs/OBSERVABILITY.md`**
- Structured logging patterns
- Correlation ID flow
- Distributed tracing setup (OpenTelemetry)
- Metrics to track per service
- Alert thresholds

---

## Success Criteria

| Goal | Metric | Current | Target |
|------|--------|---------|--------|
| **Type Safety** | Python type check passes | ❌ Not in CI | ✅ Required in CI |
| **Code Coverage** | Min coverage threshold enforced | ❌ No enforcement | ✅ 60% minimum |
| **Error Consistency** | % of services using RFC 7807 | 0% | 100% (all 16 services) |
| **Submodule Safety** | Failed pointer commits detected | 0% | 100% |
| **Observability** | Services with structured logs | 20% | 100% |
| **Documentation** | Critical docs exist (ERROR_CODES, SECURITY, TESTING, OBSERVABILITY) | 30% | 100% |

---

## Rollout Checklist

### Phase 1: Type Checking & Coverage (1 week)
- [ ] Add type checking to python CI
- [ ] Add coverage to rust CI
- [ ] Add coverage to go ci
- [ ] Add coverage to ts ci
- [ ] Create docs/ERROR_CODES.md
- [ ] PR review + merge

### Phase 2: Submodule Safety (1 week)
- [ ] Create submodule-integrity.yml
- [ ] Test on PR
- [ ] Enable on main
- [ ] Document in CONTRIBUTING.md

### Phase 3: Error Standardization (2 weeks)
- [ ] Create shared error modules (Python, Go, Rust)
- [ ] Apply to auth-service
- [ ] Apply to ai-orchestrator-service
- [ ] Apply to observaboard
- [ ] Update docs/CONTRIBUTING.md
- [ ] PR review + merge

### Phase 4: Observability (2 weeks)
- [ ] Add structlog to Python services
- [ ] Add tracing context to Rust services
- [ ] Add slog context to Go services
- [ ] Add correlation ID injection in go-gateway
- [ ] Create docs/OBSERVABILITY.md
- [ ] PR review + merge

### Phase 5: Documentation (1 week)
- [ ] Create docs/SECURITY.md
- [ ] Create docs/TESTING.md
- [ ] Create docs/DEPLOYMENT.md
- [ ] Update README with links
- [ ] PR review + merge

---

## Team Assignments (Suggested)

| Task | Owner | Duration | Notes |
|------|-------|----------|-------|
| Type checking (Python) | Lead | 1 hour | Low risk; easy to parallelize |
| Coverage setup (all langs) | Lead + 1 other | 3 hours | Use codecov.io for automation |
| Error codes reference | Tech lead | 2 hours | Audit all services |
| Submodule integrity | DevOps/Lead | 2 hours | One-time setup |
| RFC 7807 implementation | 1-2 devs | 8 hours | Can parallelize per service |
| Structured logging | 2 devs | 10 hours | More involved; split by language |
| Documentation | Tech lead + 1 other | 6 hours | High-level writing |

---

## References

- [CODE_QUALITY_REVIEW.md](CODE_QUALITY_REVIEW.md) - Full detailed review
- [RFC 7807 - Problem Details](https://datatracker.ietf.org/doc/html/rfc7807)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [OpenTelemetry](https://opentelemetry.io/)
- [Codecov Documentation](https://docs.codecov.com/)

---

## Notes

- All timestamps are estimates; adjust based on team velocity
- Prioritize type checking + coverage + error codes in first 2 weeks for quick wins
- Structured logging and distributed tracing can happen in parallel with error standardization
- Documentation can be written incrementally; doesn't block other work

