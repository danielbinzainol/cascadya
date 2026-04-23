resource "scaleway_instance_security_group" "monitoring" {
  name                     = "sg-monitoring"
  description              = "monitoring stack security group (grafana/loki/mimir/alloy)"
  zone                     = local.scw_zone
  enable_default_security  = false
  inbound_default_policy   = "drop"
  outbound_default_policy  = "accept"
  stateful                 = true

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_monitoring_temporary_ssh_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 22
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_monitoring_admin_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 22
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_monitoring_admin_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 3000
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_loki_internal_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 3100
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_mimir_ingest_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 9009
      ip_range = inbound_rule.value
    }
  }

  dynamic "inbound_rule" {
    for_each = toset(local.allowed_mimir_public_ipc_cidrs)
    content {
      action   = "accept"
      protocol = "TCP"
      port     = 9009
      ip_range = inbound_rule.value
    }
  }
}
