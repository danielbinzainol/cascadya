resource "scaleway_instance_security_group" "wazuh" {
  name        = "sg-wazuh"
  description = "wazuh manager security group"
  zone        = local.scw_zone

  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_wazuh_admin_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 22
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_wazuh_temporary_ssh_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 22
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_wazuh_admin_cidrs)
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

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_wazuh_ipc_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 1514
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_wazuh_ipc_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 1515
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_wazuh_ipc_public_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 1514
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_wazuh_ipc_public_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 1515
      ip_range = inbound_rule.value
    }
  }

  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 55000
    ip_range = format("%s/32", module.control_panel.ip_address)
  }
}
