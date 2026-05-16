# Cross-region PostgreSQL read replica.
#
# The primary instance must have binary logging / WAL replication enabled.
# The replica inherits the database version and storage settings from the primary.
#
# Usage: services that are read-heavy (reporting-service, search-service) can
# point their DATABASE_REPLICA_URL at the replica's connection string, keeping
# write traffic on the primary and spreading read load cross-region.
resource "google_sql_database_instance" "replica" {
  name                 = var.replica_name
  database_version     = "POSTGRES_16"
  region               = var.replica_region
  master_instance_name = "${var.project_id}:${var.primary_instance_name}"
  deletion_protection  = var.deletion_protection

  # replica_configuration is optional for Postgres cross-region replicas.
  # Omit failover_target (Postgres does not support legacy failover replicas).

  settings {
    tier              = var.tier
    availability_type = "ZONAL"

    backup_configuration {
      # Read replicas do not need independent backups — the primary's
      # PITR covers both the primary and replica data.
      enabled = false
    }

    ip_configuration {
      # Public IP enabled so Cloud Run services can reach the replica via
      # Cloud SQL Auth Proxy or direct SSL connection.
      ipv4_enabled = true
    }

    # Disable insights on the replica to reduce cost; enable on primary only.
    insights_config {
      query_insights_enabled = false
    }
  }
}
