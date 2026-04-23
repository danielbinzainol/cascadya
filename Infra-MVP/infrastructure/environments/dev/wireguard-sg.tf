resource "scaleway_instance_security_group" "wireguard" {
  name        = "sg-wireguard"
  description = "wireguard gateway security group"
  zone        = local.scw_zone

  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  dynamic "inbound_rule" {
    for_each = toset(local.mgmt_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 22
      ip_range = inbound_rule.value
    }
  }

  # Preserve the current direct SSH access behavior while moving off the shared SG.
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 22
    ip_range = "0.0.0.0/0"
  }

  # wg0 public endpoint for human/admin peers.
  inbound_rule {
    action   = "accept"
    protocol = "UDP"
    port     = 51820
    ip_range = "0.0.0.0/0"
  }

  # wg1 public endpoint for Teltonika edge routers.
  inbound_rule {
    action   = "accept"
    protocol = "UDP"
    port     = 51821
    ip_range = "0.0.0.0/0"
  }

  # Preserve private VPC reachability to the WireGuard router over its private NIC.
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 0
    ip_range = "10.42.0.0/16"
  }

  inbound_rule {
    action   = "accept"
    protocol = "UDP"
    port     = 0
    ip_range = "10.42.0.0/16"
  }

  inbound_rule {
    action   = "accept"
    protocol = "ICMP"
    port     = 0
    ip_range = "10.42.0.0/16"
  }
}
