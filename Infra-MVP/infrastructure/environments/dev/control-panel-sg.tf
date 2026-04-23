resource "scaleway_instance_security_group" "control_panel" {
  name        = "sg-control-panel"
  description = "control panel traefik security group"
  zone        = local.scw_zone

  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  # Temporary emergency SSH access. Restrict this again after troubleshooting.
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 22
    ip_range = "0.0.0.0/0"
  }

  # Point d'entree web unique via Traefik
  dynamic "inbound_rule" {
    for_each = toset(local.allowed_control_panel_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 443
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_monitoring_vm_scrape_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 9100
      ip_range = inbound_rule.value
    }
  }
}
