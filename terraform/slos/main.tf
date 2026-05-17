resource "google_monitoring_custom_service" "gateway" {
  service_id   = "${var.service_name}-service"
  display_name = "${var.service_name} Service"
}

# ---------------------------------------------------------------------------
# SLOs: availability + p99 latency under threshold
# ---------------------------------------------------------------------------
resource "google_monitoring_slo" "availability" {
  service             = google_monitoring_custom_service.gateway.service_id
  slo_id              = "${var.service_name}-availability"
  display_name        = "${var.service_name} availability"
  goal                = var.availability_goal
  rolling_period_days = 28

  request_based_sli {
    good_total_ratio {
      total_service_filter = join(" AND ", [
        "metric.type=\"run.googleapis.com/request_count\"",
        "resource.type=\"cloud_run_revision\"",
        "resource.label.\"service_name\"=\"${var.service_name}\"",
      ])

      good_service_filter = join(" AND ", [
        "metric.type=\"run.googleapis.com/request_count\"",
        "resource.type=\"cloud_run_revision\"",
        "resource.label.\"service_name\"=\"${var.service_name}\"",
        "metric.label.\"response_code_class\"!=\"500\"",
      ])
    }
  }
}

resource "google_monitoring_slo" "latency" {
  service             = google_monitoring_custom_service.gateway.service_id
  slo_id              = "${var.service_name}-latency"
  display_name        = "${var.service_name} latency"
  goal                = var.latency_goal
  rolling_period_days = 28

  request_based_sli {
    distribution_cut {
      distribution_filter = join(" AND ", [
        "metric.type=\"run.googleapis.com/request_latencies\"",
        "resource.type=\"cloud_run_revision\"",
        "resource.label.\"service_name\"=\"${var.service_name}\"",
      ])
      range {
        max = var.latency_threshold_seconds
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Error budget burn alerts
# ---------------------------------------------------------------------------
resource "google_monitoring_notification_channel" "email" {
  count        = var.notification_email != "" ? 1 : 0
  display_name = "SLO alerts - ${var.service_name}"
  type         = "email"

  labels = {
    email_address = var.notification_email
  }
}

resource "google_monitoring_alert_policy" "burn_fast" {
  count        = var.notification_email != "" ? 1 : 0
  display_name = "${var.service_name} error budget burn - fast"
  combiner     = "OR"

  conditions {
    display_name = "Fast burn (>2% budget in 1h)"

    condition_monitoring_query_language {
      duration = "0s"
      query    = "select_slo_burn_rate(\"${google_monitoring_slo.availability.name}\", \"3600s\") > 2"
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]
  severity              = "CRITICAL"
}

resource "google_monitoring_alert_policy" "burn_slow" {
  count        = var.notification_email != "" ? 1 : 0
  display_name = "${var.service_name} error budget burn - slow"
  combiner     = "OR"

  conditions {
    display_name = "Slow burn (>5% budget in 6h)"

    condition_monitoring_query_language {
      duration = "0s"
      query    = "select_slo_burn_rate(\"${google_monitoring_slo.availability.name}\", \"21600s\") > 1"
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]
  severity              = "WARNING"
}

# ---------------------------------------------------------------------------
# Uptime checks + alert policies
# ---------------------------------------------------------------------------
resource "google_monitoring_uptime_check_config" "service" {
  for_each     = var.uptime_checks
  display_name = each.value.display_name
  timeout      = "10s"
  period       = "60s"

  monitored_resource {
    type = "uptime_url"
    labels = {
      host       = each.value.host
      project_id = var.project_id
    }
  }

  http_check {
    path         = each.value.path
    port         = each.value.port
    use_ssl      = each.value.use_ssl
    validate_ssl = each.value.use_ssl
  }
}

resource "google_monitoring_alert_policy" "uptime" {
  for_each     = var.notification_email != "" ? google_monitoring_uptime_check_config.service : {}
  display_name = "Uptime failure - ${each.value.display_name}"
  combiner     = "OR"

  conditions {
    display_name = "Uptime check failing for ${each.value.display_name}"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\"",
        "resource.type=\"uptime_url\"",
        "metric.label.\"check_id\"=\"${each.value.uptime_check_id}\"",
      ])

      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "180s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_FRACTION_TRUE"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]
  severity              = "WARNING"
}
