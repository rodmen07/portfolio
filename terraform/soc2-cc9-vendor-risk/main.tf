terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# GCS bucket - vendor evidence storage
# Stores SOC 2 reports, DPAs, SLAs, and other vendor agreements.
# Two-year retention satisfies typical SOC 2 evidence requirements.
# ---------------------------------------------------------------------------
resource "google_storage_bucket" "vendor_evidence" {
  name                        = var.bucket_name
  project                     = var.project_id
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  retention_policy {
    is_locked        = false
    retention_period = 63072000 # 730 days (2 years)
  }

  lifecycle_rule {
    condition {
      age = 730
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }
}

# Security team read access to evidence bucket
resource "google_storage_bucket_iam_binding" "vendor_evidence_readers" {
  bucket = google_storage_bucket.vendor_evidence.name
  role   = "roles/storage.objectViewer"
  members = [
    for email in var.security_reviewer_emails : "user:${email}"
  ]
}

# Security team write access to upload evidence
resource "google_storage_bucket_iam_binding" "vendor_evidence_writers" {
  bucket = google_storage_bucket.vendor_evidence.name
  role   = "roles/storage.objectCreator"
  members = [
    for email in var.security_reviewer_emails : "user:${email}"
  ]
}

# ---------------------------------------------------------------------------
# BigQuery - vendor risk registry
# Central inventory of third-party vendors with risk tier, data classification,
# certification status, and review dates. Satisfies CC9.2 inventory control.
# ---------------------------------------------------------------------------
resource "google_bigquery_dataset" "vendor_registry" {
  dataset_id                  = var.vendor_registry_dataset_id
  project                     = var.project_id
  location                    = var.region
  description                 = "SOC 2 CC9.2 vendor risk registry. Tracks third-party vendors, risk tiers, and review cadence."
  delete_contents_on_destroy  = false

  dynamic "access" {
    for_each = var.security_reviewer_emails
    content {
      role          = "READER"
      user_by_email = access.value
    }
  }
}

resource "google_bigquery_table" "vendors" {
  dataset_id          = google_bigquery_dataset.vendor_registry.dataset_id
  table_id            = "vendors"
  project             = var.project_id
  deletion_protection = true
  description         = "Vendor inventory for SOC 2 CC9.2 compliance."

  schema = jsonencode([
    {
      name        = "vendor_id"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Unique vendor identifier (slug)."
    },
    {
      name        = "name"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Vendor display name."
    },
    {
      name        = "category"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Vendor category: saas | infra | consulting | data_processor | payment."
    },
    {
      name        = "risk_tier"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Risk tier: critical | high | medium | low. Drives review frequency."
    },
    {
      name        = "data_classification"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Highest data classification shared: pii | financial | confidential | internal | public."
    },
    {
      name        = "soc2_certified"
      type        = "BOOL"
      mode        = "NULLABLE"
      description = "Whether the vendor holds a current SOC 2 Type II certification."
    },
    {
      name        = "soc2_report_gcs_path"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "GCS object path to the vendor's SOC 2 report in the evidence bucket."
    },
    {
      name        = "agreement_gcs_path"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "GCS object path to the signed agreement or DPA in the evidence bucket."
    },
    {
      name        = "last_review_date"
      type        = "DATE"
      mode        = "NULLABLE"
      description = "Date of the most recent vendor risk review."
    },
    {
      name        = "next_review_date"
      type        = "DATE"
      mode        = "NULLABLE"
      description = "Scheduled date of next review. Critical vendors: annual; others: biennial."
    },
    {
      name        = "offboarding_date"
      type        = "DATE"
      mode        = "NULLABLE"
      description = "Date vendor relationship ended. Null for active vendors."
    },
    {
      name        = "notes"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Free-form notes on risk posture or outstanding remediation items."
    },
    {
      name        = "updated_at"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "Timestamp of last record update."
    }
  ])
}

# ---------------------------------------------------------------------------
# Pub/Sub topic - vendor risk alerts
# Used by Cloud Scheduler for quarterly review reminders and by any
# automated tooling that detects vendor posture changes.
# ---------------------------------------------------------------------------
resource "google_pubsub_topic" "vendor_alerts" {
  name    = var.pubsub_topic_name
  project = var.project_id

  message_retention_duration = "86400s" # 1 day
}

# ---------------------------------------------------------------------------
# Cloud Scheduler - quarterly vendor review reminder
# Publishes a reminder message to the Pub/Sub topic every quarter.
# A downstream function or manual runbook acknowledges and actions the review.
# ---------------------------------------------------------------------------
resource "google_cloud_scheduler_job" "vendor_review_reminder" {
  name             = "vendor-review-reminder"
  project          = var.project_id
  region           = var.region
  description      = "SOC 2 CC9.2 - quarterly vendor risk review reminder."
  schedule         = var.review_schedule
  time_zone        = var.review_schedule_timezone
  attempt_deadline = "60s"

  retry_config {
    retry_count = 3
  }

  pubsub_target {
    topic_name = google_pubsub_topic.vendor_alerts.id
    data = base64encode(jsonencode({
      type    = "quarterly_review_reminder"
      message = "Quarterly vendor risk review due. Review the vendor registry and update risk tiers, certification status, and next_review_date for all active vendors."
    }))
  }
}
