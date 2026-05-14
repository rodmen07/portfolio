locals {
  primary_region_slug  = replace(var.primary_region, "-", "")
  failover_region_slug = replace(var.failover_region, "-", "")
}

resource "google_compute_global_address" "gateway" {
  name = "${var.name_prefix}-ip"
}

resource "google_compute_region_network_endpoint_group" "primary" {
  name                  = "${var.name_prefix}-${local.primary_region_slug}-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.primary_region

  cloud_run {
    service = var.service_name
  }
}

resource "google_compute_region_network_endpoint_group" "failover" {
  name                  = "${var.name_prefix}-${local.failover_region_slug}-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.failover_region

  cloud_run {
    service = var.service_name
  }
}

resource "google_compute_health_check" "gateway" {
  name = "${var.name_prefix}-health"

  check_interval_sec  = 5
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 2

  http_health_check {
    request_path = "/health"
    port         = 80
  }
}

resource "google_compute_backend_service" "gateway" {
  name                  = "${var.name_prefix}-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30
  health_checks         = [google_compute_health_check.gateway.id]

  backend {
    group = google_compute_region_network_endpoint_group.primary.id
  }

  backend {
    group = google_compute_region_network_endpoint_group.failover.id
  }
}

resource "google_compute_url_map" "gateway" {
  name            = "${var.name_prefix}-url-map"
  default_service = google_compute_backend_service.gateway.id
}

resource "google_compute_target_http_proxy" "gateway" {
  name    = "${var.name_prefix}-http-proxy"
  url_map = google_compute_url_map.gateway.id
}

resource "google_compute_global_forwarding_rule" "gateway" {
  name                  = "${var.name_prefix}-http-fr"
  target                = google_compute_target_http_proxy.gateway.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.gateway.id
}
