output "vpc_id" {
  value = scaleway_vpc.this.id
}

output "private_network_ids" {
  value = { for k, v in scaleway_vpc_private_network.pn : k => v.id }
}

output "security_group_id" {
  value = scaleway_instance_security_group.this.id
}