output "topic_id" {
  description = "Pub/Sub topic ID for CRM mutation ingest events."
  value       = google_pubsub_topic.ingest.id
}

output "topic_name" {
  description = "Pub/Sub topic name to set as PUBSUB_TOPIC in go-gateway."
  value       = google_pubsub_topic.ingest.name
}

output "push_subscription_id" {
  description = "ID of the push subscription delivering messages to observaboard."
  value       = google_pubsub_subscription.ingest_push.id
}

output "dead_letter_topic_id" {
  description = "Pub/Sub dead-letter topic ID."
  value       = google_pubsub_topic.dead_letter.id
}
