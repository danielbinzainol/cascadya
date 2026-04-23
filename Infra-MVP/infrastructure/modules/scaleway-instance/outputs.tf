output "ip_address" {
  description = "Adresse IP publique de l'instance"
  value       = scaleway_instance_ip.server_ip.address
}

output "instance_id" {
  description = "ID de l'instance Scaleway"
  value       = scaleway_instance_server.server.id
}

output "private_ip_address" {
  description = "Adresse IPv4 privee principale de l'instance si presente"
  value = try(
    [for ip in scaleway_instance_server.server.private_ips : ip.address if can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}$", ip.address))][0],
    try(scaleway_instance_server.server.private_ips[0].address, null)
  )
}

output "private_ipv4_address" {
  description = "Adresse IPv4 privee principale de l'instance si presente"
  value = try(
    [for ip in scaleway_instance_server.server.private_ips : ip.address if can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}$", ip.address))][0],
    null
  )
}

output "private_ipv6_address" {
  description = "Adresse IPv6 privee principale de l'instance si presente"
  value = try(
    [for ip in scaleway_instance_server.server.private_ips : ip.address if can(regex(":", ip.address))][0],
    null
  )
}
