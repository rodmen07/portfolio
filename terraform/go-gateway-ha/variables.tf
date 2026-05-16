variable "project_id" {
  description = "GCP project ID hosting go-gateway and load-balancing resources."
  type        = string
}

variable "service_name" {
  description = "Cloud Run service name deployed in each region."
  type        = string
  default     = "go-gateway"
}

variable "primary_region" {
  description = "Primary Cloud Run region."
  type        = string
  default     = "us-south1"
}

variable "failover_region" {
  description = "Failover Cloud Run region."
  type        = string
  default     = "us-west1"
}

variable "name_prefix" {
  description = "Resource name prefix for global LB objects."
  type        = string
  default     = "go-gateway-ha"
}

variable "domain" {
  description = "Custom domain for the managed SSL certificate (e.g. api.example.com). Leave empty to use HTTP only."
  type        = string
  default     = ""
}
