#!/bin/bash
# ==========================================================
# Script : apply_terraform.sh
# Objective: Apply the previously generated tfplan
# ==========================================================

set -e

if [ ! -f "tfplan" ]; then
    echo "❌ Error: 'tfplan' file not found. Please run ./plan_terraform.sh first."
    exit 1
fi

# === Configuration ===
export VAULT_ADDR="https://secrets.cascadya.com"
export VAULT_SKIP_VERIFY=true

# === Credentials Logic ===
if [ -n "$SCW_ACCESS_KEY" ] && [ -n "$SCW_SECRET_KEY" ]; then
    echo "🚀 Manual mode: Using environment keys."
    ACCESS_KEY="$SCW_ACCESS_KEY"
    SECRET_KEY="$SCW_SECRET_KEY"
else
    echo "🔑 Connecting to Vault..."
    if [ ! -f "./secure/role_id.txt" ] || [ ! -f "./secure/secret_id.txt" ]; then
        echo "❌ Error: Credentials missing."
        exit 1
    fi
    ROLE_ID=$(tr -d '\r\n' < ./secure/role_id.txt)
    SECRET_ID=$(tr -d '\r\n' < ./secure/secret_id.txt)

    LOGIN_RESPONSE=$(curl -s --request POST --data "{\"role_id\": \"$ROLE_ID\", \"secret_id\": \"$SECRET_ID\"}" $VAULT_ADDR/v1/auth/approle/login)
    VAULT_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.auth.client_token')

    RESPONSE=$(curl -s -H "X-Vault-Token: $VAULT_TOKEN" $VAULT_ADDR/v1/secret/data/scaleway)
    ACCESS_KEY=$(echo $RESPONSE | jq -r '.data.data.access_key')
    SECRET_KEY=$(echo $RESPONSE | jq -r '.data.data.secret_key')
    echo "✅ Vault connection successful."
fi

# === Dynamic Backend Generation ===
echo "⚙️ Generating backend config..."
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

export AWS_ACCESS_KEY_ID="$ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$SECRET_KEY"
export AWS_DEFAULT_REGION="nl-ams"
export AWS_S3_FORCE_PATH_STYLE=true
export AWS_ENDPOINT_URL_S3="https://s3.nl-ams.scw.cloud"

# === Init and Apply ===
echo "🔄 Initializing Terraform..."
terraform init -reconfigure

echo "🚀 Applying the saved plan..."
terraform apply "tfplan"

# === Cleanup ===
unset ROLE_ID SECRET_ID VAULT_TOKEN ACCESS_KEY SECRET_KEY SCW_ACCESS_KEY SCW_SECRET_KEY
rm -f backend.auto.tfbackend
rm -f tfplan

echo ""
echo "✅ Infrastructure updated successfully."