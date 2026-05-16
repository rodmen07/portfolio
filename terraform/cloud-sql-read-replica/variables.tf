variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "primary_instance_name" {
  description = "Name of the primary Cloud SQL instance to replicate from."
  type        = string
}

variable "replica_name" {
  description = "Name for the read replica instance."
  type        = string
}

variable "replica_region" {
  description = "GCP region for the read replica (must differ from primary for cross-region HA)."
  type        = string
  default     = "us-west1"
}

variable "tier" {
  description = "Cloud SQL machine tier for the replica."
  type        = string
  default     = "db-f1-micro"
}

variable "deletion_protection" {
  description = "Prevent Terraform from destroying the replica instance."
  type        = bool
  default     = false
}
