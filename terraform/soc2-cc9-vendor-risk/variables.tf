variable "project_id" {
  description = "GCP project ID where resources will be created."
  type        = string
}

variable "region" {
  description = "GCP region for regional resources (BigQuery dataset location, Cloud Scheduler)."
  type        = string
  default     = "us-central1"
}

variable "bucket_name" {
  description = "GCS bucket name for vendor evidence storage (SOC 2 reports, DPAs, contracts)."
  type        = string
}

variable "security_reviewer_emails" {
  description = "List of IAM user emails granted read access to the vendor evidence bucket and BigQuery registry."
  type        = list(string)
  default     = []
}

variable "vendor_registry_dataset_id" {
  description = "BigQuery dataset ID for the vendor risk registry."
  type        = string
  default     = "vendor_risk_registry"
}

variable "pubsub_topic_name" {
  description = "Pub/Sub topic name for vendor risk alerts and review reminders."
  type        = string
  default     = "vendor-risk-alerts"
}

variable "review_schedule" {
  description = "Cron schedule for quarterly vendor review reminders (Cloud Scheduler)."
  type        = string
  default     = "0 9 1 */3 *"
}

variable "review_schedule_timezone" {
  description = "Timezone for the quarterly review scheduler job."
  type        = string
  default     = "America/New_York"
}
