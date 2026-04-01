#!/usr/bin/env bash
set -euo pipefail
# Use GitHub Actions workspace if available, otherwise use current directory
if [ -n "${GITHUB_WORKSPACE:-}" ]; then
  ROOT_DIR="$GITHUB_WORKSPACE"
else
  ROOT_DIR="$(pwd)"
fi

RESULTS_FILE="$ROOT_DIR/test_results.json"
LOG_DIR="$ROOT_DIR/test_logs"
NDJSON="$LOG_DIR/results.ndjson"
mkdir -p "$LOG_DIR"
: > "$NDJSON"

MAXCHARS=100000
# Ensure submodules are present: try to initialize or clone from .gitmodules
if [ -f "$ROOT_DIR/.gitmodules" ]; then
  echo "Found .gitmodules — ensuring submodules are present"
  git -C "$ROOT_DIR" config -f "$ROOT_DIR/.gitmodules" --get-regexp 'submodule\..*\.path' 2>/dev/null | while read -r key path; do
    name=$(echo "$key" | sed -E 's/submodule\.([^.]*)\.path/\1/')
    url=$(git -C "$ROOT_DIR" config -f "$ROOT_DIR/.gitmodules" --get "submodule.$name.url" 2>/dev/null || true)
    target="$ROOT_DIR/$path"
    if [ -d "$target" ] && [ -n "$(ls -A "$target" 2>/dev/null)" ]; then
      echo "Submodule $path already exists"
      continue
    fi
    if [ -n "$url" ]; then
      echo "Cloning submodule $name from $url into $path"
      rm -rf "$target"
      git clone --depth 1 "$url" "$target" || echo "clone failed for $url; continuing"
    else
      echo "No URL for submodule $name; skipping"
    fi
  done
fi

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
  logfile="$LOG_DIR/$(echo "$pname" | sed 's/[\/ ]/_/g').log"
  printf "%s" "$out_trunc" > "$logfile"
  printf '{"name":"%s","cwd":"%s","status":%d,"log_file":"%s"}\n' "$pname" "$cwd" "$status" "$logfile" >> "$NDJSON"
  return $status
}

# Discover project directories (requirements.txt, go.mod, Cargo.toml) up to depth 4
mapfile -t PROJECT_DIRS < <(find "$ROOT_DIR" -mindepth 1 -maxdepth 4 -type f \( -name requirements.txt -o -name go.mod -o -name Cargo.toml \) -not -path '*/.git/*' -not -path '*/.claude/*' -printf '%h\n' | sort -u)

if [ ${#PROJECT_DIRS[@]} -eq 0 ]; then
  echo "No project directories detected under $ROOT_DIR"
fi

for cwd in "${PROJECT_DIRS[@]}"; do
  rel=${cwd#"$ROOT_DIR"/}
  name=$(echo "$rel" | sed 's/[\/ ]/_/g')
  if [ -f "$cwd/requirements.txt" ]; then
    echo "Processing Python project: $rel"
    python -m venv "$cwd/.venv"
    . "$cwd/.venv/bin/activate"
    pip install --upgrade pip setuptools wheel || true
    pip install -r "$cwd/requirements.txt" || true
    if [ -d "$cwd/tests" ]; then
      run_and_capture "${name}-pytest" "pytest -q --maxfail=1 || true" "$cwd" || true
    fi
    deactivate || true
  elif [ -f "$cwd/go.mod" ]; then
    echo "Processing Go project: $rel"
    run_and_capture "${name}-gotest" "go test ./... || true" "$cwd" || true
  elif [ -f "$cwd/Cargo.toml" ]; then
    echo "Processing Rust project: $rel"
    run_and_capture "${name}-cargo" "cargo test --release || true" "$cwd" || true
  fi
done

# Convert ndjson to array
jq -s . "$NDJSON" > "$RESULTS_FILE" || (echo "failed to produce $RESULTS_FILE" && cp "$NDJSON" "$RESULTS_FILE")

echo "Done. Results: $RESULTS_FILE"
