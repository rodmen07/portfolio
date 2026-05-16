output "vendor_evidence_bucket" {
  description = "GCS bucket name for vendor evidence (SOC 2 reports, DPAs, contracts)."
  value       = google_storage_bucket.vendor_evidence.name
}

output "vendor_evidence_bucket_url" {
  description = "GCS URL for the vendor evidence bucket."
  value       = "gs://${google_storage_bucket.vendor_evidence.name}"
}

output "vendor_registry_dataset" {
  description = "BigQuery dataset ID for the vendor risk registry."
  value       = google_bigquery_dataset.vendor_registry.dataset_id
}

output "vendor_registry_table" {
  description = "Fully-qualified BigQuery table ID for the vendor inventory."
  value       = "${var.project_id}.${google_bigquery_dataset.vendor_registry.dataset_id}.${google_bigquery_table.vendors.table_id}"
}

output "vendor_alerts_topic" {
  description = "Pub/Sub topic name for vendor risk alerts."
  value       = google_pubsub_topic.vendor_alerts.name
}

output "vendor_alerts_topic_id" {
  description = "Fully-qualified Pub/Sub topic ID."
  value       = google_pubsub_topic.vendor_alerts.id
}

output "review_reminder_job" {
  description = "Cloud Scheduler job name for quarterly vendor review reminders."
  value       = google_cloud_scheduler_job.vendor_review_reminder.name
}
