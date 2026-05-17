locals {
  primary_region_normalized  = replace(var.primary_region, "-", "")
  failover_region_normalized = replace(var.failover_region, "-", "")
  has_domain                 = var.domain != ""
}

# Global anycast IP shared by both HTTP and HTTPS forwarding rules.
resource "google_compute_global_address" "gateway" {
  name = "${var.name_prefix}-ip"
}

# ---------------------------------------------------------------------------
# Serverless NEGs — one per region. Health checks are not supported for
# serverless NEGs; Cloud Run manages its own health internally.
# ---------------------------------------------------------------------------
resource "google_compute_region_network_endpoint_group" "primary" {
  name                  = "${var.name_prefix}-${local.primary_region_normalized}-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.primary_region

  cloud_run {
    service = var.service_name
  }
}

resource "google_compute_region_network_endpoint_group" "failover" {
  name                  = "${var.name_prefix}-${local.failover_region_normalized}-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.failover_region

  cloud_run {
    service = var.service_name
  }
}

# Backend service fans out to both regional NEGs.
# No health_checks — not applicable to serverless NEG backends.
resource "google_compute_backend_service" "gateway" {
  name                  = "${var.name_prefix}-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30
  security_policy       = var.enable_cloud_armor ? google_compute_security_policy.waf[0].id : null

  backend {
    group = google_compute_region_network_endpoint_group.primary.id
  }

  backend {
    group = google_compute_region_network_endpoint_group.failover.id
  }
}

# ---------------------------------------------------------------------------
# HTTPS stack — only provisioned when var.domain is non-empty.
# ---------------------------------------------------------------------------
resource "google_compute_managed_ssl_certificate" "gateway" {
  count = local.has_domain ? 1 : 0
  name  = "${var.name_prefix}-cert"

  managed {
    domains = [var.domain]
  }
}

resource "google_compute_url_map" "gateway_https" {
  count           = local.has_domain ? 1 : 0
  name            = "${var.name_prefix}-https-url-map"
  default_service = google_compute_backend_service.gateway.id
}

resource "google_compute_target_https_proxy" "gateway" {
  count            = local.has_domain ? 1 : 0
  name             = "${var.name_prefix}-https-proxy"
  url_map          = google_compute_url_map.gateway_https[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.gateway[0].id]
}

resource "google_compute_global_forwarding_rule" "gateway_https" {
  count                 = local.has_domain ? 1 : 0
  name                  = "${var.name_prefix}-https-fr"
  target                = google_compute_target_https_proxy.gateway[0].id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.gateway.id
}

# ---------------------------------------------------------------------------
# HTTP stack — always present.
# When a domain is configured, redirects all HTTP traffic to HTTPS (301).
# Without a domain, routes directly to the backend service.
# ---------------------------------------------------------------------------
resource "google_compute_url_map" "gateway_http" {
  name = "${var.name_prefix}-http-url-map"

  dynamic "default_url_redirect" {
    for_each = local.has_domain ? [1] : []
    content {
      https_redirect         = true
      redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
      strip_query            = false
    }
  }

  default_service = local.has_domain ? null : google_compute_backend_service.gateway.id
}

resource "google_compute_target_http_proxy" "gateway" {
  name    = "${var.name_prefix}-http-proxy"
  url_map = google_compute_url_map.gateway_http.id
}

resource "google_compute_global_forwarding_rule" "gateway_http" {
  name                  = "${var.name_prefix}-http-fr"
  target                = google_compute_target_http_proxy.gateway.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.gateway.id
}

# ---------------------------------------------------------------------------
# Cloud Armor WAF security policy (v1.14.4).
# Enabled when var.enable_cloud_armor = true.
# Applies Google-managed preconfigured ModSecurity CRS rules for the most
# common web attack categories. All rules run in DENY mode (not preview).
# ---------------------------------------------------------------------------
resource "google_compute_security_policy" "waf" {
  count = var.enable_cloud_armor ? 1 : 0
  name  = "${var.name_prefix}-waf"

  rule {
    action      = "deny(403)"
    priority    = 1000
    description = "Block XSS attacks (OWASP CRS xss-v33-stable)"
    match {
      expr { expression = "evaluatePreconfiguredExpr('xss-v33-stable')" }
    }
  }

  rule {
    action      = "deny(403)"
    priority    = 1001
    description = "Block SQL injection (OWASP CRS sqli-v33-stable)"
    match {
      expr { expression = "evaluatePreconfiguredExpr('sqli-v33-stable')" }
    }
  }

  rule {
    action      = "deny(403)"
    priority    = 1002
    description = "Block local file inclusion (OWASP CRS lfi-v33-stable)"
    match {
      expr { expression = "evaluatePreconfiguredExpr('lfi-v33-stable')" }
    }
  }

  rule {
    action      = "deny(403)"
    priority    = 1003
    description = "Block remote file inclusion (OWASP CRS rfi-v33-stable)"
    match {
      expr { expression = "evaluatePreconfiguredExpr('rfi-v33-stable')" }
    }
  }

  rule {
    action      = "deny(403)"
    priority    = 1004
    description = "Block remote code execution (OWASP CRS rce-v33-stable)"
    match {
      expr { expression = "evaluatePreconfiguredExpr('rce-v33-stable')" }
    }
  }

  # Default allow — must be last (highest priority number).
  rule {
    action      = "allow"
    priority    = 2147483647
    description = "Default allow for all other traffic"
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
  }
}
