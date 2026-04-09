#!/usr/bin/env bash
# gcp-setup.sh — one-time GCP provisioning for InfraPortal Cloud Run deployment
#
# What this creates:
#   - Artifact Registry repository (Docker images)
#   - Service account with Cloud Run + Artifact Registry + Secret Manager permissions
#   - Workload Identity Federation pool/provider (keyless GitHub Actions auth)
#   - Secret Manager secrets for sensitive env vars
#
# Usage:
#   bash gcp-setup.sh
#
# Prerequisites:
#   gcloud CLI installed and authenticated (`gcloud auth login`)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Allow non-interactive runs driven by environment variables.
# Provide: GCP_PROJECT_ID, GCP_REGION, NONINTERACTIVE=1, JWT_SECRET, and other secret envs.
GITHUB_OWNER="rodmen07"
SA_NAME="github-deployer"
POOL_ID="github-pool"
PROVIDER_ID="github-provider"
REGISTRY="microservices"

# Populate PROJECT_ID/REGION from env if set (use GCP_PROJECT_ID/GCP_REGION as canonical names)
if [ -n "${GCP_PROJECT_ID:-}" ]; then
  PROJECT_ID="${GCP_PROJECT_ID}"
fi
if [ -n "${GCP_REGION:-}" ]; then
  REGION="${GCP_REGION}"
fi

# NONINTERACTIVE=1 will avoid interactive prompts and require required envs be set.
NONINTERACTIVE=${NONINTERACTIVE:-0}

# ── Prompts ───────────────────────────────────────────────────────────────────
if [ -z "${PROJECT_ID:-}" ]; then
  if [ "${NONINTERACTIVE}" = "1" ]; then
    echo "ERROR: NONINTERACTIVE set but GCP_PROJECT_ID/PROJECT_ID not provided. Exiting."
    exit 1
  fi
  read -rp "GCP Project ID (new or existing): " PROJECT_ID
fi

if [ -z "${REGION:-}" ]; then
  if [ -n "${GCP_REGION:-}" ]; then
    REGION="${GCP_REGION}"
  elif [ "${NONINTERACTIVE}" = "1" ]; then
    REGION="us-central1"
  else
    read -rp "GCP Region [us-central1]: " REGION
  fi
fi
REGION="${REGION:-us-central1}"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo "==> Configuring project: ${PROJECT_ID} / region: ${REGION}"
gcloud config set project "${PROJECT_ID}"

# ── Create project if missing ─────────────────────────────────────────────────
if ! gcloud projects describe "${PROJECT_ID}" &>/dev/null; then
  echo "==> Creating project ${PROJECT_ID}..."
  gcloud projects create "${PROJECT_ID}" --name="InfraPortal"
fi

echo ""
echo "⚠  Ensure billing is enabled before continuing:"
echo "   https://console.cloud.google.com/billing/linkedaccount?project=${PROJECT_ID}"
if [ "${NONINTERACTIVE}" != "1" ]; then
  read -rp "   Press Enter once billing is enabled..."
else
  echo "   NONINTERACTIVE=1 — skipping billing prompt"
fi

# ── Enable APIs ───────────────────────────────────────────────────────────────
echo ""
echo "==> Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com

# ── Artifact Registry ─────────────────────────────────────────────────────────
echo ""
echo "==> Creating Artifact Registry repo '${REGISTRY}' in ${REGION}..."
gcloud artifacts repositories create "${REGISTRY}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="InfraPortal microservices Docker images" 2>/dev/null \
  || echo "   (already exists, skipping)"

# ── Service Account ───────────────────────────────────────────────────────────
echo ""
echo "==> Creating service account '${SA_NAME}'..."
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="GitHub Actions Cloud Run Deployer" 2>/dev/null \
  || echo "   (already exists, skipping)"

PROJECT_NUM=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")

echo "==> Granting IAM roles to ${SA_EMAIL}..."
for ROLE in \
  roles/run.developer \
  roles/artifactregistry.writer \
  roles/secretmanager.secretAccessor \
  roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet
done

# Allow the SA to run as itself (needed for --service-account on cloud run deploy)
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser" \
  --member="serviceAccount:${SA_EMAIL}"

# ── Workload Identity Federation ──────────────────────────────────────────────
echo ""
echo "==> Creating Workload Identity pool '${POOL_ID}'..."
gcloud iam workload-identity-pools create "${POOL_ID}" \
  --location=global \
  --display-name="GitHub Actions Pool" 2>/dev/null \
  || echo "   (already exists, skipping)"

echo "==> Creating OIDC provider '${PROVIDER_ID}'..."
gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
  --location=global \
  --workload-identity-pool="${POOL_ID}" \
  --display-name="GitHub Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="attribute.repository_owner == '${GITHUB_OWNER}'" 2>/dev/null \
  || echo "   (already exists, skipping)"

echo "==> Binding WIF principal set to service account..."
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository_owner/${GITHUB_OWNER}"

# ── Secret Manager secrets ────────────────────────────────────────────────────
echo ""
echo "==> Creating Secret Manager secrets..."
echo "   (Press Enter to skip any secret you'll configure later)"
echo ""

create_or_update_secret() {
  local name="$1" value="$2"
  if gcloud secrets describe "${name}" &>/dev/null; then
    echo -n "${value}" | gcloud secrets versions add "${name}" --data-file=-
  else
    echo -n "${value}" | gcloud secrets create "${name}" --data-file=-
  fi
}

if [ -n "${JWT_SECRET:-}" ]; then
  create_or_update_secret "AUTH_JWT_SECRET" "${JWT_SECRET}"
elif [ "${NONINTERACTIVE}" != "1" ]; then
  read -rsp "AUTH_JWT_SECRET: " JWT_SECRET; echo ""
  [ -n "${JWT_SECRET}" ] && create_or_update_secret "AUTH_JWT_SECRET" "${JWT_SECRET}"
else
  echo "Skipping AUTH_JWT_SECRET (not provided)"
fi

echo ""
echo "--- User OAuth (GitHub login) ---"
for NAME in USER_GITHUB_CLIENT_ID USER_GITHUB_CLIENT_SECRET USER_GITHUB_REDIRECT_URI \
            USER_GOOGLE_CLIENT_ID USER_GOOGLE_CLIENT_SECRET USER_GOOGLE_REDIRECT_URI \
            USER_OAUTH_STATE_SECRET; do
  # If env var with same name is present, use it. Otherwise prompt (unless non-interactive).
  if [ -n "${!NAME:-}" ]; then
    create_or_update_secret "${NAME}" "${!NAME}"
  elif [ "${NONINTERACTIVE}" = "1" ]; then
    echo "Skipping ${NAME} (not provided)"
  else
    read -rsp "${NAME}: " VAL; echo ""
    [ -n "${VAL}" ] && create_or_update_secret "${NAME}" "${VAL}"
  fi
done

echo ""
echo "--- CMS OAuth (GitHub Pages CMS) ---"
for NAME in CMS_GITHUB_CLIENT_ID CMS_GITHUB_CLIENT_SECRET CMS_GITHUB_REDIRECT_URI \
            CMS_OAUTH_STATE_SECRET; do
  if [ -n "${!NAME:-}" ]; then
    create_or_update_secret "${NAME}" "${!NAME}"
  elif [ "${NONINTERACTIVE}" = "1" ]; then
    echo "Skipping ${NAME} (not provided)"
  else
    read -rsp "${NAME}: " VAL; echo ""
    [ -n "${VAL}" ] && create_or_update_secret "${NAME}" "${VAL}"
  fi
done

# ── Output ────────────────────────────────────────────────────────────────────
WIF_PROVIDER="projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "  GCP setup complete. Configure the following on GitHub for each repo:"
echo "  (microservices, auth-service, go-gateway, projects-service)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "  Settings → Secrets and variables → Actions"
echo ""
echo "  VARIABLE (not secret):"
echo "    GCP_PROJECT_ID  =  ${PROJECT_ID}"
echo ""
echo "  SECRETS:"
echo "    GCP_WORKLOAD_IDENTITY_PROVIDER  =  ${WIF_PROVIDER}"
echo "    GCP_SERVICE_ACCOUNT             =  ${SA_EMAIL}"
echo ""
echo "  Optional — ALLOWED_ORIGINS variable on microservices repo:"
echo "    ALLOWED_ORIGINS  =  https://rodmen07.github.io,https://<go-gateway-url>"
echo ""
echo "  Artifact Registry image base:"
echo "    ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY}/<service>:<sha>"
echo ""
echo "  After deploying, note the Cloud Run service URLs and update:"
echo "    go-gateway env vars (ACCOUNTS_URL, CONTACTS_URL, etc.)"
echo "    auth-service ALLOWED_ORIGINS"
echo "    frontend-service API base URL"
echo "════════════════════════════════════════════════════════════════════════"
