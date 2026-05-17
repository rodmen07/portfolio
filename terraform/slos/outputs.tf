output "monitoring_service_name" {
  description = "Monitoring custom service name used for SLO resources."
  value       = google_monitoring_custom_service.gateway.name
}

output "availability_slo_name" {
  description = "Availability SLO resource name."
  value       = google_monitoring_slo.availability.name
}

output "latency_slo_name" {
  description = "Latency SLO resource name."
  value       = google_monitoring_slo.latency.name
}
