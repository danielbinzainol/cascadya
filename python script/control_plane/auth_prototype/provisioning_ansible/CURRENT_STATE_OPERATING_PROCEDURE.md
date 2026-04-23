# Procedure Operatoire - Etat Actuel Valide

Ce document decrit la procedure complete pour passer d'un IPC industriel vierge
a l'etat actuel valide du projet.

Etat actuel couvert par cette procedure :

- installation SSD via cle USB d'installation
- layout Mender A/B valide
- partition `/data` chiffreee en LUKS
- auto-unlock TPM2 local de `/data`
- mise a jour OTA Mender validee
- demonstration `remote unlock` validee en mode `direct`
- backend de demonstration `Vault + broker` lance sur le laptop

Le deploiement Ansible de la telemetrie `edge-agent` est desormais valide cote
IPC pour la partie deploiement. La validation runtime de bout en bout de cette
brique reste conditionnee au raccordement reel du simulateur Modbus et du
broker NATS du lab.

Ce document ne couvre pas encore :

- le transport final `WireGuard + Teltonika + broker/Vault`
- le `cutover` du boot complet vers le remote unlock
- la suppression du token TPM local via `remote-unlock-remove-local-tpm.yml`

## 1. Perimetre et livrable final

En fin de procedure, on doit pouvoir montrer :

- `findmnt /` sur le slot Mender actif
- `findmnt /data` sur `/dev/mapper/cascadya_data`
- `cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2`
- `mender-update show-artifact`
- `remote-unlock-validate.yml` avec :
  `Dry-run remote unlock completed successfully.`

## 2. Environnements utilises

### WSL

Repo :

```text
~/git/cascadya-project/cascadya-edge-os-images
```

### Windows PowerShell

Repo :

```text
C:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images
```

### IPC industriel

Utilisateur :

```text
cascadya
```

### Laptop de demo

Role :

- heberge `Vault` de demo
- heberge le broker de demo
- expose `8443` au reseau management

## 3. Variables a adapter

Verifier ou adapter ces valeurs avant execution.

```text
IPC management IP        = 192.168.50.10
Laptop management IP     = 192.168.50.20
LUKS passphrase          = admin
Inventory host alias     = cascadya
Artifact name            = cascadya-edge-os-v1.0.0
Mender artifact path     = output-mender-base/cascadya-mender-base.mender
Edge-agent app dir       = /data/cascadya/agent
Edge-agent cert dir      = /data/cascadya/agent/certs
Edge-agent venv dir      = /data/cascadya/venv
Edge-agent Modbus host   = 192.168.50.2
Edge-agent NATS URL      = tls://10.30.0.1:4222
Edge-agent cert bundle   = .tmp/cascadya-edge-agent/cascadya
Demo broker URL          = https://192.168.50.20:8443
Vault token demo         = dev-only-token
Vault KV path demo       = secret/remote-unlock/cascadya
```

Pour retrouver l'IP management du laptop sous Windows :

```powershell
ipconfig
```

## 4. Pre-requis

### Outils cote WSL

Verifier :

```bash
ansible --version
docker --version
openssl version
```

### Outils cote Windows

Verifier :

```powershell
.\tools\packer.exe version
```

### Reseau

Le reseau management entre le laptop et l'IPC doit permettre :

- SSH vers `192.168.50.10`
- acces de l'IPC vers le endpoint NATS/TLS configure pour la telemetrie
- acces de l'IPC vers le laptop sur `192.168.50.20:8443`

## 5. Phase 1 - Construire les artefacts image

Executer sur : `WSL`, puis `Windows PowerShell`.

Si les artefacts existent deja et sont connus comme bons, cette phase peut etre
sautee.

### 5.1 Construire l'image Mender

Sur `WSL` :

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images
BASE_IMAGE_PATH="/mnt/c/Users/Daniel BIN ZAINOL/Desktop/GIT - Daniel/cascadya-edge-os-images/output-debian-base/debian-base.img" \
bash scripts/build_mender_image.sh
```

Resultat attendu :

- `output-mender-base/cascadya-mender-base.img.xz`
- `output-mender-base/cascadya-mender-base.mender`

### 5.2 Construire l'image installateur USB

Sur `Windows PowerShell` :

```powershell
cd "C:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images"
.\tools\packer.exe build -force -var-file="packer/variables.pkr.hcl" packer/debian-v2-prod.pkr.hcl
```

Resultat attendu :

```text
output-final\cascadya-v2-prod.img
```

Rollback / diagnostic :

- verifier les artefacts `output-mender-base`
- verifier `packer/debian-v2-prod.pkr.hcl`
- verifier les derniers correctifs Packer et Mender du repo

## 6. Phase 2 - Installer l'IPC vierge

Executer sur : `poste operateur + IPC`.

1. Flasher `output-final/cascadya-v2-prod.img` sur une cle USB.
2. Demarrer l'IPC sur la cle.
3. Laisser l'installation automatique se terminer.
4. Retirer la cle USB.
5. Redemarrer l'IPC sur le SSD.

Resultat attendu :

- le SSD boote sans la cle
- l'IPC obtient un shell Debian normal

## 7. Phase 3 - Valider le premier boot SSD

Executer sur : `IPC`.

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
findmnt /
cat /etc/crypttab
command -v systemd-cryptenroll
sudo mender-update show-artifact
```

Resultat attendu :

- presence de `sda1`, `sda2`, `sda3`, `sda4`
- rootfs actif sur `sda2` ou `sda3`
- `systemd-cryptenroll` disponible

Si `/data` n'est pas monte :

```bash
sudo systemctl status systemd-cryptsetup@cascadya_data.service --no-pager
sudo systemctl start systemd-cryptsetup@cascadya_data.service
sudo mount -a
findmnt /data
sudo mender-update show-artifact
```

Quand le prompt apparait, entrer :

```text
admin
```

Resultat attendu :

- `/data` monte
- `mender-update show-artifact` retourne l'artifact courant

## 8. Phase 4 - Enroler le TPM2 pour l'auto-unlock local

Executer sur : `IPC`.

```bash
sudo systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/sda4
sudo systemctl daemon-reload
sudo update-initramfs -u
sudo reboot
```

Quand la passphrase est demandee :

```text
admin
```

Apres reboot :

```bash
findmnt /data
cat /etc/crypttab
sudo cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2
sudo mender-update show-artifact
```

Resultat attendu :

- `/data` monte automatiquement
- `crypttab` contient `tpm2-device=auto,tpm2-pcrs=7`
- `luksDump` contient `systemd-tpm2`

Rollback / diagnostic :

- verifier `crypttab`
- verifier `systemd-cryptsetup@cascadya_data.service`
- verifier `update-initramfs -u`

### 8.1 Complement - Cas reel observe sur un IPC neuf le 24 mars 2026

Sur un IPC neuf deja joignable en SSH, la sequence suivante a ete necessaire
pour aligner l'etat machine avec l'objectif de boot local auto-unlock TPM.

#### 8.1.1 Verification initiale apres premier boot

Executer sur : `IPC`.

```bash
hostname
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
findmnt /
findmnt /data
cat /etc/crypttab
command -v systemd-cryptenroll
sudo mender-update show-artifact || sudo mender show-artifact
```

Sortie observee et interpretee :

- `/data` etait deja monte
- `systemd-cryptenroll` etait present
- `mender-update` retournait `unknown`
- le TPM n'etait pas encore exploitable par `systemd-cryptenroll`

#### 8.1.2 Symptomes du manque de support TPM userspace

Commande :

```bash
sudo systemd-cryptenroll --tpm2-device=list
sudo systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/sda4
```

Symptomes observes :

```text
TPM2 support is not installed.
TPM2 support not installed: Operation not supported
```

Dans ce cas, installer les paquets TPM suivants.

#### 8.1.3 Installation des paquets TPM manquants

Executer sur : `IPC`.

```bash
ls -l /dev/tpm*
systemctl status tpm2-abrmd --no-pager || true
dpkg -l | grep -E 'tpm2|cryptsetup|clevis'

sudo apt-get update
sudo apt-get install -y tpm2-tools libtss2-tcti-device0
```

Puis reverifier :

```bash
sudo systemd-cryptenroll --tpm2-device=list
```

Resultat attendu :

- presence de `/dev/tpm0` et `/dev/tpmrm0`
- `systemd-cryptenroll --tpm2-device=list` retourne une ligne du type :
  `PATH /dev/tpmrm0 ...`

#### 8.1.4 Enroler le token TPM puis regenerer l'initramfs

Executer sur : `IPC`.

```bash
sudo systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/sda4
sudo systemctl daemon-reload
sudo update-initramfs -u
sudo reboot
```

Quand la passphrase est demandee, entrer la passphrase LUKS courante.
Dans l'etat de lab valide observe, cette passphrase etait encore :

```text
admin
```

#### 8.1.5 Verifier l'auto-unlock local apres reboot

Apres reconnexion SSH sur l'IPC :

```bash
hostname
findmnt /
findmnt /data
cat /etc/crypttab

sudo apt-get update
sudo apt-get install -y cryptsetup

sudo cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2
```

Resultat valide observe le 24 mars 2026 :

- `/data` etait monte automatiquement apres reboot
- `sudo cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2` retournait :
  `0: systemd-tpm2`

Note importante :

- sur cet IPC, `/etc/crypttab` est reste sous la forme
  `cascadya_data UUID=... none luks`
- malgre cela, l'etat doit etre considere comme valide si :
  - `/data` se remonte automatiquement apres reboot
  - `luksDump` montre bien `systemd-tpm2`

Conclusion pratique :

- pour cette famille d'images, la preuve de validation la plus fiable est le
  triplet :
  - reboot sans saisie manuelle
  - `/data` monte automatiquement
  - `cryptsetup luksDump` contient `systemd-tpm2`

## 9. Phase 5 - Valider l'OTA Mender locale

Executer sur : `WSL`, puis `IPC`.

### 9.1 Copier l'artefact OTA vers l'IPC

Sur `WSL` :

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images
scp output-mender-base/cascadya-mender-base.mender cascadya@192.168.50.10:/home/cascadya/
```

### 9.2 Installer et valider l'OTA

Sur `IPC` :

```bash
sudo mkdir -p /data/updates
sudo mv /home/cascadya/cascadya-mender-base.mender /data/updates/
sudo mender-update install /data/updates/cascadya-mender-base.mender
sudo reboot
```

Apres reboot :

```bash
findmnt /
findmnt /data
sudo mender-update show-artifact
sudo mender-update commit
```

Resultat attendu :

- rootfs bascule de `sda2` a `sda3` ou inversement
- `/data` reste monte
- `Committed.` s'affiche

## 10. Phase 6 - Deployer l'edge-agent de telemetrie

Executer sur : `WSL`, puis `IPC`.

### 10.1 Source de verite des fichiers telemetrie

Les scripts et services de telemetrie doivent etre maintenus dans le repo
Ansible, pas copies manuellement sous `/home/cascadya/python_scripts`.

Source de verite actuelle :

- scripts Python : `roles/edge-agent/files/src/agent`
- templates systemd : `roles/edge-agent/templates`
- runtime sur l'IPC : `/data/cascadya/agent`
- certificats runtime sur l'IPC : `/data/cascadya/agent/certs`
- environnement virtuel runtime sur l'IPC : `/data/cascadya/venv`

Les services systemd cibles sont :

- `gateway_modbus.service`
- `telemetry_publisher.service`

Les units historiques `cascadya-gateway.service` et
`cascadya-telemetry.service` ne doivent pas etre copiees telles quelles dans
`/etc/systemd/system`. Les templates Ansible sont la reference.

### 10.2 Creer l'inventaire edge-agent

Sur `WSL` :

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
cat > inventory-edge-agent.ini <<'EOF'
[cascadya_ipc]
cascadya ansible_host=192.168.50.10 ansible_user=cascadya edge_agent_modbus_host=192.168.50.2 edge_agent_modbus_port=502 edge_agent_nats_url=tls://10.30.0.1:4222 edge_agent_nats_telemetry_subject=cascadya.telemetry.live edge_agent_nats_command_subject=cascadya.routing.command edge_agent_nats_ping_subject=cascadya.routing.ping
EOF
```

Un exemple equivalent est fourni dans :

```text
inventory-edge-agent.ini.example
```

Verifier l'acces Ansible :

```bash
ansible -i inventory-edge-agent.ini all -k -m ping
```

Resultat attendu :

- `ping: pong`

### 10.3 Poser le bundle client NATS sur le controleur Ansible

Le role `edge-agent` attend un bundle client par machine dans :

```text
.tmp/cascadya-edge-agent/<inventory_hostname>/
```

Sur `WSL` :

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
mkdir -p .tmp/cascadya-edge-agent/cascadya
cp /path/to/ca.crt .tmp/cascadya-edge-agent/cascadya/ca.crt
cp /path/to/client.crt .tmp/cascadya-edge-agent/cascadya/client.crt
cp /path/to/client.key .tmp/cascadya-edge-agent/cascadya/client.key
ls -lh .tmp/cascadya-edge-agent/cascadya
```

Resultat attendu :

- `.tmp/cascadya-edge-agent/cascadya/ca.crt`
- `.tmp/cascadya-edge-agent/cascadya/client.crt`
- `.tmp/cascadya-edge-agent/cascadya/client.key`

Note :

- si `ca.crt` est present dans le bundle local, le role le deploiera en
  priorite
- si `ca.crt` n'est pas fourni dans le bundle local, le role utilisera
  `roles/edge-agent/files/certs/ca.crt`

### 10.4 Deployer les services de telemetrie

Sur `WSL` :

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-edge-agent.ini -k -K edge-agent-deploy.yml
```

Resultat attendu :

- `gateway_modbus_sbc.py` copie vers `/data/cascadya/agent`
- `telemetry_publisher.py` copie vers `/data/cascadya/agent`
- `ca.crt`, `client.crt`, `client.key` copies vers `/data/cascadya/agent/certs`
- venv cree dans `/data/cascadya/venv`
- `gateway_modbus.service` active et `enabled`
- `telemetry_publisher.service` active et `enabled`

### 10.5 Valider les services de telemetrie

Sur `WSL` :

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-edge-agent.ini -k -K edge-agent-validate.yml
```

Si le simulateur Modbus ou le broker NATS ne sont pas encore raccordes au lab,
utiliser a la place une validation de deploiement seule :

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-edge-agent.ini -k -K edge-agent-validate.yml \
  -e edge_agent_expect_runtime_connectivity=false
```

Sur `IPC` :

```bash
ls -lah /data/cascadya/agent
ls -lah /data/cascadya/agent/certs
sudo systemctl status gateway_modbus.service --no-pager
sudo systemctl status telemetry_publisher.service --no-pager
sudo journalctl -u gateway_modbus.service -n 50 --no-pager
sudo journalctl -u telemetry_publisher.service -n 50 --no-pager
```

Resultat attendu :

- les deux services sont `active (running)`
- les scripts sont deployes sous `/data/cascadya/agent`
- le bundle TLS est present sous `/data/cascadya/agent/certs`
- les journaux ne montrent pas d'erreur de certificat, de Modbus ou de NATS

Interpretation :

- si `edge_agent_expect_runtime_connectivity=true`, la validation est stricte et
  attend un Modbus et un NATS reelement joignables
- si `edge_agent_expect_runtime_connectivity=false`, la validation confirme le
  deploiement Ansible, les fichiers, les units et l'activation systemd, sans
  exiger que les dependances externes soient disponibles a cet instant

Resultat observe sur l'etat actuel du lab :

- la validation de deploiement seule est passee avec succes
- les services `gateway_modbus.service` et `telemetry_publisher.service` sont
  installes et `enabled`
- les journaux montrent encore des timeouts attendus tant que `192.168.50.2`
  et le broker NATS cible ne sont pas effectivement raccordes

Rollback / diagnostic :

- si `client.crt` ou `client.key` manque cote controleur, le role echoue avant
  le deploiement
- si les services demarrent puis redemarrent en boucle, verifier d'abord
  `journalctl -u gateway_modbus.service` et
  `journalctl -u telemetry_publisher.service`
- ne pas corriger directement a la main sous `/data/cascadya/agent` ; corriger
  d'abord les fichiers source sous `roles/edge-agent/`

## 11. Phase 7 - Preparer l'inventaire Ansible

Executer sur : `WSL`.

Creer le fichier `inventory-remote-unlock.ini` :

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
cat > inventory-remote-unlock.ini <<'EOF'
[cascadya_ipc]
cascadya ansible_host=192.168.50.10 ansible_user=cascadya remote_unlock_transport_mode=direct remote_unlock_management_interface=enp3s0 remote_unlock_uplink_interface=enp2s0 remote_unlock_broker_url=https://192.168.50.20:8443
EOF
```

Verifier l'acces Ansible :

```bash
ansible -i inventory-remote-unlock.ini all -k -m ping
```

Resultat attendu :

- `ping: pong`

## 12. Phase 8 - Generer les certificats IPC et broker

Executer sur : `WSL`.

### 12.1 Certificats client IPC

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini remote-unlock-generate-certs.yml
```

Resultat attendu :

```text
.tmp/cascadya-remote-unlock/cascadya/ca.crt
.tmp/cascadya-remote-unlock/cascadya/client.crt
.tmp/cascadya-remote-unlock/cascadya/client.key
```

### 12.2 Certificat serveur broker

```bash
ansible-playbook remote-unlock-generate-demo-broker-certs.yml \
  -e remote_unlock_demo_broker_san_ip=192.168.50.20 \
  -e remote_unlock_generate_demo_broker_certs_force=true
```

Resultat attendu :

```text
.tmp/cascadya-remote-unlock/broker/server.crt
.tmp/cascadya-remote-unlock/broker/server.key
.tmp/cascadya-remote-unlock/broker/ca.crt
```

Rollback / diagnostic :

- si le cert broker a ete genere avec la mauvaise IP, relancer la commande avec
  `remote_unlock_generate_demo_broker_certs_force=true`

## 13. Phase 9 - Lancer Vault et le broker de demonstration

Executer sur : `WSL`.

### 13.1 Creer le reseau Docker

```bash
docker network create cascadya-demo
```

### 13.2 Lancer Vault de demonstration

```bash
docker run --cap-add=IPC_LOCK --name vault-demo --network cascadya-demo -d -p 8200:8200 \
  -e VAULT_DEV_ROOT_TOKEN_ID=dev-only-token \
  hashicorp/vault server -dev -dev-listen-address=0.0.0.0:8200
```

### 13.3 Injecter le secret de demonstration

```bash
curl -sS \
  -H "X-Vault-Token: dev-only-token" \
  -H "Content-Type: application/json" \
  --data '{"data":{"secret":"admin"}}' \
  http://127.0.0.1:8200/v1/secret/data/remote-unlock/cascadya
```

### 13.4 Construire le broker de demonstration

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
docker build -t cascadya-demo-broker -f demo/Dockerfile.remote-unlock-demo-broker .
```

### 13.5 Lancer le broker de demonstration

```bash
docker rm -f remote-unlock-demo-broker 2>/dev/null || true
docker run --name remote-unlock-demo-broker --network cascadya-demo -d -p 8443:8443 \
  -v "$PWD/.tmp/cascadya-remote-unlock/broker:/certs:ro" \
  -e VAULT_TOKEN=dev-only-token \
  cascadya-demo-broker \
  --listen-host 0.0.0.0 \
  --listen-port 8443 \
  --server-cert /certs/server.crt \
  --server-key /certs/server.key \
  --client-ca /certs/ca.crt \
  --vault-addr http://vault-demo:8200 \
  --vault-kv-mount secret \
  --vault-kv-prefix remote-unlock
```

### 13.6 Verifier les conteneurs

```bash
docker ps
docker logs --tail 20 vault-demo
docker logs --tail 20 remote-unlock-demo-broker
```

Resultat attendu :

- `vault-demo` en `Up`
- `remote-unlock-demo-broker` en `Up`

## 14. Phase 10 - Exposer le broker sur le reseau management

Executer sur : `Windows PowerShell administrateur`.

Dans l'etat actuel du lab, Docker Desktop n'ecoute pas directement sur
`192.168.50.20:8443`. On ajoute donc un `portproxy`.

```powershell
netsh interface portproxy delete v4tov4 listenaddress=192.168.50.20 listenport=8443
netsh interface portproxy add v4tov4 listenaddress=192.168.50.20 listenport=8443 connectaddress=127.0.0.1 connectport=8443
New-NetFirewallRule -DisplayName "Cascadya Demo Broker 8443" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443
```

Verifier :

```powershell
netsh interface portproxy show v4tov4
Test-NetConnection 192.168.50.20 -Port 8443
```

Resultat attendu :

- `TcpTestSucceeded : True`

Rollback :

```powershell
netsh interface portproxy delete v4tov4 listenaddress=192.168.50.20 listenport=8443
Remove-NetFirewallRule -DisplayName "Cascadya Demo Broker 8443"
```

## 15. Phase 11 - Deployer le remote unlock de demonstration sur l'IPC

Executer sur : `WSL`.

### 15.1 Deployer les certificats sur l'IPC

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-stage-certs.yml \
  -e remote_unlock_enable=true
```

### 15.2 Bootstrap du role remote unlock

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_transport_mode=direct \
  -e remote_unlock_broker_url=https://192.168.50.20:8443 \
  -e remote_unlock_device_id=cascadya
```

### 15.3 Preflight

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-preflight.yml \
  -e remote_unlock_transport_mode=direct
```

### 15.4 Validation

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_transport_mode=direct
```

En parallele, garder les logs broker ouverts :

```bash
docker logs -f remote-unlock-demo-broker
```

Resultat attendu :

- `Dry-run remote unlock completed successfully.`
- logs broker avec `challenge issued`
- logs broker avec `unlock approved`

## 16. Phase 12 - Commandes de preuve de l'etat final

### 16.1 Sur l'IPC

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
findmnt /
findmnt /data
cat /etc/crypttab
sudo cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2
sudo mender-update show-artifact
sudo grep REMOTE_UNLOCK_BROKER_URL /etc/cascadya/unlock/unlock.env
sudo grep REMOTE_UNLOCK_TRANSPORT_MODE /etc/cascadya/unlock/unlock.env
```

Resultat attendu :

- `/data` monte sur `/dev/mapper/cascadya_data`
- `systemd-tpm2` est present dans le header LUKS
- `REMOTE_UNLOCK_BROKER_URL="https://192.168.50.20:8443"`
- `REMOTE_UNLOCK_TRANSPORT_MODE="direct"`

### 16.2 Sur WSL

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_transport_mode=direct
docker logs --tail 50 remote-unlock-demo-broker
```

Resultat attendu :

- `Dry-run remote unlock completed successfully.`
- `challenge issued device_id=cascadya`
- `unlock approved device_id=cascadya`

## 17. Ce qui n'est pas encore dans l'etat actuel

Ne pas inclure dans cette procedure de validation courante :

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-cutover.yml \
  -e remote_unlock_enable=true

ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-remove-local-tpm.yml \
  -e remote_unlock_enable=true
```

Ces etapes sont reservees a la future bascule vers le modele de production.

## 18. Resume executif

En suivant ce document, on obtient :

- un IPC installe sur SSD
- Mender A/B valide
- `/data` chiffre en LUKS
- auto-unlock TPM2 local valide
- OTA Mender validee
- demonstration fonctionnelle du flux `IPC -> broker -> Vault`
- demonstration pilotee exclusivement par commandes et playbooks

Le prochain objectif, hors de ce document, est de remplacer le transport direct
de demonstration par le transport cible `WireGuard + Teltonika + broker/Vault`.

## 19. Annexe - Procedure complementaire pour retrouver l'etat valide du 23 mars 2026

Cette annexe ne remplace pas les sections precedentes.
Elle ajoute la procedure compacte correspondant au setup reel valide pendant la
seance du 23 mars 2026, avec :

- `WSL` comme controleur Ansible
- `IPC` joignable en SSH sur le LAN local
- `VM Broker` exposee sur Internet en `8443`
- `VM Vault` reachable par la VM Broker
- validation `remote-unlock-validate.yml` verte en mode `direct`

### 19.1 Parties concernees

- `WSL`
  - synchronise le repo Windows
  - genere les certificats
  - execute les playbooks Ansible
- `IPC`
  - recoit les certificats client
  - execute le script `remote unlock`
  - contacte le broker distant en HTTPS mTLS
- `VM Broker`
  - heberge le broker `remote-unlock`
  - expose `POST /challenge` et `POST /unlock` sur `8443`
- `VM Vault`
  - stocke le secret pour `device_id=cascadya`
- `Scaleway / Firewall`
  - doit autoriser `TCP 8443` vers la VM Broker

### 19.2 Valeurs du setup valide

```text
WSL repo                   = ~/git/cascadya-project/cascadya-edge-os-images/ansible
Windows repo               = C:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible
IPC alias Ansible          = cascadya
IPC SSH IP                 = 192.168.10.109
IPC user                   = cascadya
IPC management interface   = enp3s0
IPC uplink interface       = enp2s0
Broker VM public IP        = 51.15.64.139
Broker VM user             = ubuntu
Vault VM IP                = 51.15.36.65
Broker URL                 = https://51.15.64.139:8443
Vault KV mount             = secret
Vault KV prefix            = remote-unlock
Vault KV final path        = secret/remote-unlock/cascadya
Transport mode             = direct
Broker SSH key             = ~/.ssh/id_ed25519
```

### 19.3 Commandes dans l'ordre

#### 19.3.1 WSL - Synchroniser le repo et charger la cle SSH Broker

```bash
rsync -ah "/mnt/c/Users/Daniel BIN ZAINOL/Desktop/GIT - Daniel/cascadya-edge-os-images/ansible/" \
  ~/git/cascadya-project/cascadya-edge-os-images/ansible/

cd ~/git/cascadya-project/cascadya-edge-os-images/ansible

eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

#### 19.3.2 WSL - Creer l'inventaire IPC

```bash
cat > inventory-remote-unlock.ini <<'EOF'
[cascadya_ipc]
cascadya ansible_host=192.168.10.109 ansible_user=cascadya ansible_ssh_transfer_method=piped remote_unlock_transport_mode=direct remote_unlock_management_interface=enp3s0 remote_unlock_uplink_interface=enp2s0 remote_unlock_gateway_audit=false remote_unlock_broker_url=https://51.15.64.139:8443 remote_unlock_device_id=cascadya
EOF
```

#### 19.3.3 WSL - Creer l'inventaire Broker

Ne pas stocker le token Vault dans Git. Le passer via `-e`.

```bash
cat > inventory-remote-unlock-broker.ini <<'EOF'
[remote_unlock_broker]
broker-DEV1-S ansible_host=51.15.64.139 ansible_user=ubuntu ansible_ssh_transfer_method=piped remote_unlock_broker_bind_port=8443 remote_unlock_broker_vault_addr=http://51.15.36.65:8200 remote_unlock_broker_vault_kv_mount=secret remote_unlock_broker_vault_kv_prefix=remote-unlock
EOF
```

#### 19.3.4 WSL - Verifier les acces SSH et Ansible

```bash
ssh -o StrictHostKeyChecking=accept-new cascadya@192.168.10.109 'hostname'

ssh -i ~/.ssh/id_ed25519 ubuntu@51.15.64.139 'hostname'

ansible -i inventory-remote-unlock.ini all -k -m ping

ansible -i inventory-remote-unlock-broker.ini remote_unlock_broker -m ping \
  -e ansible_ssh_private_key_file=~/.ssh/id_ed25519 \
  -e ansible_ssh_transfer_method=piped
```

#### 19.3.5 WSL - Generer les certificats client IPC

```bash
ansible-playbook -i inventory-remote-unlock.ini remote-unlock-generate-certs.yml \
  -e remote_unlock_generate_certs_force=true
```

#### 19.3.6 WSL - Generer les certificats serveur Broker

```bash
ansible-playbook remote-unlock-generate-broker-certs.yml \
  -e remote_unlock_demo_broker_san_ip=51.15.64.139 \
  -e remote_unlock_generate_demo_broker_certs_force=true
```

#### 19.3.7 WSL - Deployer le broker sur la VM Broker

```bash
ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-deploy-broker.yml \
  -e ansible_ssh_private_key_file=~/.ssh/id_ed25519 \
  -e ansible_ssh_transfer_method=piped \
  -e remote_unlock_broker_vault_token='TON_TOKEN_VAULT'
```

#### 19.3.8 Scaleway / Firewall - Ouvrir `TCP 8443`

Action manuelle dans la console cloud sur `broker-DEV1-S` :

- autoriser `TCP 8443` en entree
- source temporaire possible : `0.0.0.0/0`

#### 19.3.9 WSL - Injecter le secret dans Vault

Pour le `dry-run`, une valeur de test suffit.
Avant un vrai `cutover`, remplacer cette valeur par le vrai passphrase LUKS.

```bash
ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-seed-vault-secret.yml \
  -e ansible_ssh_private_key_file=~/.ssh/id_ed25519 \
  -e ansible_ssh_transfer_method=piped \
  -e remote_unlock_broker_vault_token='TON_TOKEN_VAULT' \
  -e remote_unlock_device_id=cascadya \
  -e remote_unlock_vault_secret_value='admin'
```

#### 19.3.10 WSL - Stager les certificats sur l'IPC

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-stage-certs.yml \
  -e remote_unlock_enable=true
```

#### 19.3.11 WSL - Bootstrap remote unlock sur l'IPC

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml \
  -e remote_unlock_enable=true
```

#### 19.3.12 WSL - Preflight sur l'IPC

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-preflight.yml
```

#### 19.3.13 WSL - Validation finale sur l'IPC

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml \
  -e remote_unlock_enable=true
```

### 19.4 Verifications utiles si quelque chose bloque

#### IPC - Test manuel du broker

```bash
sudo curl -v \
  --cert /etc/cascadya/unlock/client.crt \
  --key /etc/cascadya/unlock/client.key \
  --cacert /etc/cascadya/unlock/ca.crt \
  -H "Content-Type: application/json" \
  --data '{"device_id":"cascadya","hostname":"pc-ind-efic2000ca","wg_interface":"wg0","management_interface":"enp3s0","uplink_interface":"enp2s0"}' \
  https://51.15.64.139:8443/challenge
```

#### VM Broker - Logs du broker

```bash
sudo docker logs -f remote_unlock_broker
```

#### VM Vault - Lecture du secret

```bash
curl -sS \
  -H "X-Vault-Token: TON_TOKEN_VAULT" \
  http://127.0.0.1:8200/v1/secret/data/remote-unlock/cascadya
```

### 19.5 Etat final attendu

La fin correcte de cette annexe est :

- `remote-unlock-stage-certs.yml` vert
- `remote-unlock-bootstrap.yml` vert
- `remote-unlock-preflight.yml` vert
- `remote-unlock-validate.yml` vert
- logs broker avec :
  - `challenge issued device_id=cascadya`
  - `unlock approved device_id=cascadya`

Resume attendu dans la validation :

```text
Dry-run status: [remote-unlock] Dry-run remote unlock completed successfully.
Transport mode: direct
WireGuard status: not required in direct mode
```

### 19.6 Points de vigilance

- remplacer `admin` par le vrai passphrase LUKS avant un `cutover`
- revoquer / rotater le token Vault utilise pendant les tests
- ne pas lancer `remote-unlock-cutover.yml` tant que le secret reel n'est pas en place
- traiter Mender a part si on veut retrouver une validation OTA complete

### 19.7 Complement - Alignement d'un nouvel IPC deja accessible en SSH

Quand un nouvel IPC a deja ete image, boote et rendu joignable en SSH, la
sequence reelle minimale utilisee pour l'aligner avec l'etat cible est la
suivante.

#### Sur l'IPC

```bash
hostname
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
findmnt /
findmnt /data
cat /etc/crypttab
command -v systemd-cryptenroll
sudo mender-update show-artifact || sudo mender show-artifact

ls -l /dev/tpm*
systemctl status tpm2-abrmd --no-pager || true
dpkg -l | grep -E 'tpm2|cryptsetup|clevis'

sudo apt-get update
sudo apt-get install -y tpm2-tools libtss2-tcti-device0
sudo systemd-cryptenroll --tpm2-device=list

sudo systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/sda4
sudo systemctl daemon-reload
sudo update-initramfs -u
sudo reboot
```

Apres reboot :

```bash
hostname
findmnt /
findmnt /data
cat /etc/crypttab

sudo apt-get update
sudo apt-get install -y cryptsetup
sudo cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2
```

Etat valide retenu :

- `/data` monte automatiquement
- `cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2` retourne une entree
- l'IPC est alors pret pour la suite de la section `19.3`

### 19.8 Complement - Etat valide du 24 mars 2026 et bascule du remote unlock en WireGuard

Cette section complete l'annexe precedente avec l'etat reel atteint le
`24 mars 2026`. Elle ne remplace pas la procedure du `23 mars 2026`; elle la
prolonge avec :

- l'alignement complet d'un nouvel IPC deja image
- la validation OTA Mender manuelle reellement effectuee
- la bascule du flux `remote-unlock` du mode `direct` vers le mode `wireguard`

#### 19.8.1 Etat reel retenu pour l'IPC cible apres alignement

L'etat retenu et observe sur l'IPC cible est le suivant :

- hostname : `cascadya`
- interface management : `enp3s0` avec `192.168.50.1/24`
- interface uplink : `enp2s0` avec `192.168.10.109/24`
- gateway uplink : `192.168.10.1`
- partition LUKS : `/dev/sda4`
- mapper LUKS : `/dev/mapper/cascadya_data`
- mountpoint : `/data`
- rootfs actif apres OTA : `/dev/sda3`

Validation locale retenue sur l'IPC :

- `/data` se remonte automatiquement apres reboot
- `sudo cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2` retourne une entree
- `findmnt /` retourne `/dev/sda3`
- `findmnt /data` retourne `/dev/mapper/cascadya_data`

#### 19.8.2 Correctifs Mender reels utilises sur le nouvel IPC

Pour permettre l'installation OTA Mender locale sur ce nouvel IPC, il a fallu
recreer les metadonnees runtime suivantes :

```bash
sudo mkdir -p /data/mender
printf 'device_type=cascadya-ipc\n' | sudo tee /data/mender/device_type >/dev/null
printf '{\n  "RootfsPartA": "/dev/sda2",\n  "RootfsPartB": "/dev/sda3"\n}\n' | sudo tee /data/mender/mender.conf >/dev/null
sudo chown root:root /data/mender/device_type /data/mender/mender.conf
sudo chmod 644 /data/mender/device_type
sudo chmod 600 /data/mender/mender.conf
```

OTA valide retenue :

- installation de l'artifact `.mender` sur l'IPC
- reboot sur `/dev/sda3`
- `mender commit` execute avec succes
- reboot de confirmation toujours sur `/dev/sda3`

#### 19.8.3 Architecture finale retenue pour le remote unlock

L'architecture finale validee le `24 mars 2026` pour le flux d'unlock est :

- `WSL -> SSH -> IPC` via `192.168.50.1`
- `IPC -> WireGuard -> broker` via `10.30.0.1:8443`
- `broker -> Vault` via `51.15.36.65:8200`

Valeurs retenues :

- broker public : `51.15.64.139`
- broker WireGuard : `10.30.0.1/24`
- IPC WireGuard : `10.30.0.10/32`
- endpoint WireGuard : `51.15.64.139:51820/UDP`
- URL finale du broker remote unlock : `https://10.30.0.1:8443`
- chemin Vault du secret : `secret/data/remote-unlock/cascadya`

Important :

- le certificat broker a ete regenere avec SAN `10.30.0.1`
- apres cette regeneration, les tests TLS doivent viser `https://10.30.0.1:8443`
- le test par `https://51.15.64.139:8443` n'est plus la reference TLS finale

#### 19.8.4 VM Broker - mise en place WireGuard validee

Le serveur WireGuard valide cote broker a ete monte de la facon suivante :

```bash
sudo apt-get update
sudo apt-get install -y wireguard-tools
sudo mkdir -p /etc/wireguard
sudo chmod 700 /etc/wireguard

sudo sh -c 'umask 077; wg genkey > /etc/wireguard/server.key'
sudo sh -c 'wg pubkey < /etc/wireguard/server.key > /etc/wireguard/server.pub'

SERVER_PRIV=$(sudo cat /etc/wireguard/server.key)

sudo tee /etc/wireguard/wg0.conf >/dev/null <<EOF
[Interface]
Address = 10.30.0.1/24
ListenPort = 51820
PrivateKey = $SERVER_PRIV

[Peer]
PublicKey = <IPC_PUBLIC_KEY>
AllowedIPs = 10.30.0.10/32
EOF

sudo chmod 600 /etc/wireguard/wg0.conf
sudo systemctl enable --now wg-quick@wg0
sudo systemctl status wg-quick@wg0 --no-pager -l
sudo wg show
ip addr show wg0
sudo ss -lunp | grep 51820
```

Etat final retenu cote broker :

- `wg0` actif
- `10.30.0.1/24` present sur `wg0`
- ecoute UDP `51820`
- peer IPC connu avec `AllowedIPs = 10.30.0.10/32`

#### 19.8.5 WSL - regeneration du certificat broker pour l'IP WireGuard

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible

ansible-playbook remote-unlock-generate-broker-certs.yml \
  -e remote_unlock_demo_broker_san_ip=10.30.0.1 \
  -e remote_unlock_generate_demo_broker_certs_force=true

ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-deploy-broker.yml \
  -e ansible_ssh_private_key_file=~/.ssh/id_ed25519 \
  -e ansible_ssh_transfer_method=piped \
  -e remote_unlock_broker_vault_token='TON_TOKEN_VAULT'
```

Etat final retenu :

- broker redeploye avec succes
- port `8443` actif
- certificat serveur valide pour `10.30.0.1`

#### 19.8.6 IPC - bootstrap WireGuard valide

Le bootstrap retenu cote IPC est le bootstrap corrige avec passage des listes
Ansible en JSON reel :

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible

IPC_WG_PRIV=$(cat ~/wg-remote-unlock/cascadya/ipc.key)

ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml \
  -e ansible_host=192.168.50.1 \
  -e remote_unlock_enable=true \
  -e remote_unlock_transport_mode=wireguard \
  -e remote_unlock_manage_wireguard=true \
  -e remote_unlock_broker_url=https://10.30.0.1:8443 \
  -e remote_unlock_wg_interface=wg0 \
  -e remote_unlock_management_interface=enp3s0 \
  -e remote_unlock_uplink_interface=enp2s0 \
  -e remote_unlock_gateway_ip=192.168.10.1 \
  -e network_uplink_interface=enp2s0 \
  -e network_uplink_gateway_ip=192.168.10.1 \
  -e network_wireguard_address=10.30.0.10/32 \
  -e network_wireguard_private_key="$IPC_WG_PRIV" \
  -e network_wireguard_peer_public_key='<BROKER_PUBLIC_KEY>' \
  -e network_wireguard_endpoint=51.15.64.139:51820 \
  -e '{"network_bootstrap_nameservers":["1.1.1.1","8.8.8.8"],"network_wireguard_allowed_ips":["10.30.0.1/32"]}'
```

Le symptome d'echec rencontre avant correction et a conserver comme reference de
diagnostic etait :

```text
Unable to parse IP address: `['
Configuration parsing error
```

Cause retenue :

- `network_wireguard_allowed_ips='["10.30.0.1/32"]'` avait ete interprete comme
  une chaine simple puis jointe caractere par caractere dans `wg0.conf`

Verification locale retenue sur l'IPC :

```bash
sudo systemctl status wg-quick@wg0 --no-pager -l
sudo wg show
ip route get 10.30.0.1
ping -c 3 10.30.0.1
```

Etat final retenu :

- `wg-quick@wg0` actif
- route vers `10.30.0.1` via `wg0`
- `ping 10.30.0.1` reussi
- handshake WireGuard visible cote broker et cote IPC

#### 19.8.7 IPC - test manuel du broker sur le tunnel WireGuard

Le test manuel valide retenu est :

```bash
sudo curl -v \
  --cert /etc/cascadya/unlock/client.crt \
  --key /etc/cascadya/unlock/client.key \
  --cacert /etc/cascadya/unlock/ca.crt \
  -H "Content-Type: application/json" \
  --data '{"device_id":"cascadya","hostname":"cascadya","wg_interface":"wg0","management_interface":"enp3s0","uplink_interface":"enp2s0"}' \
  https://10.30.0.1:8443/challenge
```

Resultat attendu retenu :

- handshake TLS valide
- certificat broker valide pour `10.30.0.1`
- reponse `HTTP/1.0 200 OK`
- JSON avec `challenge_id` et `nonce`

#### 19.8.8 WSL - preflight et validation finales en mode WireGuard

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-preflight.yml \
  -e ansible_host=192.168.50.1 \
  -e remote_unlock_transport_mode=wireguard \
  -e remote_unlock_broker_url=https://10.30.0.1:8443

ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml \
  -e ansible_host=192.168.50.1 \
  -e remote_unlock_enable=true \
  -e remote_unlock_transport_mode=wireguard \
  -e remote_unlock_broker_url=https://10.30.0.1:8443
```

Resume final retenu dans la validation :

```text
WireGuard status: active
Transport mode: wireguard
Dry-run status: [remote-unlock] Dry-run remote unlock completed successfully.
```

Verification complementaire retenue :

- `wg show` cote IPC affiche un `latest handshake`
- `transfer` non nul dans la sortie WireGuard
- logs broker contenant :
  - `challenge issued device_id=cascadya`
  - `unlock approved device_id=cascadya`

#### 19.8.9 Limites restantes a garder en tete

L'etat atteint le `24 mars 2026` est un etat valide et fonctionnel, mais il
reste les limites suivantes :

- le broker actuel est un broker de demonstration
- la quote TPM est transportee et utilisee dans le flux, mais elle n'est pas
  encore verifiee cryptographiquement cote broker
- le `remote-unlock-validate.yml` reste un `dry-run` par defaut
- le vrai `cutover` de production reste a figer ensuite dans des playbooks
  Ansible idempotents

#### 19.8.10 Etat final cible considere comme atteint au 24 mars 2026

Le socle valide retenu a la fin de cette journee est :

- IPC reprovisionne et fonctionnel
- OTA Mender locale validee avec bascule sur `/dev/sda3`
- auto-unlock TPM local valide
- broker Vault fonctionnel
- secret Vault `cascadya` present
- remote unlock fonctionnel en `dry-run`
- transport final `WireGuard` fonctionnel
- validation Ansible verte en mode `wireguard`
