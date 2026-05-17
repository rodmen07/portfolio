terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.40, < 6.0"
    }
  }

  # State is stored in GCS. Pass bucket and prefix via -backend-config flags or
  # a backend.hcl file at init time, e.g.:
  #   terraform init \
  #     -backend-config="bucket=<state-bucket>" \
  #     -backend-config="prefix=portfolio/prod"
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}
