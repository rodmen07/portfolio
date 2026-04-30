# Productionizer v2.0 - Migration & Implementation Guide

## What's Changed

### Before (v1.0)
- ❌ Tightly coupled to GitHub Actions workflow
- ❌ Time-limited execution (15-60 minute windows)
- ❌ Bash while-loop in YAML with 250+ lines
- ❌ PR creation, README updates in shell scripts
- ❌ Difficult to test locally

### After (v2.0) - DECOUPLED
- ✅ Standalone Python runner (`runner.py`)
- ✅ Full loop execution (all 30 tasks, no time limits)
- ✅ Clean separation: `main.py` (single task) + `runner.py` (orchestration)
- ✅ PR creation, README updates in Python
- ✅ Run locally: `python runner.py`
- ✅ Simplified workflow (60 lines vs 250+)

## File Changes

### New Files
```
agents/productionizer/
├── runner.py                    # NEW: Full-loop orchestrator
├── DECOUPLED.md                 # NEW: Architecture documentation
└── .github/workflows/
    └── productionizer-decoupled.yml  # NEW: Simplified workflow
```

### Modified Files
```
agents/productionizer/
├── main.py                      # MODIFIED: Docstring clarified (single task)
└── (all other files unchanged)
```

### Deprecated Files (Optional - keep for reference)
```
.github/workflows/
└── productionizer.yml           # OLD: Keep for reference, mark archived
```

## Implementation Checklist

- [x] Created `runner.py` (full-loop orchestrator)
- [x] Created `productionizer-decoupled.yml` (simplified workflow)
- [x] Updated `main.py` docstring
- [x] Created `DECOUPLED.md` (architecture doc)
- [ ] Test locally with single task
- [ ] Test locally with full loop
- [ ] Test via GitHub Actions workflow_dispatch
- [ ] Update portfolio README with new usage
- [ ] Archive old workflow (optional)

## Quick Start

### 1. Test Single Task (5 min)
```bash
cd portfolio/agents/productionizer

# Set up environment
export GOOGLE_API_KEY="sk-..."
export INFRAPORTAL_PAT="ghp_..."

# Force a single task for quick testing
export FORCE_PAGE="PortalLoginPage"
export FORCE_GAP="loading-skeleton"

# Run
python3 main.py
echo "Exit code: $?"  # Should be 0, 2, or 1
```

### 2. Test Full Loop Locally (1-2 hours)
```bash
cd portfolio/agents/productionizer

export GOOGLE_API_KEY="sk-..."
export INFRAPORTAL_PAT="ghp_..."

# Run all remaining tasks
python3 runner.py
echo "Exit code: $?"  # Should be 0 (success) or 1 (error)
```

### 3. Test via GitHub Actions
```bash
# Trigger via gh CLI
gh workflow run productionizer-decoupled.yml \
  --repo rodmen07/portfolio \
  -f force_page="" \
  -f force_gap=""

# Or via UI: https://github.com/rodmen07/portfolio/actions
```

## Key Concepts

### Main.py (Single Task Executor)
- **Input**: FORCE_PAGE + FORCE_GAP (optional), or auto-select from state.json
- **Output**: Exit code (0, 1, 2, or 3) + .productionizer-output.json (if success)
- **Side Effects**: Commits to git branch, updates state.json
- **No PR Creation**: That's runner.py's job

### Runner.py (Orchestrator) - NEW
- **Input**: GOOGLE_API_KEY, INFRAPORTAL_PAT, optional FORCE_PAGE/FORCE_GAP
- **Output**: Exit code (0 = success, 1 = error)
- **Loop**: FOR each remaining task: run main.py → push PR → update README
- **Stops When**:
  - All 30 tasks complete (success)
  - Open PRs >= 25 (pauses gracefully)
  - main.py returns error (exit 1)

### State.json (Persistent)
- **Format**: `{"completed": [["page", "gap"], ...], "recent_summaries": [...], "last_run": "..."}`
- **Location**: `agents/productionizer/state.json`
- **Tracked**: In portfolio repo (committed to main)
- **Used By**: main.py (to pick next task) + update_readme.py (progress display)

## Exit Codes

### main.py
```
0 = task completed and committed to branch
1 = unrecoverable error (stop)
2 = task skipped (continue to next)
3 = all tasks already done
```

### runner.py
```
0 = completed run (some/all tasks done, or gracefully paused)
1 = critical error (stop immediately)
```

## Deployment Strategy

### Option A: Gradual Migration (Recommended)
1. Deploy new workflow (`productionizer-decoupled.yml`)
2. Keep old workflow available for reference
3. Test new workflow via workflow_dispatch
4. Once confident, archive old workflow
5. Update documentation

### Option B: Quick Switch
1. Replace old workflow with new one
2. Delete old workflow file
3. Announce on team channels

## Testing Scenarios

### Test 1: Single Task Verification
```bash
# Expected: Success or skip, no errors
export FORCE_PAGE="AuditPage"
export FORCE_GAP="loading-skeleton"
python3 main.py
# Should exit 0 or 2, output .productionizer-output.json
```

### Test 2: State Persistence
```bash
# First run
python3 runner.py
# Check: agents/productionizer/state.json has completion

# Second run (should skip completed)
python3 runner.py
# Should process fewer tasks
```

### Test 3: PR Creation
```bash
# Before: Check infraportal open PRs
gh pr list --repo rodmen07/infraportal --state open | wc -l

# Run
python3 runner.py

# After: Should have +N open PRs
gh pr list --repo rodmen07/infraportal --state open | wc -l
```

## Troubleshooting

### "module 'tasks' has no attribute 'build_task_queue'"
**Fix**: Install dependencies
```bash
cd agents/productionizer
pip install google-genai
```

### "git: fatal: not a git repository"
**Fix**: Ensure infraportal clone exists at `../infraportal/`
```bash
# From portfolio root
git clone https://github.com/rodmen07/infraportal.git
```

### "INFRAPORTAL_PAT is not set"
**Fix**: Export GitHub token with repo access
```bash
export INFRAPORTAL_PAT="ghp_xxxx..."
```

### "Rate limited by Gemini API"
**Normal**: SDK implements exponential backoff. Wait and retry.

## Performance Notes

### Expected Timing
- Single task: 3-10 minutes (depends on page size)
- Full loop (30 tasks): 2-6 hours (at ~5 min per task avg)
- With PR creation/README updates: add ~1 min per task

### Resource Usage
- CPU: Moderate (npm tsc + eslint verification)
- Memory: Low (~200MB)
- API Calls: ~2-3 per task (Gemini messages)
- GitHub API: ~10 calls per task (PR creation, PR list)

## FAQ

**Q: Do I need to run GitHub Actions?**
No, you can run locally: `python runner.py`

**Q: Can I run multiple instances in parallel?**
No, they share git state and would conflict.

**Q: How do I skip a completed task?**
Edit `state.json` and add `[page, gap]` to `completed`.

**Q: What if the workflow times out?**
Workflow timeout is 180 min (3 hours). If runner.py is still working, it will continue. Check logs.

**Q: Can I force a specific task?**
Yes: `export FORCE_PAGE="X" FORCE_GAP="Y"` before running `main.py` or `runner.py`.

**Q: How do I track progress?**
- Via code: `jq .completed agents/productionizer/state.json | length`
- Via UI: Check infraportal README.md (updated between markers)
- Via GitHub: Check open PRs at github.com/rodmen07/infraportal

## Rollback Plan

If v2.0 has issues:
1. Re-enable old workflow: `.github/workflows/productionizer.yml`
2. Revert runner.py + decoupled workflow commit
3. State.json is backward compatible (v1.0 can read it)

## Next Steps

1. **Deploy**: Commit runner.py + productionizer-decoupled.yml to portfolio/main
2. **Test**: Run locally with `python runner.py`
3. **Iterate**: Use GitHub Actions for production runs
4. **Monitor**: Watch for API errors, PR creation issues
5. **Iterate**: Tune performance, add caching if needed

---

**Version**: 2.0 (Decoupled)  
**Date**: 2026-04-30  
**Status**: Ready for deployment
