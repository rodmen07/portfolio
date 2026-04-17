"""
Task catalog for the productionizer agent — infraportal UI/UX edition.
Target: rodmen07/infraportal (React 19 / TypeScript strict / Vite 5 / Tailwind CSS)
30 tasks total: 10 pages × 3 UI/UX gap types, iterated gap-first.
"""

PAGES = [
    "PortalPage",         # src/pages/PortalPage.tsx       — main task portal (~34KB)
    "CrmAdminPage",       # src/pages/CrmAdminPage.tsx     — CRM admin (~94KB)
    "AuditPage",          # src/pages/AuditPage.tsx        — audit log viewer
    "ReportsPage",        # src/pages/ReportsPage.tsx      — reports dashboard
    "ObservaboardPage",   # src/pages/ObservaboardPage.tsx — observability metrics
    "SearchPage",         # src/pages/SearchPage.tsx       — cross-domain search
    "ServiceHealthPage",  # src/pages/ServiceHealthPage.tsx — service health monitor
    "UserDashboardPage",  # src/pages/UserDashboardPage.tsx — user/admin dashboard
    "PortalLoginPage",    # src/pages/PortalLoginPage.tsx  — login form
    "ContactPage",        # src/pages/ContactPage.tsx      — contact/demo form
]

# Gap IDs in priority order (highest visual impact first)
GAPS = [
    "loading-skeleton",   # Replace text spinners with layout-matching skeleton screens
    "empty-state",        # Replace bare "no data" text with designed empty state UI
    "error-ux",           # Replace inline error text with structured error cards + retry
]


def build_task_queue() -> list[tuple[str, str]]:
    """Return all (page, gap) pairs in gap-first priority order."""
    return [(gap, page) for gap in GAPS for page in PAGES]


def pick_next_task(state: dict) -> tuple[str, str] | None:
    """
    Return the first (page, gap) pair not yet in state['completed'], or None
    if all 30 tasks are done.
    """
    completed = {(page, gap) for page, gap in state.get("completed", [])}
    for gap, page in build_task_queue():
        if (page, gap) not in completed:
            return page, gap
    return None


def file_path_for_page(page: str) -> str:
    """Return the src-relative file path for a given page component."""
    return f"src/pages/{page}.tsx"
