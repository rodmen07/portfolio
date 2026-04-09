#!/usr/bin/env bash
set -euo pipefail

# Pull the built runner image from GHCR and run workspace tests locally when the CI build completes.
# Usage: bash .github/scripts/pull-and-run.sh

OWNER=${OWNER:-rodmen07}
REPO=${REPO:-portfolio}
BRANCH=${BRANCH:-ci/build-runner-image}
IMAGE_TAG=${IMAGE_TAG:-py3.13}
IMAGE="ghcr.io/${OWNER}/workspace-test-runner:${IMAGE_TAG}"
OUT_DIR=${OUT_DIR:-artifacts/ci-runner-image}

mkdir -p "$OUT_DIR"

MAX_WAIT=${MAX_WAIT:-1800}
INTERVAL=${INTERVAL:-15}
elapsed=0

echo "Watching Actions runs for ${OWNER}/${REPO} branch ${BRANCH} (timeout ${MAX_WAIT}s)"

while [ $elapsed -lt $MAX_WAIT ]; do
  resp=$(curl -s "https://api.github.com/repos/${OWNER}/${REPO}/actions/runs?branch=$(printf '%s' "$BRANCH" | sed 's/ /%20/g')&per_page=1")
  run_id=$(echo "$resp" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('workflow_runs')[0].get('id') if d.get('workflow_runs') else '')")
  status=$(echo "$resp" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('workflow_runs')[0].get('status') if d.get('workflow_runs') else '')")
  if [ -n "$run_id" ]; then
    echo "Found run id=$run_id status=$status"
    if [ "$status" = "completed" ]; then
      echo "Run completed; downloading logs and attempting to pull image $IMAGE"
      curl -sL "https://api.github.com/repos/${OWNER}/${REPO}/actions/runs/${run_id}/logs" -o "$OUT_DIR/run_${run_id}_logs.zip" || echo "failed to download logs"
      echo "$resp" | python -c "import sys,json, pathlib; d=json.load(sys.stdin); pathlib.Path('${OUT_DIR}/run_${run_id}.json').write_text(json.dumps(d.get('workflow_runs')[0], indent=2))"

      if command -v docker >/dev/null 2>&1; then
        if docker version >/dev/null 2>&1; then
          echo "Pulling image $IMAGE"
          if docker pull "$IMAGE"; then
            echo "Running workspace tests inside container..."
            docker run --rm -v "$PWD":/workspace -w /workspace "$IMAGE" bash -lc "chmod +x ./run_workspace_tests.sh && ./run_workspace_tests.sh" || echo "docker run failed"
          else
            echo "docker pull failed; image may be private or unavailable"
          fi
        else
          echo "Docker daemon not running; cannot pull/run image"
        fi
      else
        echo "Docker CLI not installed; cannot pull/run image"
      fi
      exit 0
    fi
  else
    echo "No run found yet for branch $BRANCH"
  fi
  sleep $INTERVAL
  elapsed=$((elapsed + INTERVAL))
done

echo "Timed out waiting for Actions run after ${MAX_WAIT}s"
exit 1
