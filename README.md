![Portfolio hero](docs/images/v1-portfolio-hero.png)

# Portfolio

Production-grade cloud engineering projects in Rust, Python, TypeScript, Go,
and Terraform across AWS and GCP.

**Live site:** https://rodmen07.github.io/infraportal/

## Highlights

- **InfraPortal** — 11-service CRM platform on GCP Cloud Run with PostgreSQL,
  JWT auth, and an LLM-backed planner (Claude + Gemini). React 19 client
  portal with GitHub + Google OAuth.
- **SOC 2 baseline** — cloud-agnostic Terraform module implementing 9 SOC 2
  Type II controls on both GCP and AWS.
- **Multi-environment CI/CD template** — GitHub Actions reference with
  OIDC-only credentials, manual approval gates, and automated rollback on
  GCP Cloud Run / AWS ECS.
- **Observaboard** — Django 5 + Celery webhook ingestion API with
  PostgreSQL full-text search and dual JWT / API-key auth.
- **DynamoDB medallion pipeline** — Rust + Go prototype showing
  exactly-once cloud-audit-log delivery via single-table conditional writes,
  with a live admin dashboard.
- **Productionizer agent** — Gemini 2.5 Flash autonomous agent that opens
  daily PRs improving the Rust microservices.

## Documentation

- [Architecture, services, and deployments](./docs/ARCHITECTURE.md)
- [Contributing, submodule workflow, local dev](./docs/CONTRIBUTING.md)
- [Roadmap and release history](./docs/ROADMAP.md)
- [Security policy](./SECURITY.md)
- [`services.yaml`](./services.yaml) — machine-readable service inventory

## Quick start

```bash
git clone --recurse-submodules https://github.com/rodmen07/portfolio.git
cd portfolio
cp .env.example .env          # then fill in real values
bash ./run_workspace_tests.sh # cross-repo workspace checks
```

A [`justfile`](./justfile) wraps the most common workflows; run `just` with no
arguments to list them. Toolchain versions are pinned in
[`.devcontainer/`](./.devcontainer/) for VS Code / Codespaces.

## License

[MIT](./LICENSE)
