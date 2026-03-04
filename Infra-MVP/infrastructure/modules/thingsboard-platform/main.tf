###############################################################
# MODULE : thingsboard-platform
# OBJECTIF : Héberger la VM ThingsBoard sur le même réseau privé
# que Vault et Docmost, avec le même groupe de sécurité
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
# Attribution d'une IP publique à la VM ThingsBoard
# -------------------------------------------------------------
resource "scaleway_instance_ip" "thingsboard_ip" {}

# -------------------------------------------------------------
# Volume de données (pour Docker/ThingsBoard)
# -------------------------------------------------------------
resource "scaleway_block_volume" "thingsboard_data" {
  name       = "thingsboard-data"
  size_in_gb = 20
  iops       = 5000
  zone       = var.zone
}

# -------------------------------------------------------------
# Instance ThingsBoard (Ubuntu 22.04 )
# -------------------------------------------------------------
resource "scaleway_instance_server" "thingsboard_vm" {
  name              = "thingsboard-DEV1-S"
  type              = var.instance_type
  image             = "ubuntu_jammy"
  zone              = var.zone

  ip_id             = scaleway_instance_ip.thingsboard_ip.id
  security_group_id = var.security_group_id


  additional_volume_ids = [scaleway_block_volume.thingsboard_data.id]

  user_data = var.user_data


  tags = ["terraform", "thingsboard", "staging"]
}
# Interface réseau privée pour ThingsBoard
resource "scaleway_instance_private_nic" "thingsboard_private" {
  server_id          = scaleway_instance_server.thingsboard_vm.id
  private_network_id = var.private_network_id
  zone               = var.zone
}
