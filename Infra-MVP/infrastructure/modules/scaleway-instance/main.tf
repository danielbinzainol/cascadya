###############################################################
# MODULE : scaleway-instance 
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
# Création d'une IP publique
# -------------------------------------------------------------
resource "scaleway_instance_ip" "server_ip" {
  zone = var.zone
}

# -------------------------------------------------------------
# Création du volume supplémentaire
# -------------------------------------------------------------
# Nouveau système Scaleway Block Storage
resource "scaleway_block_volume" "data_volume" {
  name       = "${var.instance_name}-data"
  size_in_gb = var.data_volume_size_gb
  iops       = 5000
  zone       = var.zone
}


# -------------------------------------------------------------
# Création du serveur Scaleway avec volume et SSH
# -------------------------------------------------------------
resource "scaleway_instance_server" "server" {
  name  = var.instance_name
  type  = var.instance_type
  image = var.image
  zone  = var.zone
  user_data = var.user_data

  ip_id = scaleway_instance_ip.server_ip.id
  
additional_volume_ids = [scaleway_block_volume.data_volume.id]
security_group_id = var.security_group_id
dynamic "private_network" {
    for_each = var.private_network_id != null ? [var.private_network_id] : []
    content {
      pn_id = private_network.value
    }
  }

  tags = ["terraform", var.instance_type]
}
