###############################################################
# Sorties du module ThingsBoard Platform (corrigé)
###############################################################

# IP publique
output "thingsboard_public_ip" {
  description = "Adresse IP publique de la VM ThingsBoard"
  value       = scaleway_instance_ip.thingsboard_ip.address
}

# IP privée (avec vérification pour éviter les erreurs)
output "thingsboard_private_ip" {
  description = "Adresse IP privée de la VM ThingsBoard"
  value = (
    length(scaleway_instance_server.thingsboard_vm.private_ips) > 0
    ? scaleway_instance_server.thingsboard_vm.private_ips[0].address
    : "no-private-ip"
  )
}


# ID de la machine virtuelle
output "thingsboard_instance_id" {
  description = "ID de la VM ThingsBoard"
  value       = scaleway_instance_server.thingsboard_vm.id
}
