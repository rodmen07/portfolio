# Pub/Sub ingest pipeline for CRM mutation events.
#
# go-gateway publishes a JSON message to `crm-mutation-ingest` for every
# successful CRM mutation (POST/PATCH/PUT/DELETE on observed routes).
#
# A push subscription delivers each message to observaboard's /api/ingest/
# endpoint with an OIDC token so observaboard can verify the caller.
#
# Undeliverable messages are routed to a dead-letter topic after
# var.max_delivery_attempts, preventing the main topic from backing up.

# ---------------------------------------------------------------------------
# Main ingest topic
# ---------------------------------------------------------------------------
resource "google_pubsub_topic" "ingest" {
  name                       = var.topic_name
  message_retention_duration = var.message_retention_duration
}

# ---------------------------------------------------------------------------
# Dead-letter topic + subscription (required for dead-letter policy to work)
# ---------------------------------------------------------------------------
resource "google_pubsub_topic" "dead_letter" {
  name                       = var.dead_letter_topic_name
  message_retention_duration = "604800s" # 7 days
}

resource "google_pubsub_subscription" "dead_letter_drain" {
  name  = "${var.dead_letter_topic_name}-drain"
  topic = google_pubsub_topic.dead_letter.id

  # Manual inspection only — no auto-delete; retain 7 days.
  message_retention_duration = "604800s"
  retain_acked_messages      = true
  ack_deadline_seconds       = 20
}

# Grant Pub/Sub's service account permission to publish to the dead-letter topic.
resource "google_pubsub_topic_iam_member" "pubsub_sa_dead_letter_publish" {
  topic  = google_pubsub_topic.dead_letter.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

data "google_project" "project" {
  project_id = var.project_id
}

# ---------------------------------------------------------------------------
# Push subscription — delivers to observaboard /api/ingest/ with OIDC token
# ---------------------------------------------------------------------------
resource "google_pubsub_subscription" "ingest_push" {
  name  = "${var.topic_name}-push"
  topic = google_pubsub_topic.ingest.id

  ack_deadline_seconds = 20

  push_config {
    push_endpoint = var.observaboard_ingest_url

    oidc_token {
      service_account_email = var.observaboard_sa_email
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = var.max_delivery_attempts
  }
}

# ---------------------------------------------------------------------------
# IAM — go-gateway service account must be able to publish to the topic.
# Set gateway_sa_email via a variable or add the binding in the caller module.
# ---------------------------------------------------------------------------
variable "gateway_sa_email" {
  description = "Service account email for go-gateway (publisher). Leave empty to skip IAM binding."
  type        = string
  default     = ""
}

resource "google_pubsub_topic_iam_member" "gateway_publish" {
  count  = var.gateway_sa_email != "" ? 1 : 0
  topic  = google_pubsub_topic.ingest.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${var.gateway_sa_email}"
}

# ---------------------------------------------------------------------------
# Cloud Monitoring — alert when messages accumulate in the dead-letter topic
# (v1.12.4)
# ---------------------------------------------------------------------------

resource "google_monitoring_notification_channel" "dead_letter_email" {
  count        = var.alert_email != "" ? 1 : 0
  display_name = "Dead-letter alert: ${var.dead_letter_topic_name}"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }
}

resource "google_monitoring_alert_policy" "dead_letter" {
  count        = var.alert_email != "" ? 1 : 0
  display_name = "Pub/Sub dead-letter backlog: ${var.dead_letter_topic_name}"
  combiner     = "OR"

  conditions {
    display_name = "Undelivered messages in dead-letter drain subscription"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type = \"pubsub_subscription\"",
        "resource.labels.subscription_id = \"${google_pubsub_subscription.dead_letter_drain.name}\"",
        "metric.type = \"pubsub.googleapis.com/subscription/num_undelivered_messages\"",
      ])

      # Alert when at least 1 message has been undelivered for 5 minutes.
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.dead_letter_email[0].name]

  severity = "WARNING"

  documentation {
    content = <<-EOT
      Messages have accumulated in the Pub/Sub dead-letter topic '${var.dead_letter_topic_name}'.

      This means go-gateway observer events failed to be delivered to the observaboard
      ingest endpoint (${var.observaboard_ingest_url}) after ${var.max_delivery_attempts} attempts.

      Remediation steps:
      1. Check Cloud Run logs for the observaboard service — look for 4xx/5xx on /api/ingest/.
      2. Inspect messages in the dead-letter drain subscription using the Cloud Console
         or: gcloud pubsub subscriptions pull ${var.dead_letter_topic_name}-drain --limit=10
      3. Replay valid messages by republishing them to ${var.topic_name} once the issue is resolved.
         See go-gateway/scripts/replay-deadletter.sh for an automated replay helper.
    EOT
  }
}

# ---------------------------------------------------------------------------
# BigQuery sink — forward all ingest messages to BQ for analytics
# (v1.13 — enabled when bigquery_dataset_id is set)
# ---------------------------------------------------------------------------

resource "google_bigquery_dataset" "ingest_sink" {
  count       = var.bigquery_dataset_id != "" ? 1 : 0
  dataset_id  = var.bigquery_dataset_id
  location    = var.region
  description = "CRM mutation ingest events streamed from the Pub/Sub ingest pipeline."
}

resource "google_bigquery_table" "crm_mutations" {
  count               = var.bigquery_dataset_id != "" ? 1 : 0
  dataset_id          = google_bigquery_dataset.ingest_sink[0].dataset_id
  table_id            = var.bigquery_table_id
  deletion_protection = false

  schema = jsonencode([
    { name = "subscription_name", type = "STRING", mode = "NULLABLE", description = "Pub/Sub subscription name." },
    { name = "message_id", type = "STRING", mode = "NULLABLE", description = "Pub/Sub message ID." },
    { name = "publish_time", type = "TIMESTAMP", mode = "NULLABLE", description = "Message publish timestamp." },
    { name = "data", type = "STRING", mode = "NULLABLE", description = "Base64-encoded message payload." },
    { name = "attributes", type = "STRING", mode = "NULLABLE", description = "Message attributes serialised as JSON." },
  ])
}

# Pub/Sub service account needs BigQuery Data Editor on the sink dataset.
resource "google_bigquery_dataset_iam_member" "pubsub_bq_editor" {
  count      = var.bigquery_dataset_id != "" ? 1 : 0
  dataset_id = google_bigquery_dataset.ingest_sink[0].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription" "bigquery_sink" {
  count = var.bigquery_dataset_id != "" ? 1 : 0
  name  = "${var.topic_name}-bq-sink"
  topic = google_pubsub_topic.ingest.id

  bigquery_config {
    table          = "${var.project_id}.${google_bigquery_dataset.ingest_sink[0].dataset_id}.${google_bigquery_table.crm_mutations[0].table_id}"
    write_metadata = true
  }

  depends_on = [google_bigquery_dataset_iam_member.pubsub_bq_editor]
}

# ---------------------------------------------------------------------------
# Cloud Monitoring — alert on ingest topic publish spike
# (v1.13 — enabled when spike_alert_email is set)
# ---------------------------------------------------------------------------

resource "google_monitoring_notification_channel" "spike_email" {
  count        = var.spike_alert_email != "" ? 1 : 0
  display_name = "Ingest spike alert: ${var.topic_name}"
  type         = "email"

  labels = {
    email_address = var.spike_alert_email
  }
}

resource "google_monitoring_alert_policy" "ingest_spike" {
  count        = var.spike_alert_email != "" ? 1 : 0
  display_name = "Pub/Sub ingest spike: ${var.topic_name}"
  combiner     = "OR"

  conditions {
    display_name = "High publish rate on ${var.topic_name}"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type = \"pubsub_topic\"",
        "resource.labels.topic_id = \"${google_pubsub_topic.ingest.name}\"",
        "metric.type = \"pubsub.googleapis.com/topic/send_message_operation_count\"",
      ])

      # ALIGN_DELTA over 60 s gives the count of messages published in that window.
      comparison      = "COMPARISON_GT"
      threshold_value = var.spike_threshold_per_min
      duration        = "60s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.labels.topic_id"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.spike_email[0].name]

  severity = "WARNING"

  documentation {
    content = <<-EOT
      The ingest topic '${var.topic_name}' is receiving more than ${var.spike_threshold_per_min}
      messages per minute — this may indicate an unexpected traffic surge or a publishing loop.

      Remediation steps:
      1. Review go-gateway Cloud Run logs for unusual request patterns.
      2. Check the Pub/Sub topic metrics dashboard for the source of the spike.
      3. If the spike is legitimate (e.g. a bulk import), increase spike_threshold_per_min
         in Terraform variables and re-apply.
      4. If the spike is unintended, trace back to the publishing service and apply
         rate limits or circuit breakers as appropriate.
    EOT
  }
}

# ---------------------------------------------------------------------------
# BigQuery scheduled query — daily CRM mutation aggregates (v1.14.6)
# Enabled when bq_enable_daily_aggregates = true AND bigquery_dataset_id != "".
# Runs every 24 hours and writes a daily_crm_summary table with per-day,
# per-resource-type, per-method event counts derived from the raw crm_mutations
# table. Requires the BigQuery Data Transfer API to be enabled in the project.
# ---------------------------------------------------------------------------
resource "google_bigquery_data_transfer_config" "daily_crm_agg" {
  count = (var.bq_enable_daily_aggregates && var.bigquery_dataset_id != "") ? 1 : 0

  display_name           = "${var.topic_name}-daily-crm-summary"
  location               = var.region
  data_source_id         = "scheduled_query"
  schedule               = "every 24 hours"
  destination_dataset_id = google_bigquery_dataset.ingest_sink[0].dataset_id

  params = {
    query = <<-SQL
      SELECT
        TIMESTAMP_TRUNC(publish_time, DAY)                                      AS day,
        IFNULL(JSON_EXTRACT_SCALAR(attributes, '$.resource_type'), 'unknown')   AS resource_type,
        IFNULL(JSON_EXTRACT_SCALAR(attributes, '$.method'), 'unknown')          AS method,
        COUNT(*)                                                                 AS event_count
      FROM `${var.project_id}.${var.bigquery_dataset_id}.${var.bigquery_table_id}`
      WHERE publish_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 25 HOUR)
      GROUP BY 1, 2, 3
      ORDER BY 1 DESC, 4 DESC
    SQL

    destination_table_name_template = "daily_crm_summary"
    write_disposition               = "WRITE_TRUNCATE"
  }

  depends_on = [google_bigquery_table.crm_mutations]
}
