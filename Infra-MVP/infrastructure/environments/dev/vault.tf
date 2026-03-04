###############################################################
# Connexion à Vault et récupération des secrets Scaleway
###############################################################

provider "vault" {
  address = "https://secrets.cascadya.com"

  auth_login {
    path = "auth/approle/login"
    parameters = {
      # CORRECTION: Use 'var' to accept value from the script
      role_id   = var.vault_role_id
      secret_id = var.vault_secret_id
    }
  }
}

###############################################################
# Lecture du secret Scaleway depuis Vault (KV v2)
###############################################################
data "vault_kv_secret_v2" "scw" {
  mount = "secret"
  name  = "scaleway"
}

###############################################################
# Extraction des variables
###############################################################
locals {
  scw_access_key = data.vault_kv_secret_v2.scw.data["access_key"]
  scw_secret_key = data.vault_kv_secret_v2.scw.data["secret_key"]
  scw_project_id = data.vault_kv_secret_v2.scw.data["project_id"]
  scw_region     = data.vault_kv_secret_v2.scw.data["region"]
  scw_zone       = data.vault_kv_secret_v2.scw.data["zone"]
}

###############################################################
# Configuration du provider Scaleway
###############################################################

provider "scaleway" {
  alias      = "from_vault"
  access_key = local.scw_access_key
  secret_key = local.scw_secret_key
  project_id = local.scw_project_id
  region     = local.scw_region
  zone       = local.scw_zone
}

provider "scaleway" {
  access_key = local.scw_access_key
  secret_key = local.scw_secret_key
  project_id = local.scw_project_id
  region     = local.scw_region
  zone       = local.scw_zone
}