# Productionizer Agent - Decoupled Architecture

> **Version**: 2.0 (Decoupled from GitHub Actions)  
> **Status**: Ready for local + CI/CD execution  
> **Model**: Google Gemini 2.5 Flash

## Overview

The **productionizer** is an autonomous UI/UX improvement agent for the **infraportal** React/TypeScript frontend. It systematically improves 10 page components across 3 UI/UX gap types (30 total tasks).

This version **decouples the agent from GitHub Actions**, allowing it to:
- ✅ Run through all 30 tasks in **one invocation** (no time limits)
- ✅ Execute **locally** without workflow dispatch
- ✅ Handle PR creation, README updates, and state management in Python
- ✅ Scale from single task (for testing) to full loop (production)

## Architecture

### Core Components

| File | Purpose |
|------|---------|
| `main.py` | Single-task executor (Gemini agentic loop + verification) |
| `runner.py` | **NEW** Full-loop orchestrator (task selection, PR creation, state sync) |
| `tasks.py` | Task catalog (30 page/gap combinations) |
| `tools.py` | Agent tools (read_file, write_file, run_shell) |
| `prompts.py` | System + task prompts for Gemini |
| `update_readme.py` | Progress tracking in infraportal/README.md |
| `state.json` | Persistent completion state |

### Execution Flow

#### Single Task (main.py)
```
Load state → Pick task → Create branch → Gemini loop → 
Verify (tsc + eslint) → Commit → Save state
Exit: 0 (success), 1 (error), 2 (skip), 3 (all done)
```

#### Full Loop (runner.py) - **NEW**
```
FOR each remaining task:
  - Run main.py for single task
  - If exit 0: Push branch + Create PR + Update README
  - If exit 1: Stop (error)
  - If exit 2: Continue (skip)
  - Handle open PR guard (max 25)
COMMIT final state.json
```

## Usage

### Local (Decoupled from GitHub Actions)

**Prerequisites:**
- Python 3.13+
- Node.js 20+
- Google Gemini API key
- GitHub PAT with infraportal access
- Local infraportal clone at `../infraportal/`

**Single Task:**
```bash
cd agents/productionizer
export GOOGLE_API_KEY="your-gemini-key"
export FORCE_PAGE="AuditPage"
export FORCE_GAP="loading-skeleton"
python main.py
```

**Full Loop (All 30 tasks):**
```bash
cd agents/productionizer
export GOOGLE_API_KEY="your-gemini-key"
export INFRAPORTAL_PAT="your-github-token"
python runner.py
```

**Force Specific Task via Runner:**
```bash
export FORCE_PAGE="AuditPage"
export FORCE_GAP="loading-skeleton"
python runner.py
```

### GitHub Actions (Simplified Workflow)

Trigger manually via `workflow_dispatch`:

```bash
gh workflow run productionizer-decoupled.yml \
  --repo rodmen07/portfolio \
  -f force_page="AuditPage" \
  -f force_gap="loading-skeleton"
```

Or without force parameters to auto-select next task:

```bash
gh workflow run productionizer-decoupled.yml --repo rodmen07/portfolio
```

**Workflow URL**: `.github/workflows/productionizer-decoupled.yml`

## Task Structure

### 30 Total Tasks

**Pages** (10 React components):
- PortalPage, CrmAdminPage, AuditPage, ReportsPage, ObservaboardPage
- SearchPage, ServiceHealthPage, UserDashboardPage, PortalLoginPage, ContactPage

**Gap Types** (3 UI/UX improvements, applied gap-first):
1. `loading-skeleton` - Replace spinner text with skeleton screens
2. `empty-state` - Replace bare "no data" with designed empty states
3. `error-ux` - Replace inline errors with error cards + retry buttons

**Iteration Order**: Gap-first (all 10 pages per gap before moving to next gap)

## State Management

### state.json Schema
```json
{
  "completed": [["PageName", "gap-type"], ...],
  "recent_summaries": [
    {"page": "PageName", "gap": "gap-type", "summary": "..."},
    ...
  ],
  "last_run": "2026-04-30T16:52:22Z"
}
```

**Persistence:**
- Tracked in **portfolio repo** (`agents/productionizer/state.json`)
- Updated after each successful task
- Committed to main after full run
- Enables graceful resumption on network/API failures

## Exit Codes

| Code | Meaning | Next Action |
|------|---------|-------------|
| 0 | Task completed | Push PR + continue |
| 1 | Error | Stop (manual review) |
| 2 | Skipped | Continue to next task |
| 3 | All done | Stop (graceful) |

## Stop Conditions

The runner stops gracefully when:
- ✅ All 30 tasks complete
- ⚠️ 25+ open PRs awaiting review (prevents review queue bloat)
- ❌ Unrecoverable error occurs (exit code 1)

## Verification

Each task undergoes strict verification:
- **TypeScript**: `npx tsc --noEmit` (zero type errors)
- **Linting**: `npx eslint src/pages/{page}.tsx --max-warnings=0`
- **Revert on Failure**: Invalid changes are automatically reverted

## Key Improvements Over v1

### Time Limits Removed
- ❌ Old: `duration_minutes` parameter (15-60 min windows)
- ✅ New: No time limits, full loop in one run

### Decoupled Execution
- ❌ Old: 250+ line YAML workflow with bash while-loop
- ✅ New: Simple workflow + Python runner handles orchestration

### Local Execution
- ❌ Old: GitHub Actions only
- ✅ New: Run locally with `python runner.py`

### Cleaner Separation
- ❌ Old: PR creation, README updates, state sync all in YAML
- ✅ New: All logic in Python for testability + maintainability

## Progress Tracking

### infraportal/README.md Integration
Progress is automatically updated between markers:
- `<!-- PRODUCTIONIZER:START -->`
- `<!-- PRODUCTIONIZER:END -->`

**Displays:**
- Progress bar (n / 30 tasks)
- Task matrix (✅ done vs ⬜ pending)
- Next pending task
- Recent completions (last 5)
- Last run timestamp

## Error Handling

| Scenario | Behavior |
|----------|----------|
| API rate limit | Exponential backoff via Gemini SDK |
| Verification failure | Revert changes, mark skip, continue |
| No changes detected | Mark skip, continue |
| Transient API error | Revert and skip (next task) |
| Critical error | Stop loop, exit code 1 |
| Open PRs >= 25 | Pause gracefully, exit code 0 |

## Testing

### Single Task (Quick Smoke Test)
```bash
cd agents/productionizer
export GOOGLE_API_KEY="your-key"
export FORCE_PAGE="PortalLoginPage"
export FORCE_GAP="loading-skeleton"
python main.py
echo "Exit code: $?"
```

### Full Loop (Production-like)
```bash
cd agents/productionizer
export GOOGLE_API_KEY="your-key"
export INFRAPORTAL_PAT="your-token"
python runner.py
echo "Exit code: $?"
```

### Dry Run (No PR Creation)
Modify `runner.py` to skip `push_pr_and_update_readme()` for testing.

## Future Enhancements

### Possible Improvements
- [ ] Add caching for large page components
- [ ] Implement batch task execution (N tasks per run)
- [ ] Add cost estimation before full loop
- [ ] Parallel task execution (with proper state locking)
- [ ] Metrics collection (time per task, cost per task, success rate)
- [ ] Rollback capability (undo PRs if metrics regress)

## Migration from v1

If you were using the old workflow:

1. **Stop using**: `.github/workflows/productionizer.yml` (deprecated)
2. **Start using**: `.github/workflows/productionizer-decoupled.yml`
3. **Run locally**: `python runner.py` instead of waiting for Actions
4. **Optional**: Keep old workflow for reference, mark as archived

## Support & Debugging

### Common Issues

**Q: How do I check progress?**
```bash
cat agents/productionizer/state.json | jq '.completed | length'
```

**Q: How do I skip a specific task?**
```bash
# Edit state.json and add [page, gap] to completed
python -c "
import json
with open('agents/productionizer/state.json') as f:
    state = json.load(f)
state['completed'].append(['AuditPage', 'loading-skeleton'])
with open('agents/productionizer/state.json', 'w') as f:
    json.dump(state, f, indent=2)
"
```

**Q: Can I run multiple tasks in parallel?**
No, tasks share git state and would conflict. Run them sequentially.

## Architecture Diagram

```
runner.py (Orchestrator)
    ↓
FOR each remaining task:
    ├─→ main.py (Single Task Executor)
    │   ├─→ Gemini Agent Loop
    │   ├─→ Verification (tsc + eslint)
    │   └─→ Commit
    └─→ Push PR
    └─→ Update README
    └─→ Check state + PR count guard
        ↓
COMMIT state.json to portfolio/main
```

---

**Last Updated**: 2026-04-30  
**Version**: 2.0 (Decoupled)  
**Status**: Production-ready
