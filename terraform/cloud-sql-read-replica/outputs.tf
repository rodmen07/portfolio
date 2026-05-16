output "instance_name" {
  description = "Name of the read replica Cloud SQL instance."
  value       = google_sql_database_instance.replica.name
}

output "connection_name" {
  description = "Cloud SQL connection name for use with Cloud SQL Auth Proxy (project:region:instance)."
  value       = google_sql_database_instance.replica.connection_name
}

output "public_ip" {
  description = "Public IPv4 address of the read replica."
  value       = google_sql_database_instance.replica.public_ip_address
}

output "database_replica_url_template" {
  description = "Template DATABASE_REPLICA_URL — substitute <user> and <password> before use."
  sensitive   = true
  value       = "postgresql://<user>:<password>@${google_sql_database_instance.replica.public_ip_address}:5432/<dbname>?sslmode=require"
}
