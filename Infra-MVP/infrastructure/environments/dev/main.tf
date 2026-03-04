# -------------------------------------------------------------
# Module Réseau (VPC + Private Networks + Security Group)
# -------------------------------------------------------------
module "network" {
  source     = "../../modules/network"
  project_id = local.scw_project_id
  region     = local.scw_region
  zone       = local.scw_zone

  vpc_name    = "vpc-main"
  name_prefix = "corp"

  # Mets ici ton IP publique réelle (l'adresse ip de ton PC)
  mgmt_cidrs = ["195.68.106.70/32"]

  subnets = {
    public = "10.42.0.0/24"
    app    = "10.42.1.0/24"
    data   = "10.42.2.0/24"
  }


extra_inbound_rules = [
  # Allow ALL private network traffic (VPN + VM-to-VM)
  {
    id       = "private-tcp-10-42"
    action   = "accept"
    protocol = "TCP"
    port     = 0
    ip_range = "10.42.0.0/16"
  },
  {
    id       = "private-udp-10-42"
    action   = "accept"
    protocol = "UDP"
    port     = 0
    ip_range = "10.42.0.0/16"
  },
  {
    id       = "private-icmp-10-42"
    action   = "accept"
    protocol = "ICMP"
    port     = 0
    ip_range = "10.42.0.0/16"
  },

  {
    id       = "vault-8200"
    action   = "accept"
    protocol = "TCP"
    port     = 8200
    ip_range = "0.0.0.0/0"
  },

  {
    id       = "ssh-22"
    action   = "accept"
    protocol = "TCP"
    port     = 22
    ip_range = "0.0.0.0/0"
  },



  # Existing web rules
  {
    id       = "http-80"
    action   = "accept"
    protocol = "TCP"
    port     = 80
    ip_range = "0.0.0.0/0"
  },
  {
    id       = "https-443"
    action   = "accept"
    protocol = "TCP"
    port     = 443
    ip_range = "0.0.0.0/0"
  },
  {
    id       = "smtp-587"
    action   = "accept"
    protocol = "TCP"
    port     = 587
    ip_range = "0.0.0.0/0"
  },

  # VPN network rules
  {
    id       = "private-tcp-10-8"
    action   = "accept"
    protocol = "TCP"
    port     = 0
    ip_range = "10.8.0.0/24"
  },
  {
    id       = "private-udp-10-8"
    action   = "accept"
    protocol = "UDP"
    port     = 0
    ip_range = "10.8.0.0/24"
  },
  {
    id       = "private-icmp-10-8"
    action   = "accept"
    protocol = "ICMP"
    port     = 0
    ip_range = "10.8.0.0/24"
  },

  # Public service ports (MQTT + HTTP)
  {
    id       = "web-8080"
    action   = "accept"
    protocol = "TCP"
    port     = 8080
    ip_range = "0.0.0.0/0"
  },
  {
    id       = "mqtt-8883"
    action   = "accept"
    protocol = "TCP"
    port     = 8883
    ip_range = "0.0.0.0/0"
  },
]





}

###############################################################
# FICHIER : main.tf (corrigé AMS1 + Vault)
###############################################################

terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    bucket                      = "terraform-state-cascadya"
    key                         = "terraform/terraform.tfstate"
    region                      = "nl-ams"
    endpoints                   = { s3 = "https://s3.nl-ams.scw.cloud" }
    use_path_style              = true
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true
  }

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = ">= 2.30.0"
    }
  }
}

# -------------------------------------------------------------
# Variables et Provider Scaleway
# -------------------------------------------------------------
#variable "scw_access_key" { sensitive = true }
#variable "scw_secret_key" { sensitive = true }
#variable "scw_project_id" {}
#variable "scw_region" { default = "nl-ams" }
#variable "scw_zone"   { default = "nl-ams-1" }


# -------------------------------------------------------------
# Disques de données
# -------------------------------------------------------------

resource "scaleway_block_volume" "vault_data" {
  name       = "disque-donnees-vault"
  size_in_gb = 10
  iops       = 5000
}

# -------------------------------------------------------------
# IP publiques
# -------------------------------------------------------------
resource "scaleway_instance_ip" "vault_ip" {}

# -------------------------------------------------------------
# Instance Vault
# -------------------------------------------------------------
resource "scaleway_instance_server" "vault" {
  name              = "vault-DEV1-S"
  type              = "DEV1-S"
  image             = "ubuntu_jammy"
  security_group_id = module.network.security_group_id
  ip_id             = scaleway_instance_ip.vault_ip.id

  additional_volume_ids = [scaleway_block_volume.vault_data.id]
  user_data = local.user_data_common
  tags = ["terraform", "DEV1-S", "ansible", "vault"]
}

# Interface réseau privée Vault
resource "scaleway_instance_private_nic" "vault_private" {
  server_id          = scaleway_instance_server.vault.id
  private_network_id = module.network.private_network_ids["data"]
  zone               = local.scw_zone

}

# -------------------------------------------------------------
# Instance Docmost (via module)
# -------------------------------------------------------------
module "docmost" {
  source = "../../modules/scaleway-instance"
  providers = {
    scaleway = scaleway.from_vault
  }
  instance_name       = "docmost-DEV1-S"
  instance_type       = "DEV1-S"
  image               = "ubuntu_jammy"
  zone                = "nl-ams-1"
  data_volume_size_gb = 20
  security_group_id   = module.network.security_group_id
  private_network_id  = module.network.private_network_ids["app"]
  user_data           = local.user_data_common

}
# -------------------------------------------------------------
# Module ThingsBoard Platform
# -------------------------------------------------------------
module "thingsboard_platform" {
  source = "../../modules/thingsboard-platform"

  instance_type      = "DEV1-S"
  zone               = local.scw_zone
  private_network_id = module.network.private_network_ids["app"]
  security_group_id  = module.network.security_group_id
  user_data          = local.user_data_common

}
# -------------------------------------------------------------
# Module ThingsBoard Database (DB-DEV-M)
# -------------------------------------------------------------
module "thingsboard_db" {
  source             = "../../modules/thingsboard-db"
  region             = local.scw_region
  private_network_id = module.network.private_network_ids["data"]

  db_user     = "thingsboard"
  db_password = "ChangeMe123!"
  db_name     = "thingsboard"
  node_type   = "DB-DEV-M"
}
# -------------------------------------------------------------
# Module WireGuard (basé sur scaleway-instance)
# -------------------------------------------------------------
module "wireguard" {
  source = "../../modules/scaleway-instance"

  instance_name       = "wireguard-DEV1-S"
  instance_type       = "DEV1-S"
  image               = "ubuntu_jammy"
  zone                = local.scw_zone
  security_group_id   = module.network.security_group_id
  private_network_id  = module.network.private_network_ids["app"]
  data_volume_size_gb = 10
  user_data           = local.user_data_common
}
# -------------------------------------------------------------
# Module Monitoring (Prometheus + Grafana + Loki)
# -------------------------------------------------------------
module "monitoring" {
  source = "../../modules/scaleway-instance"

  instance_name       = "monitoring-DEV1-S"
  instance_type       = "DEV1-S"
  image               = "ubuntu_jammy"
  zone                = local.scw_zone

  security_group_id   = module.network.security_group_id
  private_network_id  = module.network.private_network_ids["app"]

  data_volume_size_gb = 10   # si tu veux stocker Loki localement
  user_data           = local.user_data_common

}
# -------------------------------------------------------------
# Module Broker (VM dédiée + VerneMQ)
# -------------------------------------------------------------
module "broker" {
  source = "../../modules/scaleway-instance"

  instance_name       = "vm-broker"
  instance_type       = "DEV1-S"
  image               = "ubuntu_jammy"
  zone                = local.scw_zone

  private_network_id  = module.network.private_network_ids["app"]
  security_group_id   = scaleway_instance_security_group.broker.id
  user_data           = local.user_data_common

}


# -------------------------------------------------------------
# Sorties
# -------------------------------------------------------------

output "vault_ipv4" {
  description = "Adresse IPv4 publique du serveur Vault"
  value       = scaleway_instance_ip.vault_ip.address
}

# -------------------------------------------------------------
# Sorties de la base de données ThingsBoard
# -------------------------------------------------------------
output "thingsboard_db_host" {
  value       = module.thingsboard_db.thingsboard_db_host
  description = "Adresse IP interne de la base PostgreSQL ThingsBoard"
}

output "thingsboard_db_port" {
  value       = module.thingsboard_db.thingsboard_db_port
  description = "Port d'accès à la base PostgreSQL"
}

output "thingsboard_db_name" {
  value       = module.thingsboard_db.thingsboard_db_name
  description = "Nom de la base PostgreSQL ThingsBoard"
}

output "thingsboard_db_user" {
  value       = module.thingsboard_db.thingsboard_db_user
  description = "Utilisateur de la base PostgreSQL"
}
output "wireguard_ipv4" {
  description = "Adresse IPv4 publique du serveur WireGuard"
  value       = module.wireguard.ip_address
}
output "monitoring_ipv4" {
  description = "Adresse IPv4 publique de la VM Monitoring"
  value       = module.monitoring.ip_address
}
