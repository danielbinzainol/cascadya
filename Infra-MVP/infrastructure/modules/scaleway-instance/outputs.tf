output "ip_address" {
  description = "Adresse IP publique de l'instance"
  value       = scaleway_instance_ip.server_ip.address
}

output "instance_id" {
  description = "ID de l'instance Scaleway"
  value       = scaleway_instance_server.server.id
}
