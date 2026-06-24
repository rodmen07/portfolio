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
- [ ] Create RFC 7807 shared error module for Python (1 hour)
- [ ] Apply to auth-service (1.5 hours)
- [ ] Apply to ai-orchestrator-service (1.5 hours)
- [ ] Apply to observaboard (1 hour)
- [ ] Document pattern in microservices/CLAUDE.md + Go services (1 hour)
- [ ] Update docs/CONTRIBUTING.md with error handling guide (1 hour)
- **Total:** ~7.5 hours

### Week 4: Stability & Observability (8 hours)
- [ ] Add submodule integrity CI (1.5 hours)
- [ ] Implement structured logging across all services (5 hours)
- [ ] Create docs/OBSERVABILITY.md (1.5 hours)
- **Total:** ~8 hours

---

## Success Criteria

| Goal | Metric | Current | Target |
|-----|--------|---------|--------|
| **Type Safety** | Python type check passes | ❌ Not in CI | ✅ Required in CI |
| **Code Coverage** | Min coverage threshold enforced | ❌ No enforcement | ✅ 60% minimum |
| **Error Consistency** | % of services using RFC 7807 | 0% | 100% (all 16 services) |
| **Submodule Safety** | Failed pointer commits detected | 0% | 100% |
| **Observability** | Services with structured logs | 20% | 100% |
| **Documentation** | Critical docs exist | 30% | 100% |
