###############################################################
# OUTPUTS - PostgreSQL (avec private_network)
###############################################################

output "thingsboard_db_host" {
  description = "Adresse IP privée de la base PostgreSQL"
  value       = try(scaleway_rdb_instance.thingsboard_db.private_network[0].ip, "")
}

output "thingsboard_db_port" {
  description = "Port d'accès PostgreSQL"
  value       = try(scaleway_rdb_instance.thingsboard_db.private_network[0].port, 5432)
}

output "thingsboard_db_name" {
  description = "Nom de la base ThingsBoard"
  value       = var.db_name
}

output "thingsboard_db_user" {
  description = "Nom de l'utilisateur PostgreSQL"
  value       = var.db_user
}
