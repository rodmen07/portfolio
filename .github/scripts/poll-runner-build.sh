#!/usr/bin/env bash
set -euo pipefail

OWNER="rodmen07"
REPO="portfolio"
BRANCH="ci/build-runner-image"
OUT_DIR="artifacts/ci-runner-image"
mkdir -p "$OUT_DIR"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required but not installed. Install jq and re-run." >&2
  exit 2
fi

MAX_WAIT=${MAX_WAIT:-1800} # seconds
INTERVAL=${INTERVAL:-15}
elapsed=0

echo "Polling GitHub Actions for $OWNER/$REPO branch $BRANCH (timeout ${MAX_WAIT}s)..."
while [ $elapsed -lt $MAX_WAIT ]; do
  resp=$(curl -s "https://api.github.com/repos/$OWNER/$REPO/actions/runs?branch=$BRANCH&per_page=1") || true
  run_id=$(echo "$resp" | jq -r '.workflow_runs[0].id // empty')
  if [ -n "$run_id" ]; then
    status=$(echo "$resp" | jq -r '.workflow_runs[0].status // empty')
    conclusion=$(echo "$resp" | jq -r '.workflow_runs[0].conclusion // empty')
    echo "Found run id=$run_id status=$status conclusion=$conclusion"
    if [ "$status" = "completed" ]; then
      echo "Run completed (conclusion=$conclusion). Downloading logs..."
      curl -sL "https://api.github.com/repos/$OWNER/$REPO/actions/runs/$run_id/logs" -o "$OUT_DIR/run_${run_id}_logs.zip" || echo "failed to download logs"
      echo "$resp" | jq '.workflow_runs[0]' > "$OUT_DIR/run_${run_id}.json"
      echo "Saved run metadata to $OUT_DIR/run_${run_id}.json"
      echo "Done."
      exit 0
    fi
    echo "Run found but not completed. sleeping ${INTERVAL}s..."
  else
    echo "No run found yet for branch $BRANCH. sleeping ${INTERVAL}s..."
  fi
  sleep $INTERVAL
  elapsed=$((elapsed + INTERVAL))
done

echo "Timed out waiting for Actions run after ${MAX_WAIT}s" >&2
exit 1
