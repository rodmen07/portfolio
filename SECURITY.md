# Security Policy

This umbrella repository aggregates several independently-versioned services
(see `services.yaml`). The services follow the SOC 2 controls documented in
`microservices/terraform-soc2-baseline/` (CC6.1 — A1.2).

## Supported versions

Only the latest commit on `main` of each submodule is supported. Older tags
and revisions are kept for reference but receive no security updates.

| Component     | Supported |
|---------------|-----------|
| `main` branch | ✅        |
| Older tags    | ❌        |

## Reporting a vulnerability

Please **do not** open public GitHub issues for security problems.

- Use [GitHub Private Vulnerability Reporting](https://github.com/rodmen07/portfolio/security/advisories/new)
  on this repository, or on the affected submodule's repository.
- Include reproduction steps, affected service(s), commit SHA, and any
  proof-of-concept payloads.

You should expect:

- Acknowledgement within **3 business days**.
- A triage decision (accepted / needs-info / not-a-vulnerability) within
  **10 business days**.
- A fix or mitigation plan for accepted reports within **30 days** for
  high/critical severity, or **90 days** for low/medium severity.

## Handling

Confirmed vulnerabilities are tracked as private security advisories, fixed
on a private branch, and disclosed in a coordinated release once a fix is
available. Credit is given to the reporter unless they prefer to remain
anonymous.

## Scope

In scope:

- Source code and CI workflows in this repository and its submodules.
- Live deployments listed under "Deployment summary" in
  `docs/ARCHITECTURE.md`.

Out of scope:

- Findings that require physical access, social engineering, or
  compromised user credentials.
- Denial-of-service via volumetric traffic against the live demo
  deployments.
- Issues in third-party services (GCP, Fly.io, GitHub Pages) themselves.
