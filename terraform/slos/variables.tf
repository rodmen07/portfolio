variable "project_id" {
  description = "GCP project ID for monitoring resources."
  type        = string
}

variable "service_name" {
  description = "Logical service name for the custom monitoring service."
  type        = string
  default     = "go-gateway"
}

variable "region" {
  description = "Primary region label used in resource filters."
  type        = string
  default     = "us-central1"
}

variable "availability_goal" {
  description = "Availability SLO goal (for example 0.999 for 99.9%)."
  type        = number
  default     = 0.999
}

variable "latency_goal" {
  description = "Latency SLO goal percentage for requests under latency_threshold_seconds."
  type        = number
  default     = 0.99
}

variable "latency_threshold_seconds" {
  description = "Latency threshold in seconds for the latency SLO."
  type        = number
  default     = 2
}

variable "notification_email" {
  description = "Email for SLO and uptime alert notifications. Leave empty to skip alerting resources."
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
