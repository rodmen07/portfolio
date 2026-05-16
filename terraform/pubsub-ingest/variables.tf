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
