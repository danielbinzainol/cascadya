param(
    [string]$HostName = "51.15.115.203",
    [string]$UserName = "ubuntu",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\id_ed25519",
    [string]$DomainName = "portal.cascadya.internal",
    [string]$RemoteAppPath = "/opt/cascadya_portal_hub",
    [string]$RemoteEnvDir = "/etc/cascadya-portal",
    [string]$RemoteEnvPath = "/etc/cascadya-portal/cascadya-portal.env",
    [string]$RemoteService = "cascadya-portal-hub",
    [string]$RemoteTraefikRoot = "/opt/traefik-control-panel",
    [int]$AppPort = 8788,
    [string[]]$AllowedCidrs = @("10.8.0.0/24", "10.42.1.5/32", "195.68.106.70/32"),
    [switch]$PushLocalEnv
)

$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$RemoteTempPath = "/tmp/cascadya_portal_hub-deploy"
$SshTarget = "$UserName@$HostName"
$LocalEnvPath = Join-Path $RepoRoot ".env"

if (-not (Test-Path $KeyPath)) {
    throw "Cle SSH introuvable: $KeyPath"
}

Write-Host "Repo local : $RepoRoot"
Write-Host "Cible      : $SshTarget"
Write-Host "Domaine    : $DomainName"
Write-Host "Service    : $RemoteService"
Write-Host "Port local : $AppPort"
Write-Host "CIDRs      : $($AllowedCidrs -join ', ')"

& ssh -i $KeyPath $SshTarget "rm -rf $RemoteTempPath && mkdir -p $RemoteTempPath"
if ($LASTEXITCODE -ne 0) {
    throw "Impossible de preparer le repertoire temporaire sur la VM."
}

$ItemsToCopy = @("app.py", "requirements.txt", ".env.example", "README.md", "portal_hub", "deploy")

Push-Location $RepoRoot
try {
    & scp -i $KeyPath -r $ItemsToCopy "$SshTarget`:$RemoteTempPath/"
    if ($LASTEXITCODE -ne 0) {
        throw "Echec du transfert SCP vers la VM."
    }

    if ($PushLocalEnv) {
        if (-not (Test-Path $LocalEnvPath)) {
            throw "Option -PushLocalEnv demandee, mais le fichier local .env est absent."
        }
        & scp -i $KeyPath $LocalEnvPath "$SshTarget`:$RemoteTempPath/local.env"
        if ($LASTEXITCODE -ne 0) {
            throw "Impossible de transferer le .env local vers la VM."
        }
    }
}
finally {
    Pop-Location
}

$PushLocalEnvFlag = if ($PushLocalEnv) { "1" } else { "0" }
$AllowedCidrsBlock = (($AllowedCidrs | ForEach-Object { "          - `"$($_)`"" }) -join "`n")
$RemoteCommand = @"
set -e
sudo mkdir -p '$RemoteAppPath' '$RemoteEnvDir' '$RemoteTraefikRoot/dynamic' '$RemoteTraefikRoot/certs'
sudo rsync -a --delete --exclude '.venv/' --exclude '.env' --exclude '__pycache__/' --exclude '*.pyc' '$RemoteTempPath/' '$RemoteAppPath/'

if [ ! -x '$RemoteAppPath/.venv/bin/python' ]; then
  python3 -m venv '$RemoteAppPath/.venv'
fi

'$RemoteAppPath/.venv/bin/python' -m pip install -r '$RemoteAppPath/requirements.txt'

sed \
  -e 's|__REMOTE_APP_PATH__|$RemoteAppPath|g' \
  -e 's|__REMOTE_ENV_PATH__|$RemoteEnvPath|g' \
  '$RemoteAppPath/deploy/cascadya-portal-hub.service.template' | sudo tee '/etc/systemd/system/$RemoteService.service' >/dev/null

python3 - <<'PY'
from pathlib import Path
template_path = Path('$RemoteAppPath/deploy/cascadya-portal-hub.traefik.yml.template')
target_path = Path('/tmp/$RemoteService.yml')
content = template_path.read_text()
content = content.replace('__DOMAIN_NAME__', '$DomainName')
content = content.replace('__APP_PORT__', '$AppPort')
content = content.replace('__ALLOWED_CIDRS_BLOCK__', """$AllowedCidrsBlock""")
target_path.write_text(content)
PY
sudo install -m 0644 '/tmp/$RemoteService.yml' '$RemoteTraefikRoot/dynamic/$RemoteService.yml'

sed \
  -e 's|__DOMAIN_NAME__|$DomainName|g' \
  -e 's|__APP_PORT__|$AppPort|g' \
  '$RemoteAppPath/deploy/cascadya-portal-hub.env.template' | sudo tee '$RemoteEnvPath.example' >/dev/null

if [ '$PushLocalEnvFlag' = '1' ]; then
  sudo install -m 0640 '$RemoteTempPath/local.env' '$RemoteEnvPath'
elif [ ! -f '$RemoteEnvPath' ]; then
  sudo install -m 0640 '$RemoteEnvPath.example' '$RemoteEnvPath'
fi

if [ ! -f '$RemoteTraefikRoot/certs/$DomainName.key' ]; then
  sudo openssl genrsa -out '$RemoteTraefikRoot/certs/$DomainName.key' 2048
fi

if [ ! -f '$RemoteTraefikRoot/certs/$DomainName.crt' ]; then
  sudo openssl req -x509 -new \
    -key '$RemoteTraefikRoot/certs/$DomainName.key' \
    -out '$RemoteTraefikRoot/certs/$DomainName.crt' \
    -days 365 \
    -subj '/CN=$DomainName' \
    -addext 'subjectAltName=DNS:$DomainName'
fi

sudo chmod 0600 '$RemoteTraefikRoot/certs/$DomainName.key'
sudo chmod 0644 '$RemoteTraefikRoot/certs/$DomainName.crt'
sudo systemctl daemon-reload
sudo systemctl enable '$RemoteService'
sudo systemctl restart '$RemoteService'

echo '--- service'
sudo systemctl --no-pager --full status '$RemoteService' | sed -n '1,18p'
echo '--- health'
success=0
for attempt in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:$AppPort/api/healthz >/tmp/cascadya_portal-health.json 2>/dev/null; then
    cat /tmp/cascadya_portal-health.json
    success=1
    break
  fi
  sleep 2
done
test "\$success" -eq 1
if grep -q 'replace-me' '$RemoteEnvPath'; then
  echo '--- attention'
  echo 'Le fichier environment contient encore des placeholders. Complete PORTAL_SESSION_SECRET et PORTAL_OIDC_CLIENT_SECRET.'
fi
"@

& ssh -i $KeyPath $SshTarget $RemoteCommand
if ($LASTEXITCODE -ne 0) {
    throw "Le deploiement distant a echoue."
}

Write-Host ""
Write-Host "Deploiement termine."
Write-Host "Verification live : https://$DomainName"
