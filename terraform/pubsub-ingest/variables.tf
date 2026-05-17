variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region for resources."
  type        = string
  default     = "us-central1"
}

variable "topic_name" {
  description = "Pub/Sub topic name for CRM mutation ingest events."
  type        = string
  default     = "crm-mutation-ingest"
}

variable "observaboard_ingest_url" {
  description = "Full URL of the observaboard ingest endpoint (e.g. https://observaboard-xxx.run.app/api/ingest/)."
  type        = string
}

variable "observaboard_sa_email" {
  description = "Service account email that Pub/Sub will use to generate OIDC tokens for the push subscription."
  type        = string
}

variable "message_retention_duration" {
  description = "How long undelivered messages are retained (e.g. '86400s' = 1 day)."
  type        = string
  default     = "86400s"
}

variable "dead_letter_topic_name" {
  description = "Pub/Sub topic name for dead-lettered messages (created automatically)."
  type        = string
  default     = "crm-mutation-ingest-deadletter"
}

variable "max_delivery_attempts" {
  description = "Maximum delivery attempts before routing to the dead-letter topic."
  type        = number
  default     = 5
}

variable "alert_email" {
  description = "Email address for Cloud Monitoring alerts when messages accumulate in the dead-letter topic. Leave empty to skip alert creation."
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# BigQuery sink (v1.13)
# ---------------------------------------------------------------------------

variable "bigquery_dataset_id" {
  description = "BigQuery dataset ID for the CRM mutation analytics sink. Leave empty to skip BigQuery subscription creation."
  type        = string
  default     = ""
}

variable "bigquery_table_id" {
  description = "BigQuery table name for the CRM mutation analytics sink (created inside bigquery_dataset_id)."
  type        = string
  default     = "crm_mutations"
}

# ---------------------------------------------------------------------------
# Ingest spike alert (v1.13)
# ---------------------------------------------------------------------------

variable "spike_alert_email" {
  description = "Email for Cloud Monitoring alerts when the ingest topic publish rate exceeds the spike threshold. Leave empty to skip spike alert creation."
  type        = string
  default     = ""
}

variable "spike_threshold_per_min" {
  description = "Message publish rate (messages/minute) above which the ingest spike alert fires."
  type        = number
  default     = 1000
}

# ---------------------------------------------------------------------------
# BigQuery scheduled query / daily aggregates (v1.14.6)
# ---------------------------------------------------------------------------

variable "bq_enable_daily_aggregates" {
  description = "Create a BigQuery Data Transfer scheduled query that produces a daily_crm_summary table from crm_mutations. Requires bigquery_dataset_id and the BigQuery Data Transfer API to be enabled in the project."
  type        = bool
  default     = false
}
