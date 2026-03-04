###############################################################
# MODULE NETWORK (VPC + Private Networks + Security Group)
###############################################################

terraform {
  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = ">= 2.30.0"
    }
  }
}

# 1) Création du VPC principal
resource "scaleway_vpc" "this" {
  name = var.vpc_name
}

# 2) Réseaux privés
resource "scaleway_vpc_private_network" "pn" {
  for_each   = var.subnets
  name       = "${var.name_prefix}-${each.key}"
  region = var.region
  vpc_id     = scaleway_vpc.this.id
  project_id = var.project_id

  ipv4_subnet {
    subnet = each.value
  }
}
# 3) Security Group (pare-feu)
resource "scaleway_instance_security_group" "this" {
  name        = var.sg_name
  description = "Deny-all inbound; SSH/WireGuard autorisés depuis mgmt_cidrs"
  zone        = var.zone

  inbound_default_policy  = "drop"
  outbound_default_policy = var.sg_outbound_policy

  # SSH 22/TCP
  dynamic "inbound_rule" {
    for_each = var.mgmt_cidrs
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 22
      ip_range = inbound_rule.value
    }
  }

  # WireGuard 51820/UDP
  dynamic "inbound_rule" {
    for_each = var.mgmt_cidrs
    content {
      action   = "accept"
      protocol = "UDP"
      port     = 51820
      ip_range = inbound_rule.value
    }
  }

  # Règles additionnelles — version blindée (aucune erreur possible)
  dynamic "inbound_rule" {
    for_each = try(var.extra_inbound_rules, [])
    content {
      action   = lookup(inbound_rule.value, "action", "accept")
      protocol = lookup(inbound_rule.value, "protocol", "TCP")
      port     = lookup(inbound_rule.value, "port", 0)
      ip_range = lookup(inbound_rule.value, "ip_range", "0.0.0.0/0")
    }
  }
}

# ---------------------
# OUTPUTS
# ---------------------

output "vpc_id" {
  value = scaleway_vpc.this.id
}

output "private_network_ids" {
  value = { for k, v in scaleway_vpc_private_network.pn : k => v.id }
}

output "security_group_id" {
  value = scaleway_instance_security_group.this.id
}
