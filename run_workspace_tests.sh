#!/usr/bin/env bash
set -euo pipefail
cd /workspace

RESULTS_FILE="/workspace/test_results.json"
LOG_DIR="/workspace/test_logs"
NDJSON="$LOG_DIR/results.ndjson"
mkdir -p "$LOG_DIR"
: > "$NDJSON"

MAXCHARS=100000

run_and_capture() {
  local pname="$1"
  local cmd="$2"
  local cwd="$3"
  echo "=== Running $pname in $cwd ==="
  pushd "$cwd" >/dev/null || return 1
  set +e
  output=$(bash -lc "$cmd" 2>&1)
  status=$?
  set -e
  popd >/dev/null
  if [ ${#output} -gt $MAXCHARS ]; then
    out_trunc="${output:0:$MAXCHARS}\n\n---OUTPUT TRUNCATED---\n"
  else
    out_trunc="$output"
  fi
  logfile="$LOG_DIR/${pname}.log"
  printf "%s" "$out_trunc" > "$logfile"
  printf '{"name":"%s","cwd":"%s","status":%d,"log_file":"%s"}\n' "$pname" "$cwd" "$status" "$logfile" >> "$NDJSON"
  return $status
}

for d in */ ; do
  if [ ! -d "$d" ]; then
    continue
  fi
  if [ "$d" = ".git/" ]; then
    continue
  fi
  if [ "$d" = "node_modules/" ] || [ "$d" = "target/" ]; then
    continue
  fi
  if [ -f "$d/requirements.txt" ]; then
    name="${d%/}"
    echo "Processing Python project: $name"
    python -m venv "$d/.venv"
    . "$d/.venv/bin/activate"
    pip install --upgrade pip setuptools wheel || true
    pip install -r "$d/requirements.txt" || true
    if [ -d "$d/tests" ]; then
      run_and_capture "${name}-pytest" "pytest -q --maxfail=1 || true" "$d" || true
    fi
    deactivate || true
  elif [ -f "$d/go.mod" ]; then
    name="${d%/}"
    echo "Processing Go project: $name"
    run_and_capture "${name}-gotest" "go test ./... || true" "$d" || true
  elif [ -f "$d/Cargo.toml" ]; then
    name="${d%/}"
    echo "Processing Rust project: $name"
    run_and_capture "${name}-cargo" "cargo test --release || true" "$d" || true
  else
    echo "Skipping $d (unknown project type)"
  fi
done

# Convert ndjson to array
jq -s . "$NDJSON" > "$RESULTS_FILE" || (echo "failed to produce $RESULTS_FILE" && cp "$NDJSON" "$RESULTS_FILE")

echo "Done. Results: $RESULTS_FILE"
