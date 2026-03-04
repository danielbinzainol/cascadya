###############################################################
# MODULE : thingsboard-db
# OBJECTIF : Déployer une base PostgreSQL managée sur Scaleway
# avec le type DB-DEV-M et une connexion via le réseau privé
###############################################################

terraform {
  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = ">= 2.30.0"
    }
  }
}

resource "scaleway_rdb_instance" "thingsboard_db" {
  name              = "thingsboard-db"
  node_type         = var.node_type            # ex: "DB-DEV-M"
  engine            = "PostgreSQL-14"
  is_ha_cluster     = false
  disable_backup    = false
  user_name         = var.db_user
  password          = var.db_password
  region            = var.region

  private_network {
    pn_id       = var.private_network_id
    enable_ipam = true    # ← obligatoire pour activer IPAM automatique
  }

  tags = ["terraform", "thingsboard", "database"]
}

resource "scaleway_rdb_database" "thingsboard_database" {
  instance_id = scaleway_rdb_instance.thingsboard_db.id
  name        = var.db_name
}
