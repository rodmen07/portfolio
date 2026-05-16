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
