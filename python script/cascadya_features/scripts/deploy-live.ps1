param(
    [string]$HostName = "51.15.115.203",
    [string]$UserName = "ubuntu",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\id_ed25519",
    [string]$RemoteAppPath = "/opt/cascadya_features",
    [string]$RemoteService = "cascadya-features",
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$RemoteTempPath = "/tmp/cascadya_features-deploy"
$SshTarget = "$UserName@$HostName"

if (-not (Test-Path $KeyPath)) {
    throw "Cle SSH introuvable: $KeyPath"
}

Write-Host "Repo local : $RepoRoot"
Write-Host "Cible      : $SshTarget"
Write-Host "Mode       : $(if ($FrontendOnly) { 'frontend only' } else { 'full app' })"

& ssh -i $KeyPath $SshTarget "rm -rf $RemoteTempPath && mkdir -p $RemoteTempPath"
if ($LASTEXITCODE -ne 0) {
    throw "Impossible de preparer le repertoire temporaire sur la VM."
}

$ItemsToCopy = if ($FrontendOnly) {
    @("web")
} else {
    @("app.py", "requirements.txt", "web", "cascadya_features", "tests")
}

Push-Location $RepoRoot
try {
    & scp -i $KeyPath -r $ItemsToCopy "$SshTarget`:$RemoteTempPath/"
    if ($LASTEXITCODE -ne 0) {
        throw "Echec du transfert SCP vers la VM."
    }
}
finally {
    Pop-Location
}

if ($FrontendOnly) {
    $RemoteCommand = @"
set -e
sudo mkdir -p '$RemoteAppPath/web'
sudo rsync -a --delete '$RemoteTempPath/web/' '$RemoteAppPath/web/'
echo '--- live html markers'
curl -s http://127.0.0.1:8766/ | grep -n 'Review multi-agents\|Syntheses par modele'
"@
} else {
    $RemoteCommand = @"
set -e
sudo mkdir -p '$RemoteAppPath'
sudo rsync -a --delete --exclude '.venv/' --exclude '.env' --exclude 'run.stdout.log' --exclude 'run.stderr.log' '$RemoteTempPath/' '$RemoteAppPath/'
if [ ! -x '$RemoteAppPath/.venv/bin/python' ]; then
  python3 -m venv '$RemoteAppPath/.venv'
fi
'$RemoteAppPath/.venv/bin/python' -m pip install -r '$RemoteAppPath/requirements.txt'
sudo systemctl restart '$RemoteService'
echo '--- service'
sudo systemctl --no-pager --full status '$RemoteService' | sed -n '1,15p'
echo '--- health'
success=0
for attempt in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:8766/api/healthz >/tmp/cascadya_features-health.json 2>/dev/null; then
    cat /tmp/cascadya_features-health.json
    success=1
    break
  fi
  sleep 2
done
test "`$success" -eq 1
"@
}

& ssh -i $KeyPath $SshTarget $RemoteCommand
if ($LASTEXITCODE -ne 0) {
    throw "Le deploiement distant a echoue."
}

Write-Host ""
Write-Host "Deploiement termine."
Write-Host "Verification locale VPN : https://features.cascadya.internal"
