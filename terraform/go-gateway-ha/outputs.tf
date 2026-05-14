output "global_ip" {
  description = "Global external IP for the go-gateway HA load balancer."
  value       = google_compute_global_address.gateway.address
}

output "http_endpoint" {
  description = "HTTP endpoint for the global load balancer."
  value       = "http://${google_compute_global_address.gateway.address}"
}

output "regional_backends" {
  description = "Cloud Run regional backends configured for the load balancer."
  value = {
    primary  = var.primary_region
    failover = var.failover_region
  }
}
