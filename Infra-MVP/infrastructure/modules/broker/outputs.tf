output "public_ip" {
  value = scaleway_instance_ip.broker_ip.address
}

output "server_id" {
  value = scaleway_instance_server.broker.id
}
