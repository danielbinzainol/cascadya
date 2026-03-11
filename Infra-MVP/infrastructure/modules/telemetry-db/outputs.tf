output "db_host" {
  value       = scaleway_rdb_instance.telemetry_instance.private_network[0].ip
  description = "Private IP of the telemetry DB"
}

output "db_port" {
  value       = scaleway_rdb_instance.telemetry_instance.private_network[0].port
  description = "Port of the telemetry DB"
}

output "db_name" {
  value       = scaleway_rdb_database.telemetry_db.name
}

output "db_user" {
  value       = scaleway_rdb_instance.telemetry_instance.user_name
}