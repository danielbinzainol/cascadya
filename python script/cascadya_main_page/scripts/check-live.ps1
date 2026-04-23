param(
    [string]$HostName = "51.15.115.203",
    [string]$UserName = "ubuntu",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\id_ed25519",
    [string]$DomainName = "portal.cascadya.internal",
    [string]$RemoteService = "cascadya-portal-hub",
    [int]$AppPort = 8788
)

$ErrorActionPreference = "Stop"
$SshTarget = "$UserName@$HostName"

Write-Host "=== VM Control Panel ==="
& ssh -i $KeyPath $SshTarget "sudo systemctl --no-pager --full status '$RemoteService' | sed -n '1,18p'"
if ($LASTEXITCODE -ne 0) {
    throw "Impossible de lire le statut du service distant."
}

Write-Host ""
Write-Host "=== Backend local sur la VM ==="
& ssh -i $KeyPath $SshTarget "curl -s http://127.0.0.1:$AppPort/api/healthz && echo && curl -s http://127.0.0.1:$AppPort/api/status"
if ($LASTEXITCODE -ne 0) {
    throw "Impossible de lire les endpoints locaux sur la VM."
}

Write-Host ""
Write-Host "=== Live via le nom interne depuis ton poste ==="
curl.exe -ksS "https://$DomainName/api/healthz"
Write-Host ""
curl.exe -ksS "https://$DomainName/api/status"
