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
  # SMTP sortant requis pour l'envoi via Brevo.
  sg_enable_default_security = false

  # Mets ici ton IP publique réelle (l'adresse ip de ton PC)
  mgmt_cidrs = local.mgmt_cidrs

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

  # Public service ports (HTTP)
  {
    id       = "web-8080"
    action   = "accept"
    protocol = "TCP"
    port     = 8080
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
  name                  = "vault-DEV1-S"
  type                  = "DEV1-S"
  image                 = "ubuntu_jammy"
  security_group_id     = module.network.security_group_id
  ip_id                 = scaleway_instance_ip.vault_ip.id

  additional_volume_ids = [scaleway_block_volume.vault_data.id]
  #user_data            = local.user_data_common
  tags                  = ["terraform", "DEV1-S", "ansible", "vault"]
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
# Module Control Panel (prototype Auth FastAPI)
# -------------------------------------------------------------
module "control_panel" {
  source = "../../modules/scaleway-instance"

  instance_name       = "control-panel-DEV1-S"
  instance_type       = "DEV1-S"
  image               = "ubuntu_jammy"
  zone                = local.scw_zone
  security_group_id   = scaleway_instance_security_group.control_panel.id
  private_network_id  = module.network.private_network_ids["app"]
  data_volume_size_gb = 20
  user_data           = local.user_data_common
}

# -------------------------------------------------------------
# Module C-Market (scripts Python / algorithmes)
# -------------------------------------------------------------
module "c_market" {
  source = "../../modules/scaleway-instance"

  instance_name       = "c-market-Dev1-S"
  instance_type       = "DEV1-S"
  image               = "ubuntu_jammy"
  zone                = local.scw_zone
  security_group_id   = module.network.security_group_id
  private_network_id  = module.network.private_network_ids["app"]
  data_volume_size_gb = 20
  user_data           = local.user_data_common
  tags                = ["terraform", "dev1", "algorithms", "c-market"]
}

# -------------------------------------------------------------
# Module Wazuh Manager (single-node all-in-one Dev1)
# -------------------------------------------------------------
module "wazuh" {
  source = "../../modules/scaleway-instance"

  instance_name       = "wazuh-Dev1-S"
  instance_type       = "BASIC2-A4C-8G"
  image               = "ubuntu_jammy"
  zone                = local.scw_zone
  security_group_id   = scaleway_instance_security_group.wazuh.id
  private_network_id  = module.network.private_network_ids["app"]
  root_volume_size_gb = 80
  data_volume_size_gb = 50
  user_data           = local.user_data_wazuh
  protected           = true
  tags                = ["terraform", "dev1", "security", "wazuh"]
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
  security_group_id   = scaleway_instance_security_group.wireguard.id
  private_network_id  = module.network.private_network_ids["app"]
  data_volume_size_gb = 10
  #user_data           = local.user_data_common
}

# -------------------------------------------------------------
# Module Monitoring (Grafana + Loki + Mimir + Alloy)
# -------------------------------------------------------------
module "monitoring" {
  source = "../../modules/scaleway-instance"

  instance_name       = "monitoring-DEV1-S"
  instance_type       = "DEV1-M"
  image               = "ubuntu_jammy"
  zone                = local.scw_zone

  security_group_id   = scaleway_instance_security_group.monitoring.id
  private_network_id  = module.network.private_network_ids["app"]

  root_volume_size_gb = 20
  data_volume_size_gb = 30
  user_data           = local.user_data_common
  protected           = true
  tags                = ["terraform", "dev1", "monitoring", "grafana", "loki", "mimir", "alloy"]

}
# -------------------------------------------------------------
# Module Broker (NATS)
# -------------------------------------------------------------
module "broker" {
  source = "../../modules/scaleway-instance"

  instance_name       = "broker-DEV1-S"
  instance_type       = "DEV1-S"
  image               = "ubuntu_jammy"
  zone                = local.scw_zone

  private_network_id  = module.network.private_network_ids["app"]
  security_group_id   = scaleway_instance_security_group.broker.id
  # user_data           = local.user_data_common

}

# -------------------------------------------------------------
# Module Telemetry Database (Timescale / PostgreSQL)
# -------------------------------------------------------------
module "telemetry_db" {
  source             = "../../modules/telemetry-db"
  region             = local.scw_region
  private_network_id = module.network.private_network_ids["data"]

  db_user     = "cascadya"
  db_password = "C4sc4dy4_Louvre!!2025" # Change ceci par un mot de passe fort
  db_name     = "cascadya_telemetry"
  node_type   = "DB-DEV-S"
}

# -------------------------------------------------------------
# Sorties
# -------------------------------------------------------------

output "vault_ipv4" {
  description = "Adresse IPv4 publique du serveur Vault"
  value       = scaleway_instance_ip.vault_ip.address
}

output "wireguard_ipv4" {
  description = "Adresse IPv4 publique du serveur WireGuard"
  value       = module.wireguard.ip_address
}
output "wireguard_private_ip" {
  description = "Adresse IPv4 privee de la VM WireGuard sur le reseau applicatif"
  value       = module.wireguard.private_ipv4_address
}
output "control_panel_ipv4" {
  description = "Adresse IPv4 publique de la VM Control Panel"
  value       = module.control_panel.ip_address
}
output "control_panel_private_ip" {
  description = "Adresse IPv4 privee de la VM Control Panel sur le reseau applicatif"
  value       = module.control_panel.private_ipv4_address
}
output "docmost_private_ip" {
  description = "Adresse IPv4 privee de la VM Docmost sur le reseau applicatif"
  value       = module.docmost.private_ipv4_address
}
output "broker_ipv4" {
  description = "Adresse IPv4 publique de la VM broker"
  value       = module.broker.ip_address
}
output "broker_private_ip" {
  description = "Adresse IPv4 privee de la VM broker sur le reseau applicatif"
  value       = module.broker.private_ipv4_address
}
output "broker_private_ipv6" {
  description = "Adresse IPv6 privee de la VM broker sur le reseau applicatif"
  value       = module.broker.private_ipv6_address
}
output "c_market_ipv4" {
  description = "Adresse IPv4 publique de la VM c-market"
  value       = module.c_market.ip_address
}
output "c_market_private_ip" {
  description = "Adresse IPv4 privee de la VM c-market sur le reseau applicatif"
  value       = module.c_market.private_ipv4_address
}
output "wazuh_ipv4" {
  description = "Adresse IPv4 publique de la VM Wazuh"
  value       = module.wazuh.ip_address
}
output "wazuh_private_ip" {
  description = "Adresse IPv4 privee de la VM Wazuh sur le reseau applicatif"
  value       = module.wazuh.private_ipv4_address
}
output "monitoring_ipv4" {
  description = "Adresse IPv4 publique de la VM Monitoring"
  value       = module.monitoring.ip_address
}
output "monitoring_private_ip" {
  description = "Adresse IPv4 privee de la VM Monitoring sur le reseau applicatif"
  value       = module.monitoring.private_ipv4_address
}
output "mimir_bucket_name" {
  description = "Nom du bucket Object Storage dedie a Mimir"
  value       = nonsensitive(scaleway_object_bucket.mimir.name)
}
output "mimir_bucket_endpoint" {
  description = "Endpoint S3 du bucket Mimir"
  value       = nonsensitive(local.mimir_bucket_endpoint)
}
output "mimir_bucket_region" {
  description = "Region du bucket Mimir"
  value       = nonsensitive(local.scw_region)
}
output "vault_private_ip" {
  description = "Adresse IPv4 privee de la VM Vault"
  value = try(
    [for ip in scaleway_instance_server.vault.private_ips : ip.address if can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}$", ip.address))][0],
    null
  )
}
output "mimir_internal_url" {
  description = "URL interne recommandee pour joindre Mimir depuis le reseau prive"
  value       = "http://${module.monitoring.private_ipv4_address}:9009"
}
output "loki_internal_url" {
  description = "URL interne recommandee pour joindre Loki depuis le reseau prive"
  value       = "http://${module.monitoring.private_ipv4_address}:3100"
}

# -------------------------------------------------------------
# Sorties de la base de données Telemetry
# -------------------------------------------------------------
output "telemetry_db_host" {
  value       = module.telemetry_db.db_host
  description = "Adresse IP interne de la base PostgreSQL Telemetry"
}

output "telemetry_db_port" {
  value       = module.telemetry_db.db_port
}

output "telemetry_db_name" {
  value       = module.telemetry_db.db_name
}
