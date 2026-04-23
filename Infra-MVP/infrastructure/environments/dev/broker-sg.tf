# broker-sg.tf
resource "scaleway_instance_security_group" "broker" {
  name        = "sg-broker"
  description = "broker security group"
  zone        = local.scw_zone

  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  # On écrit TOUTES les règles directement ici
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 8883
    ip_range = "0.0.0.0/0"
  }
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 80
    ip_range = "0.0.0.0/0"
  }
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 443
    ip_range = "0.0.0.0/0"
  }
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 4222
    ip_range = "10.42.1.0/24"
  }
  # Monitoring/diagnostic NATS interne uniquement
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 8222
    ip_range = "10.42.1.0/24"
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
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 8443
    ip_range = "0.0.0.0/0"
  }
  # Control panel backend -> broker IPC/API path
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 9443
    ip_range = format("%s/32", module.control_panel.ip_address)
  }
  inbound_rule {
    action   = "accept"
    protocol = "UDP"
    port     = 51820
    ip_range = "0.0.0.0/0"
  }
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 8888
    ip_range = "10.8.0.0/24"
  }
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 22
    ip_range = "10.8.0.0/24"
  }
  inbound_rule {
    action   = "accept"
    protocol = "TCP"
    port     = 22
    ip_range = "0.0.0.0/0"
  }

}
# Remarque : Je n'ai PAS mis la ressource "scaleway_instance_security_group_rules" ici.
