output "redis_host" {
  description = "Memorystore Redis host."
  value       = google_redis_instance.gateway.host
}

output "redis_port" {
  description = "Memorystore Redis port."
  value       = google_redis_instance.gateway.port
}

output "redis_url" {
  description = "Connection URL for go-gateway distributed rate limiter."
  value       = local.redis_url
  sensitive   = true
}

output "secret_name" {
  description = "Secret Manager secret name storing REDIS_URL (if enabled)."
  value       = var.enable_secret ? google_secret_manager_secret.redis_url[0].name : null
}
