###############################################################
# Variables injectees par le script run_terraform.sh
###############################################################

variable "vault_role_id" {
  type        = string
  description = "ID du role Vault (injecte automatiquement par le script)"
  sensitive   = true
}

variable "vault_secret_id" {
  type        = string
  description = "Secret ID Vault (injecte automatiquement par le script)"
  sensitive   = true
}

###############################################################
# Cles SSH par defaut et CIDR reseau partages
###############################################################

locals {
  wireguard_cidr = "10.8.0.0/24"

  # CIDR(s) d'administration autorises en acces direct
  mgmt_cidrs = [
    "195.68.106.70/32"
  ]

  allowed_control_panel_cidrs = distinct(concat(
    [local.wireguard_cidr],
    local.mgmt_cidrs,
  ))

  allowed_monitoring_admin_cidrs = distinct(concat(
    [local.wireguard_cidr],
    local.mgmt_cidrs,
  ))

  # Autorise le scrape node_exporter depuis la VM monitoring uniquement.
  # Mettre a jour cette valeur si l'IP privee de monitoring change un jour.
  allowed_monitoring_vm_scrape_cidrs = [
    "10.42.1.4/32",
  ]

  # Ouverture SSH temporaire sur monitoring pour depannage / onboarding.
  # A refermer des que les IPs admin dediees sont connues ou que l'acces
  # via WireGuard suffit.
  allowed_monitoring_temporary_ssh_cidrs = [
    "0.0.0.0/0",
  ]

  allowed_loki_internal_cidrs = distinct([
    "10.42.0.0/16",
    local.wireguard_cidr,
  ])

  # Mimir recoit les metriques poussees par Alloy depuis les IPC.
  # Hypothese cible: les IPC passent d'abord par l'overlay prive (WireGuard).
  allowed_mimir_ingest_cidrs = [
    local.wireguard_cidr,
  ]

  # Si certains IPC ne passent pas encore par WireGuard, ajouter ici
  # explicitement leur IP publique source en /32, de facon temporaire.
  allowed_mimir_public_ipc_cidrs = []

  # Wazuh: acces admin restreint au VPN et aux IPs d'administration explicites.
  allowed_wazuh_admin_cidrs = distinct(concat(
    [local.wireguard_cidr],
    local.mgmt_cidrs,
  ))

  # Ouverture SSH temporaire sur Wazuh pour depannage / onboarding.
  # A refermer des que les IPs admin dediees sont connues ou que l'acces
  # via WireGuard suffit.
  allowed_wazuh_temporary_ssh_cidrs = [
    "0.0.0.0/0",
  ]

  # Hypothese Dev1: les IPC rejoignent Wazuh via l'overlay WireGuard existant.
  # Etendre cette liste si certains IPC doivent enroler hors overlay prive.
  allowed_wazuh_ipc_cidrs = [
    local.wireguard_cidr,
  ]

  # Par defaut, aucun fallback public n'est expose pour les ports Wazuh agent.
  # Si un diagnostic exceptionnel l'impose, ajouter explicitement ici un /32
  # public temporaire puis le retirer apres usage.
  allowed_wazuh_ipc_public_cidrs = []

  # Liste des cles publiques autorisees
  default_ssh_keys = [
    file(pathexpand("~/.ssh/publickeyopenssh.pub")),
    file(pathexpand("~/.ssh/Luc.pub")),
    file(pathexpand("~/.ssh/id_ed25519.pub")),
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPOfIr+wgRdN5sEOW0R4ZtdZqZolDPDMLBjdJM6c7g5g loris@cascadya"
  ]

  # Bloc cloud-init commun a toutes les machines
  user_data_common = {
    "cloud-init" = <<-EOF
      #cloud-config
      ssh_authorized_keys:
%{ for key in local.default_ssh_keys ~}
        - ${key}
%{ endfor ~}
    EOF
  }

  user_data_wazuh = {
    "cloud-init" = <<-EOF
      #cloud-config
      hostname: wazuh-dev1-s
      preserve_hostname: false
      ssh_authorized_keys:
%{ for key in local.default_ssh_keys ~}
        - ${key}
%{ endfor ~}
    EOF
  }
}
