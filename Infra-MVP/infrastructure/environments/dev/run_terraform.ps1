# ==========================================================
# Script : run_terraform.ps1
# Objectif : Lancer Terraform en se connectant à Vault
# ==========================================================

# === Configuration de l'adresse Vault ===
$env:VAULT_ADDR = "https://secrets.cascadya.com"

# === Lecture des identifiants AppRole depuis le dossier "secure" ===
$role_id = Get-Content ".\secure\role_id.txt" | Out-String
$secret_id = Get-Content ".\secure\secret_id.txt" | Out-String

# Nettoyage des retours à la ligne et espaces
$role_id = $role_id.Trim()
$secret_id = $secret_id.Trim()

Write-Host "Connexion à Vault ($env:VAULT_ADDR)..."
Write-Host " Initialisation de Terraform..."

# === Lancement de Terraform ===
terraform init | Out-Host
terraform plan -var="vault_role_id=$role_id" -var="vault_secret_id=$secret_id"

# Nettoyage mémoire
$role_id = $null
$secret_id = $null
[System.GC]::Collect()

Write-Host ""
Write-Host "Execution terminee avec succes."


