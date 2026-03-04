###############################################################
# Variables injectées par le script run_terraform.sh
###############################################################

variable "vault_role_id" {
  type        = string
  description = "ID du rôle Vault (injecté automatiquement par le script)"
  sensitive   = true
}

variable "vault_secret_id" {
  type        = string
  description = "Secret ID Vault (injecté automatiquement par le script)"
  sensitive   = true
}

###############################################################
# Clés SSH par défaut pour toutes les VMs
###############################################################

locals {
  # Liste des clés publiques autorisées
  default_ssh_keys = [
    file(pathexpand("~/.ssh/publickeyopenssh.pub")),
    file(pathexpand("~/.ssh/Luc.pub")),
    file(pathexpand("~/.ssh/id_ed25519.pub"))
  ]

  # Bloc cloud-init commun à toutes les machines
  user_data_common = {
    "cloud-init" = <<-EOF
      #cloud-config
      ssh_authorized_keys:
%{ for key in local.default_ssh_keys ~}
        - ${key}
%{ endfor ~}
    EOF
  }
}