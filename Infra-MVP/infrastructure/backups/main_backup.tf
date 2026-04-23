###############################################################
# FICHIER : main.tf (corrigé pour AMS1 + ajout Vault)
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
variable "scw_access_key" { sensitive = true }
variable "scw_secret_key" { sensitive = true }
variable "scw_project_id" {}
variable "scw_region" { default = "nl-ams" }
variable "scw_zone"   { default = "nl-ams-1" }

provider "scaleway" {
  access_key = var.scw_access_key
  secret_key = var.scw_secret_key
  project_id = var.scw_project_id
  region     = var.scw_region
  zone       = var.scw_zone
}

# -------------------------------------------------------------
# Groupe de sécurité
# -------------------------------------------------------------
resource "scaleway_instance_security_group" "sg" {
  name                    = "ansible-sg"
  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  inbound_rule {
    action   = "accept"
    port     = 22
    protocol = "TCP"
    ip_range = "0.0.0.0/0"
  }

  # (Optionnel) Port Vault (8200)
  inbound_rule {
    action   = "accept"
    port     = 8200
    protocol = "TCP"
    ip_range = "0.0.0.0/0"
  }
}

# -------------------------------------------------------------
# Disque de données persistant de 20 Go
# -------------------------------------------------------------
resource "scaleway_block_volume" "appflowy_data" {
  name       = "disque-donnees-appflowy"
  size_in_gb = 20
  iops       = 5000
}

# -------------------------------------------------------------
# Adresse IPv4 publique pour AppFlowy
# -------------------------------------------------------------
resource "scaleway_instance_ip" "ipv4" {}

# -------------------------------------------------------------
# Instance AppFlowy
# -------------------------------------------------------------
resource "scaleway_instance_server" "appflowy" {
  name              = "appflowy-DEV1-M"
  type              = "DEV1-M"
  image             = "ubuntu_jammy"
  security_group_id = scaleway_instance_security_group.sg.id
  ip_id             = scaleway_instance_ip.ipv4.id

  additional_volume_ids = [scaleway_block_volume.appflowy_data.id]

  user_data = {
    "cloud-init" = <<-EOF
      #cloud-config
      ssh_authorized_keys:
        - ${file(pathexpand("~/.ssh/publickeyopenssh.pub"))}
    EOF
  }

  tags = ["terraform", "DEV1-M", "ansible", "target"]
}

# -------------------------------------------------------------
# Adresse IPv4 publique pour Vault
# -------------------------------------------------------------
resource "scaleway_instance_ip" "vault_ip" {}

# -------------------------------------------------------------
# Instance Vault
# -------------------------------------------------------------
resource "scaleway_instance_server" "vault" {
  name              = "vault-DEV1-S"
  type              = "DEV1-S"
  image             = "ubuntu_jammy"
  security_group_id = scaleway_instance_security_group.sg.id
  ip_id             = scaleway_instance_ip.vault_ip.id

  user_data = {
    "cloud-init" = <<-EOF
      #cloud-config
      ssh_authorized_keys:
        - ${file(pathexpand("~/.ssh/publickeyopenssh.pub"))}
    EOF
  }

  tags = ["terraform", "DEV1-S", "ansible", "vault"]
}

# -------------------------------------------------------------
# Sorties
# -------------------------------------------------------------
output "appflowy_ipv4" {
  description = "Adresse IPv4 publique du serveur AppFlowy"
  value       = scaleway_instance_ip.ipv4.address
}

output "vault_ipv4" {
  description = "Adresse IPv4 publique du serveur Vault"
  value       = scaleway_instance_ip.vault_ip.address
}
