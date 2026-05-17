# ── Shared ────────────────────────────────────────────────────────────────────

variable "project_id" {
  description = "GCP project ID for all resources in this environment."
  type        = string
}

variable "region" {
  description = "Default GCP region."
  type        = string
  default     = "us-central1"
}

# ── go-gateway HA global load balancer (v1.11.1) ──────────────────────────────

variable "gateway_domain" {
  description = "Custom domain for the HTTPS load balancer (e.g. api.example.com). Leave empty for HTTP only."
  type        = string
  default     = ""
}

variable "gateway_sa_email" {
  description = "Service account email for the go-gateway Cloud Run service. Used to grant Pub/Sub publisher role."
  type        = string
  default     = ""
}

# ── Cloud SQL cross-region read replica (v1.11.2) ────────────────────────────

variable "primary_instance_name" {
  description = "Name of the primary Cloud SQL PostgreSQL instance to replicate."
  type        = string
}

variable "replica_name" {
  description = "Name for the read replica instance."
  type        = string
  default     = "postgres-replica-us-west1"
}

variable "replica_tier" {
  description = "Cloud SQL machine tier for the read replica."
  type        = string
  default     = "db-f1-micro"
}

variable "replica_deletion_protection" {
  description = "Prevent Terraform from destroying the read replica."
  type        = bool
  default     = false
}

# ── Pub/Sub CRM ingest pipeline (v1.11.3) ────────────────────────────────────

variable "observaboard_ingest_url" {
  description = "Full URL of the observaboard /api/ingest/ push endpoint."
  type        = string
}

variable "observaboard_sa_email" {
  description = "Service account email Pub/Sub uses to generate OIDC tokens for the push subscription."
  type        = string
}

variable "pubsub_alert_email" {
  description = "Email address for Cloud Monitoring alerts when messages land in the dead-letter topic. Leave empty to skip."
  type        = string
  default     = ""
}

# ── SOC 2 CC9.2 vendor risk (v1.8.x) ─────────────────────────────────────────

variable "vendor_bucket_name" {
  description = "GCS bucket name for SOC 2 vendor evidence storage (SOC 2 reports, DPAs, contracts)."
  type        = string
}

variable "security_reviewer_emails" {
  description = "IAM user emails granted read access to the vendor evidence bucket and BigQuery registry."
  type        = list(string)
  default     = []
}
