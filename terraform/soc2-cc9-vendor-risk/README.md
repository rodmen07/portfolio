# soc2-cc9-vendor-risk

Terraform module implementing SOC 2 CC9.2 vendor risk management controls.

## Control

**CC9.2** - The entity assesses and manages risks associated with vendors and business partners.

## Resources created

| Resource | Purpose |
|---|---|
| `google_storage_bucket.vendor_evidence` | Stores SOC 2 reports, DPAs, SLAs, and signed agreements. Versioned with a 2-year retention policy. |
| `google_bigquery_table.vendors` | Central vendor inventory: risk tier, data classification, certification status, and review dates. |
| `google_pubsub_topic.vendor_alerts` | Message bus for review reminders and automated posture-change alerts. |
| `google_cloud_scheduler_job.vendor_review_reminder` | Quarterly reminder (default: 1st of each quarter, 9 AM ET) to action vendor reviews. |

## Usage

```hcl
module "vendor_risk" {
  source = "./terraform/soc2-cc9-vendor-risk"

  project_id               = "my-gcp-project"
  region                   = "us-central1"
  bucket_name              = "my-gcp-project-vendor-evidence"
  security_reviewer_emails = ["security@example.com", "compliance@example.com"]
}
```

## Vendor registry schema

The BigQuery `vendors` table tracks:

- **vendor_id** - unique slug (e.g. `aws`, `stripe`, `okta`)
- **risk_tier** - `critical | high | medium | low`; drives review frequency
- **data_classification** - highest sensitivity of data shared with the vendor
- **soc2_certified** - current SOC 2 Type II status
- **soc2_report_gcs_path** - pointer to the SOC 2 report in the evidence bucket
- **last_review_date / next_review_date** - review cadence tracking
- **offboarding_date** - set when a vendor relationship ends (audit trail)

## Review cadence

| Risk tier | Recommended review frequency |
|---|---|
| critical | Annual |
| high | Annual |
| medium | Biennial |
| low | Biennial |

The Cloud Scheduler job fires every quarter. The security team reviews vendors
whose `next_review_date` is within the upcoming 90 days.

## Inputs

| Name | Description | Default |
|---|---|---|
| `project_id` | GCP project ID | required |
| `region` | GCP region | `us-central1` |
| `bucket_name` | GCS bucket name for evidence | required |
| `security_reviewer_emails` | IAM emails granted read/write on evidence | `[]` |
| `vendor_registry_dataset_id` | BigQuery dataset ID | `vendor_risk_registry` |
| `pubsub_topic_name` | Pub/Sub topic name | `vendor-risk-alerts` |
| `review_schedule` | Cron for quarterly reminder | `0 9 1 */3 *` |
| `review_schedule_timezone` | Timezone for scheduler | `America/New_York` |

## Outputs

| Name | Description |
|---|---|
| `vendor_evidence_bucket` | GCS bucket name |
| `vendor_evidence_bucket_url` | GCS URL (`gs://...`) |
| `vendor_registry_dataset` | BigQuery dataset ID |
| `vendor_registry_table` | Fully-qualified BigQuery table ID |
| `vendor_alerts_topic` | Pub/Sub topic name |
| `vendor_alerts_topic_id` | Fully-qualified Pub/Sub topic ID |
| `review_reminder_job` | Cloud Scheduler job name |
