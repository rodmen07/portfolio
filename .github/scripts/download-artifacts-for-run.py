#!/usr/bin/env python3
"""
Poll a GitHub Actions run until completion and download its artifacts.

Usage:
  python .github/scripts/download-artifacts-for-run.py <run_id>

Environment:
  GITHUB_TOKEN (optional) - if set, used for higher rate limits and auth.
"""
from __future__ import annotations
import os
import sys
import time
import json
import urllib.request
import urllib.parse


def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_binary(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main():
    if len(sys.argv) < 2:
        print("Usage: download-artifacts-for-run.py <run_id>")
        return 2
    run_id = sys.argv[1]
    owner = os.environ.get("OWNER", "rodmen07")
    repo = os.environ.get("REPO", "portfolio")
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    run_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
    artifacts_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"

    outdir = os.path.join("artifacts", f"ci-run-{run_id}")
    os.makedirs(outdir, exist_ok=True)

    timeout = int(os.environ.get("MAX_WAIT", "1800"))
    interval = int(os.environ.get("INTERVAL", "10"))
    elapsed = 0
    print(f"Polling run {run_id} until completion (timeout {timeout}s)")
    while elapsed < timeout:
        try:
            run = fetch_json(run_url, headers=headers)
        except Exception as e:
            print(f"Error fetching run: {e}")
            run = None
        status = run.get("status") if run else None
        conclusion = run.get("conclusion") if run else None
        print(f"status={status} conclusion={conclusion}")
        if status == "completed":
            print(f"Run completed (conclusion={conclusion})")
            break
        time.sleep(interval)
        elapsed += interval

    if status != "completed":
        print("Timed out waiting for run to complete")
        return 1

    try:
        arts = fetch_json(artifacts_url, headers=headers)
    except Exception as e:
        print(f"Error fetching artifacts list: {e}")
        return 1

    for a in arts.get("artifacts", []):
        name = a.get("name")
        url = a.get("archive_download_url")
        if not url:
            print(f"No archive URL for artifact {name}")
            continue
        print(f"Downloading artifact {name} from {url}")
        try:
            data = fetch_binary(url, headers=headers)
            fname = os.path.join(outdir, f"{name}.zip")
            with open(fname, "wb") as fh:
                fh.write(data)
            print(f"Saved {fname}")
        except Exception as e:
            print(f"Failed to download {name}: {e}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
