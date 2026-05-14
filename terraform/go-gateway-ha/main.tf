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

resource "google_compute_backend_service" "gateway" {
  name                  = "${var.name_prefix}-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30

  backend {
    group = google_compute_region_network_endpoint_group.primary.id
  }

  backend {
    group    = google_compute_region_network_endpoint_group.failover.id
    failover = true
  }

  failover_policy {
    failover_ratio                        = 0.5
    disable_connection_drain_on_failover = false
    drop_traffic_if_unhealthy            = false
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
