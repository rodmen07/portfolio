resource "google_redis_instance" "gateway" {
  name               = var.name
  project            = var.project_id
  region             = var.region
  tier               = var.tier
  memory_size_gb     = var.memory_size_gb
  redis_version      = var.redis_version
  connect_mode       = var.connect_mode
  display_name       = "go-gateway redis"
  auth_enabled       = false
  transit_encryption_mode = "DISABLED"
}

locals {
  redis_url = "redis://${google_redis_instance.gateway.host}:${google_redis_instance.gateway.port}"
}

resource "google_secret_manager_secret" "redis_url" {
  count     = var.enable_secret ? 1 : 0
  secret_id = var.secret_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "redis_url" {
  count       = var.enable_secret ? 1 : 0
  secret      = google_secret_manager_secret.redis_url[0].id
  secret_data = local.redis_url
}
