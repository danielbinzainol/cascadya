###############################################################
# MODULE : broker
# OBJECTIF : héberger broker sur le réseau privé
###############################################################

terraform {
  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = ">= 2.30.0"
    }
  }
}

# -------------------------------------------------------------
# ip publique pour le broker (mqtts 8883)
# -------------------------------------------------------------
resource "scaleway_instance_ip" "broker_ip" {}

# -------------------------------------------------------------
# instance broker
# -------------------------------------------------------------
resource "scaleway_instance_server" "broker" {
  name  = var.name
  type  = var.instance_type
  image = "ubuntu_jammy"
  zone  = var.zone

  ip_id             = scaleway_instance_ip.broker_ip.id
  security_group_id = var.security_group_id

  user_data = var.user_data

  tags = ["terraform", "broker", "vernemq"]
}


# -------------------------------------------------------------
# interface réseau privée
# -------------------------------------------------------------
resource "scaleway_instance_private_nic" "broker_private" {
  server_id          = scaleway_instance_server.broker.id
  private_network_id = var.private_network_id
  zone               = var.zone
}
