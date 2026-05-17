# Production environment — wires all Portfolio Terraform modules together.
# Modules are sourced from sibling directories under terraform/.
#
# Usage:
#   cd terraform/envs/prod
#   terraform init -backend-config="bucket=<state-bucket>" \
#                  -backend-config="prefix=portfolio/prod"
#   cp terraform.tfvars.example terraform.tfvars   # fill in values
#   terraform plan
#   terraform apply

# ── go-gateway global HTTPS load balancer (v1.11.1) ──────────────────────────
module "go_gateway_ha" {
  source = "../../go-gateway-ha"

  project_id         = var.project_id
  domain             = var.gateway_domain
  enable_cloud_armor = var.enable_cloud_armor
}

# ── Cloud SQL cross-region read replica (v1.11.2) ────────────────────────────
module "cloud_sql_replica" {
  source = "../../cloud-sql-read-replica"

  project_id            = var.project_id
  primary_instance_name = var.primary_instance_name
  replica_name          = var.replica_name
  tier                  = var.replica_tier
  replica_region        = "us-west1"
  deletion_protection   = var.replica_deletion_protection
}

# ── Pub/Sub CRM mutation ingest pipeline (v1.11.3) ───────────────────────────
module "pubsub_ingest" {
  source = "../../pubsub-ingest"

  project_id                 = var.project_id
  observaboard_ingest_url    = var.observaboard_ingest_url
  observaboard_sa_email      = var.observaboard_sa_email
  gateway_sa_email           = var.gateway_sa_email
  alert_email                = var.pubsub_alert_email
  bigquery_dataset_id        = var.pubsub_bigquery_dataset_id
  bq_enable_daily_aggregates = var.bq_enable_daily_aggregates
}

# -- Monitoring SLOs + burn alerts + uptime checks (v1.15.4-1.15.6) ----------
module "gateway_slos" {
  source = "../../slos"

  project_id                = var.project_id
  region                    = var.region
  service_name              = "go-gateway"
  availability_goal         = var.gateway_availability_goal
  latency_goal              = var.gateway_latency_goal
  latency_threshold_seconds = var.gateway_latency_threshold_seconds
  notification_email        = var.slo_alert_email
  uptime_checks             = var.uptime_checks
}

# -- Distributed rate limiting state (v1.15.7) --------------------------------
module "gateway_redis" {
  source = "../../memorystore"
  count  = var.enable_gateway_redis ? 1 : 0

  project_id     = var.project_id
  region         = var.region
  name           = var.gateway_redis_name
  tier           = var.gateway_redis_tier
  memory_size_gb = var.gateway_redis_memory_size_gb
  enable_secret  = true
  secret_id      = var.gateway_redis_secret_id
}

# ── SOC 2 CC9.2 vendor risk module (v1.8.x) ──────────────────────────────────
module "soc2_cc9_vendor_risk" {
  source = "../../soc2-cc9-vendor-risk"

  project_id               = var.project_id
  region                   = var.region
  bucket_name              = var.vendor_bucket_name
  security_reviewer_emails = var.security_reviewer_emails
}

# ── Aggregated outputs ────────────────────────────────────────────────────────

output "gateway_http_ip" {
  description = "Global anycast IP for the go-gateway HTTPS load balancer."
  value       = module.go_gateway_ha.http_endpoint
}

output "gateway_https_endpoint" {
  description = "HTTPS endpoint for go-gateway (null when no domain is configured)."
  value       = module.go_gateway_ha.https_endpoint
}

output "replica_connection_name" {
  description = "Cloud SQL read replica connection name (for Cloud SQL Auth Proxy)."
  value       = module.cloud_sql_replica.connection_name
}

output "replica_database_url_template" {
  description = "DATABASE_REPLICA_URL template string (fill in user/password/dbname)."
  value       = module.cloud_sql_replica.database_replica_url_template
  sensitive   = true
}

output "pubsub_ingest_topic" {
  description = "Pub/Sub topic name to set as PUBSUB_TOPIC in go-gateway."
  value       = module.pubsub_ingest.topic_name
}

output "gateway_availability_slo" {
  description = "Monitoring resource name for go-gateway availability SLO."
  value       = module.gateway_slos.availability_slo_name
}

output "gateway_latency_slo" {
  description = "Monitoring resource name for go-gateway latency SLO."
  value       = module.gateway_slos.latency_slo_name
}

output "gateway_redis_url" {
  description = "REDIS_URL for go-gateway (null when gateway Redis is disabled)."
  value       = var.enable_gateway_redis ? module.gateway_redis[0].redis_url : null
  sensitive   = true
}
