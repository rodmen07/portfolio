variable "project_id" {
  description = "GCP project ID hosting Redis resources."
  type        = string
}

variable "region" {
  description = "Region for the Redis instance."
  type        = string
  default     = "us-central1"
}

variable "name" {
  description = "Redis instance name."
  type        = string
  default     = "go-gateway-redis"
}

variable "tier" {
  description = "Redis service tier (BASIC or STANDARD_HA)."
  type        = string
  default     = "BASIC"
}

variable "memory_size_gb" {
  description = "Redis memory size in GB."
  type        = number
  default     = 1
}

variable "redis_version" {
  description = "Redis engine version."
  type        = string
  default     = "REDIS_7_0"
}

variable "connect_mode" {
  description = "Connection mode (DIRECT_PEERING or PRIVATE_SERVICE_ACCESS)."
  type        = string
  default     = "DIRECT_PEERING"
}

variable "enable_secret" {
  description = "Whether to write REDIS_URL to Secret Manager."
  type        = bool
  default     = true
}

variable "secret_id" {
  description = "Secret Manager secret id that stores REDIS_URL."
  type        = string
  default     = "GO_GATEWAY_REDIS_URL"
}
