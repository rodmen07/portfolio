GCP Setup (interactive and non-interactive)

This repository includes `gcp-setup.sh` at the repository root to provision one-time GCP resources used by the microservices and CI workflows.

What the script does (summary):
- Creates Artifact Registry repository for Docker images
- Creates a service account with Cloud Run / Artifact Registry / Secret Manager roles
- Creates a Workload Identity Federation pool/provider for GitHub Actions
- Creates or updates Secret Manager secrets for JWTs and OAuth client secrets

Prerequisites:
- `gcloud` CLI installed and authenticated: `gcloud auth login`
- Billing enabled on the target project

Interactive usage (default):

```bash
bash gcp-setup.sh
```

The script will prompt for `GCP Project ID`, `GCP Region` (defaults to `us-central1`), and will prompt for secret values. Press Enter to skip any secret you want to configure later.

Non-interactive usage (recommended for automation):

Set environment variables and run with `NONINTERACTIVE=1`. Required variables when running non-interactively:
- `GCP_PROJECT_ID` — the project id to configure

Optional variables (if set, they will be used instead of prompting):
- `GCP_REGION` — region (defaults to `us-central1`)
- `JWT_SECRET` — will be written to Secret Manager as `AUTH_JWT_SECRET`
- `USER_GITHUB_CLIENT_ID`, `USER_GITHUB_CLIENT_SECRET`, `USER_GITHUB_REDIRECT_URI`
- `USER_GOOGLE_CLIENT_ID`, `USER_GOOGLE_CLIENT_SECRET`, `USER_GOOGLE_REDIRECT_URI`
- `USER_OAUTH_STATE_SECRET`
- `CMS_GITHUB_CLIENT_ID`, `CMS_GITHUB_CLIENT_SECRET`, `CMS_GITHUB_REDIRECT_URI`, `CMS_OAUTH_STATE_SECRET`

Example non-interactive invocation:

```bash
export GCP_PROJECT_ID="my-project-id"
export GCP_REGION="us-central1"
export NONINTERACTIVE=1
export JWT_SECRET="$(openssl rand -hex 32)"
# optionally set other secrets as env vars
bash gcp-setup.sh
```

Notes:
- When `NONINTERACTIVE=1` and required env values are missing, the script will exit with an error rather than prompting.
- The script performs live `gcloud` operations; review and run it from a machine with the proper `gcloud` authentication.
- After the script completes it prints the Workload Identity Provider and service account to configure as GitHub Actions secrets:
  - `GCP_PROJECT_ID` (variable)
  - `GCP_WORKLOAD_IDENTITY_PROVIDER` (secret)
  - `GCP_SERVICE_ACCOUNT` (secret)

If you'd like, I can also:
- Add a Terraform-based provisioning alternative under `terraform/gcp/` (recommended for reproducible infra), or
- Add a GitHub Actions workflow that runs an idempotent, non-interactive provisioning job (requires careful IAM/billing handling).
