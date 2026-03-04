#!/bin/bash
# ==========================================================
# Script : run_terraform.sh
# Objectif : Lancer Terraform de manière sécurisée (Vault ou Manuel)
# ==========================================================

set -e  # Stop en cas d'erreur

# === Configuration ===
export VAULT_ADDR="https://secrets.cascadya.com"
export VAULT_SKIP_VERIFY=true  # utile si certificat auto-signé

# === Logique de Sélection des Credentials ===
if [ -n "$SCW_ACCESS_KEY" ] && [ -n "$SCW_SECRET_KEY" ]; then
    echo "🚀 Mode Manuel détecté : Utilisation des clés d'environnement."
    ACCESS_KEY="$SCW_ACCESS_KEY"
    SECRET_KEY="$SCW_SECRET_KEY"
    
    # Valeurs dummy pour satisfaire les variables obligatoires de Terraform
    ROLE_ID="manual_override"
    SECRET_ID="manual_override"

else
    echo "🔑 Aucun environnement détecté. Tentative de connexion à Vault..."

    if [ ! -f "./secure/role_id.txt" ] || [ ! -f "./secure/secret_id.txt" ]; then
        echo "❌ Erreur : Fichiers role_id.txt ou secret_id.txt introuvables dans ./secure/"
        exit 1
    fi

    ROLE_ID=$(tr -d '\r\n' < ./secure/role_id.txt)
    SECRET_ID=$(tr -d '\r\n' < ./secure/secret_id.txt)

    LOGIN_RESPONSE=$(curl -s --request POST --data "{\"role_id\": \"$ROLE_ID\", \"secret_id\": \"$SECRET_ID\"}" $VAULT_ADDR/v1/auth/approle/login)
    VAULT_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.auth.client_token')

    if [ "$VAULT_TOKEN" == "null" ] || [ -z "$VAULT_TOKEN" ]; then
      echo "❌ Erreur : impossible d’obtenir un token Vault."
      exit 1
    fi

    RESPONSE=$(curl -s -H "X-Vault-Token: $VAULT_TOKEN" $VAULT_ADDR/v1/secret/data/scaleway)
    ACCESS_KEY=$(echo $RESPONSE | jq -r '.data.data.access_key')
    SECRET_KEY=$(echo $RESPONSE | jq -r '.data.data.secret_key')
    
    echo "✅ Connexion à Vault réussie."
fi

# === Génération backend dynamique ===
echo "⚙️  Génération de la configuration backend..."
cat > backend.auto.tfbackend <<BACKEND_CONFIG
bucket                      = "terraform-state-cascadya"
key                         = "terraform/terraform.tfstate"
region                      = "nl-ams"
endpoints                   = { s3 = "https://s3.nl-ams.scw.cloud" }
use_path_style              = true
skip_credentials_validation = true
skip_region_validation      = true
skip_metadata_api_check     = true
skip_requesting_account_id  = true
access_key                  = "$ACCESS_KEY"
secret_key                  = "$SECRET_KEY"
BACKEND_CONFIG

# === Export des credentials Scaleway pour Terraform ===
export AWS_ACCESS_KEY_ID="$ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$SECRET_KEY"
export AWS_DEFAULT_REGION="nl-ams"
export AWS_S3_FORCE_PATH_STYLE=true
export AWS_ENDPOINT_URL_S3="https://s3.nl-ams.scw.cloud"

# === Initialisation et exécution Terraform ===
echo "🔄 Initialisation de Terraform..."
terraform init -reconfigure

echo "📋 Exécution du Plan..."
terraform plan -refresh-only -var="vault_role_id=$ROLE_ID" -var="vault_secret_id=$SECRET_ID"

#echo ""
#echo "🚀 Application du plan Terraform..."
#terraform apply -auto-approve \
  #-var="vault_role_id=$ROLE_ID" \
  #-var="vault_secret_id=$SECRET_ID"

# Update the bottom of run_terraform.sh to this:
echo "🛠️  Reconnecting the internal network wires..."
terraform apply \
  -target=scaleway_instance_private_nic.vault_private \
  -target=module.thingsboard_platform.scaleway_instance_private_nic.thingsboard_private \
  -auto-approve \
  -var="vault_role_id=$ROLE_ID" \
  -var="vault_secret_id=$SECRET_ID"
  
# === Nettoyage ===
unset ROLE_ID SECRET_ID VAULT_TOKEN ACCESS_KEY SECRET_KEY SCW_ACCESS_KEY SCW_SECRET_KEY
rm -f backend.auto.tfbackend

echo ""
echo "✅ Exécution terminée avec succès."