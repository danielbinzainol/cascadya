# broker-sg.tf
resource "scaleway_instance_security_group" "broker" {
  name        = "sg-broker"
  description = "mqtt broker security group"
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