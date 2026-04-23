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
# Creation d'une IP publique
# -------------------------------------------------------------
resource "scaleway_instance_ip" "server_ip" {
  zone = var.zone
}

# -------------------------------------------------------------
# Creation du volume supplementaire
# -------------------------------------------------------------
resource "scaleway_block_volume" "data_volume" {
  name       = "${var.instance_name}-data"
  size_in_gb = var.data_volume_size_gb
  iops       = 5000
  zone       = var.zone
}

# -------------------------------------------------------------
# Creation du serveur Scaleway avec volume et SSH
# -------------------------------------------------------------
resource "scaleway_instance_server" "server" {
  name      = var.instance_name
  type      = var.instance_type
  image     = var.image
  zone      = var.zone
  user_data = var.user_data

  ip_id = scaleway_instance_ip.server_ip.id

  dynamic "root_volume" {
    for_each = var.root_volume_size_gb != null ? [var.root_volume_size_gb] : []
    content {
      size_in_gb = root_volume.value
    }
  }

  additional_volume_ids = [scaleway_block_volume.data_volume.id]
  security_group_id     = var.security_group_id
  protected             = var.protected

  dynamic "private_network" {
    for_each = var.private_network_id != null ? [var.private_network_id] : []
    content {
      pn_id = private_network.value
    }
  }

  tags = var.tags != null ? var.tags : ["terraform", var.instance_type]

  lifecycle {
    ignore_changes = [user_data]
  }
}
