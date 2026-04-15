"""
Task catalog for the productionizer agent.
55 tasks total: 11 services × 5 gap types, iterated gap-first so all services
receive the highest-priority improvement before any receive the second, etc.
"""

SERVICES = [
    "accounts-service",
    "activities-service",
    "audit-service",
    "automation-service",
    "contacts-service",
    "integrations-service",
    "opportunities-service",
    "projects-service",
    "reporting-service",
    "search-service",
    "spend-service",
]

# Gap IDs in priority order (highest impact first)
GAPS = [
    "structured-logging",    # Add tracing::info!/debug! to handler business logic
    "dynamic-health",        # /health and /ready do a live DB ping instead of hardcoded "ok"
    "error-details",         # Populate ApiError.details on all validation errors
    "audit-error-handling",  # Replace silent let _ = emit_audit with warn! logging
    "error-path-tests",      # Add integration test cases for error paths not yet covered
    "unwrap-elimination",    # Replace .unwrap()/.expect() in handler code with ? or error returns
    "input-validation",      # Add length/non-empty validation on string fields before DB ops
]


def build_task_queue() -> list[tuple[str, str]]:
    """Return all (service, gap) pairs in gap-first priority order."""
    return [(gap, service) for gap in GAPS for service in SERVICES]


def pick_next_task(state: dict) -> tuple[str, str] | None:
    """
    Return the first (service, gap) pair not yet in state['completed'], or None
    if all 55 tasks are done.
    """
    completed = {(svc, gap) for svc, gap in state.get("completed", [])}
    for gap, service in build_task_queue():
        if (service, gap) not in completed:
            return service, gap
    return None


_SERVICE_TO_DB: dict[str, str] = {
    "accounts-service":     "accounts",
    "activities-service":   "activities",
    "audit-service":        "audit",
    "automation-service":   "workflows",
    "contacts-service":     "contacts",
    "integrations-service": "connections",
    "opportunities-service": "opportunities",
    "projects-service":     "projects",
    "reporting-service":    "reports",
    "search-service":       "documents",
    "spend-service":        "spend",
}


def db_name_for_service(service: str) -> str:
    """Return the PostgreSQL database name for a given service.

    These names match the CI setup in microservices/.github/workflows/rust.yml.
    """
    if service not in _SERVICE_TO_DB:
        raise ValueError(f"Unknown service: {service}. Add it to _SERVICE_TO_DB.")
    return _SERVICE_TO_DB[service]
