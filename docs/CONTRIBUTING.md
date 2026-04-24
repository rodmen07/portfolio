# Contributing

Thanks for taking a look. This is the day-to-day workflow for the umbrella
repo. For architecture, see [ARCHITECTURE.md](./ARCHITECTURE.md). For the
shipped-version history, see [ROADMAP.md](./ROADMAP.md).

## Submodule workflow

The repo uses git submodules — each subproject is an independently-versioned
repository. Submodules are declared in `.gitmodules`; a machine-readable
inventory lives in [`services.yaml`](../services.yaml).

```bash
# After cloning the umbrella repo:
git submodule update --init --recursive

# Update all submodules to their latest configured commits:
git submodule update --remote --recursive

# Inspect submodule status:
git submodule status --recursive

# Bump a single submodule pointer:
cd <submodule>
git pull origin main
cd ..
git add <submodule>
git commit -m "Update <submodule> pointer"
```

> Run `git clean -fdx` inside a submodule only if you want a fully clean state
> and are okay losing uncommitted local changes.

## Local environment

1. Copy the workspace template:

   ```bash
   cp .env.example .env
   ```

2. Fill in real values for the integrations you actually plan to exercise
   (LLM keys, OAuth client IDs, AWS credentials). Local-only test runs
   typically only need `AUTH_JWT_SECRET` and `TEST_DATABASE_URL=sqlite::memory:`.
3. The Dev Container in `.devcontainer/` pins the toolchain versions used in
   CI (Rust, Python, Go, Node, Terraform). Open the repo in VS Code or
   Codespaces to use it.

## Running checks

There are two layers:

- `run_workspace_tests.sh` at the repo root — cross-repo validation used in
  CI and for any bash environment.
- `microservices/scripts/run-checks.ps1` — deeper microservices-only
  verification on Windows.

### Option 1: workspace runner (recommended)

```bash
bash ./run_workspace_tests.sh
```

The script writes a JSON summary (`test_results.json`) and per-project logs
under `test_logs/`.

### Option 2: microservices PowerShell runner (Windows only)

```powershell
cd microservices
./scripts/run-checks.ps1
```

### Option 3: per-service

You can also invoke `cargo test`, `cargo clippy`, `pytest`, `go test`, or
`npm run build` directly inside each service directory. Recommended local
verification for a Rust service:

```bash
cd microservices/reporting-service
export AUTH_JWT_SECRET=dev-insecure-secret-change-me
cargo test

cd ../accounts-service
export TEST_DATABASE_URL=sqlite::memory:
export AUTH_JWT_SECRET=dev-insecure-secret-change-me
cargo test
# repeat for contacts-service, opportunities-service, activities-service, etc.
```

A `justfile` at the repo root wraps the most common commands; run `just` with
no arguments to list them.

## Style and quality gates

- `pre-commit run --all-files` runs the formatters and lightweight linters
  pinned in [`.pre-commit-config.yaml`](../.pre-commit-config.yaml)
  (Rust `cargo fmt`, Python `ruff`, Go `gofmt`, Terraform `fmt`,
  `prettier`, plus a Dockerfile `USER`-directive check for SOC 2 CC6.8).
- CodeQL, Trivy image scans, and gitleaks run in the umbrella CI on every PR
  and on a weekly schedule.

## Pull requests

- One topic per PR; keep commits focused.
- Update `services.yaml` and `docs/ARCHITECTURE.md` together when adding,
  renaming, or relocating a service.
- Update `docs/ROADMAP.md` only when a feature is **Published** (all release
  locations updated; see `microservices/CLAUDE.md` § Release Locations).
- New deployments must add a row to the deployment table in
  `docs/ARCHITECTURE.md`.

## Security

Please do not file public issues for security problems. Use Private
Vulnerability Reporting on this repo or the affected submodule. Full policy:
[`SECURITY.md`](../SECURITY.md).
