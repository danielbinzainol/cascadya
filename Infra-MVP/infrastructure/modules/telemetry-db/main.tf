terraform {
  required_providers {
    scaleway = {
      source = "scaleway/scaleway"
    }
  }
}

# Création de l'instance PostgreSQL sur Scaleway
resource "scaleway_rdb_instance" "telemetry_instance" {
  name           = "telemetry-db-cluster"
  node_type      = var.node_type
  engine         = "PostgreSQL-15"
  is_ha_cluster  = false
  disable_backup = false
  user_name      = var.db_user
  password       = var.db_password
  region         = var.region

  # On la place dans ton subnet privé "data"
  private_network {
    pn_id = var.private_network_id
    enable_ipam = true
  }
}

# Création de la base de données spécifique
resource "scaleway_rdb_database" "telemetry_db" {
  instance_id = scaleway_rdb_instance.telemetry_instance.id
  name        = var.db_name
  region      = var.region
}

resource "scaleway_rdb_privilege" "telemetry_privilege" {
  instance_id   = scaleway_rdb_instance.telemetry_instance.id
  user_name     = var.db_user
  database_name = scaleway_rdb_database.telemetry_db.name
  permission    = "all"
}