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

variable "enable_cloud_armor" {
  description = "Enable Cloud Armor WAF on go-gateway load balancer backend."
  type        = bool
  default     = false
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

variable "pubsub_bigquery_dataset_id" {
  description = "BigQuery dataset ID for pubsub-ingest analytics sink. Leave empty to disable sink."
  type        = string
  default     = ""
}

variable "bq_enable_daily_aggregates" {
  description = "Enable scheduled daily aggregate query over crm_mutations table."
  type        = bool
  default     = false
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

# -- SLO + uptime (v1.15.4-1.15.6) -------------------------------------------
variable "gateway_availability_goal" {
  description = "Availability SLO target for go-gateway."
  type        = number
  default     = 0.999
}

variable "gateway_latency_goal" {
  description = "Latency SLO target for go-gateway."
  type        = number
  default     = 0.99
}

variable "gateway_latency_threshold_seconds" {
  description = "Latency SLO threshold in seconds for go-gateway."
  type        = number
  default     = 2
}

variable "slo_alert_email" {
  description = "Email notification channel for SLO burn and uptime alerts. Leave empty to disable."
  type        = string
  default     = ""
}

variable "uptime_checks" {
  description = "Map of uptime checks keyed by ID."
  type = map(object({
    display_name = string
    host         = string
    path         = string
    use_ssl      = bool
    port         = number
  }))
  default = {}
}

# -- Memorystore / Redis (v1.15.7) -------------------------------------------
variable "enable_gateway_redis" {
  description = "Provision Memorystore Redis for distributed gateway rate limiting."
  type        = bool
  default     = false
}

variable "gateway_redis_name" {
  description = "Redis instance name for go-gateway."
  type        = string
  default     = "go-gateway-redis"
}

variable "gateway_redis_tier" {
  description = "Redis instance tier (BASIC or STANDARD_HA)."
  type        = string
  default     = "BASIC"
}

variable "gateway_redis_memory_size_gb" {
  description = "Redis memory size in GB."
  type        = number
  default     = 1
}

variable "gateway_redis_secret_id" {
  description = "Secret Manager secret id used to store REDIS_URL."
  type        = string
  default     = "GO_GATEWAY_REDIS_URL"
}
