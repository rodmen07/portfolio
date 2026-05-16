output "global_ip" {
  description = "Global external IP for the go-gateway HA load balancer."
  value       = google_compute_global_address.gateway.address
}

output "http_endpoint" {
  description = "HTTP endpoint. Redirects to HTTPS when var.domain is set."
  value       = "http://${google_compute_global_address.gateway.address}"
}

output "https_endpoint" {
  description = "HTTPS endpoint (only populated when var.domain is set)."
  value       = local.has_domain ? "https://${var.domain}" : null
}

output "regional_backends" {
  description = "Cloud Run regional backends configured for the load balancer."
  value = {
    primary  = var.primary_region
    failover = var.failover_region
  }
}
