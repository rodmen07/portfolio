#!/usr/bin/env python3
"""
Poll GitHub Actions for a workflow run on a branch and download logs when it completes.

Defaults (can be overridden via environment variables):
  OWNER (rodmen07)
  REPO (portfolio)
  BRANCH (ci/build-runner-image)
  OUT_DIR (artifacts/ci-runner-image)
  MAX_WAIT (1800 seconds)
  INTERVAL (15 seconds)
  GITHUB_TOKEN (optional, to increase rate limits)

This script uses only the Python standard library.
"""
from __future__ import annotations
import os
import sys
import time
import json
import urllib.request
import urllib.parse
from http.client import HTTPException


OWNER = os.environ.get("OWNER", "rodmen07")
REPO = os.environ.get("REPO", "portfolio")
BRANCH = os.environ.get("BRANCH", "ci/build-runner-image")
OUT_DIR = os.environ.get("OUT_DIR", "artifacts/ci-runner-image")
MAX_WAIT = int(os.environ.get("MAX_WAIT", "1800"))
INTERVAL = int(os.environ.get("INTERVAL", "15"))
TOKEN = os.environ.get("GITHUB_TOKEN")

os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def fetch_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"fetch_json error for {url}: {e}")
        return None


def fetch_binary(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except Exception as e:
        print(f"fetch_binary error for {url}: {e}")
        return None


def main() -> int:
    print(f"Polling GitHub Actions for {OWNER}/{REPO} branch {BRANCH} (timeout {MAX_WAIT}s)")
    elapsed = 0
    runs_url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs?branch={urllib.parse.quote(BRANCH)}&per_page=1"

    while elapsed < MAX_WAIT:
        data = fetch_json(runs_url)
        if data and data.get("workflow_runs"):
            run = data["workflow_runs"][0]
            run_id = run.get("id")
            status = run.get("status")
            conclusion = run.get("conclusion")
            print(f"Found run id={run_id} status={status} conclusion={conclusion}")
            if status == "completed":
                # download logs
                logs_url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run_id}/logs"
                print(f"Run completed; downloading logs from {logs_url} ...")
                content = fetch_binary(logs_url)
                if content:
                    out_zip = os.path.join(OUT_DIR, f"run_{run_id}_logs.zip")
                    with open(out_zip, "wb") as fh:
                        fh.write(content)
                    print(f"Saved logs to {out_zip}")
                meta_file = os.path.join(OUT_DIR, f"run_{run_id}.json")
                with open(meta_file, "w", encoding="utf-8") as fh:
                    json.dump(run, fh, indent=2)
                print(f"Saved metadata to {meta_file}")
                return 0
            else:
                print(f"Run not completed yet (status={status}). Sleeping {INTERVAL}s...")
        else:
            print(f"No run found for branch {BRANCH}. Sleeping {INTERVAL}s...")
        time.sleep(INTERVAL)
        elapsed += INTERVAL

    print(f"Timed out after {MAX_WAIT} seconds waiting for workflow run.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
