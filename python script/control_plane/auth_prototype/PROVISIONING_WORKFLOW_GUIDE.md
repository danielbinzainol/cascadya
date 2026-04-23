# Provisioning Workflow Guide

Ce guide aligne le dashboard `auth_prototype` avec le repo Ansible de reference :

`C:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible`

## Validation deja acquise

La phase precedente peut etre consideree comme validee quand :

- le scan IPC retourne bien un candidat reachable
- le site peut etre cree ou reutilise
- l'asset passe de `discovered` a `registered`
- la preparation du job fait passer l'asset a `provisioning`
- le reseau `control-panel -> wireguard -> IPC` permet au minimum `ping` et `TCP/22`

Dans cet etat, le dashboard a deja prouve :

- la decouverte
- l'onboarding
- la preparation du contexte Ansible

Le runner final peut encore rester en mode `mock` tant qu'on n'execute pas les playbooks pour de vrai depuis le control panel.

## Source de verite Ansible

Les workflows du dashboard sont derives des playbooks suivants :

- `remote-unlock-generate-certs.yml`
- `remote-unlock-generate-broker-certs.yml`
- `remote-unlock-stage-certs.yml`
- `ipc-persist-network-routing.yml`
- `remote-unlock-prepare-broker-wireguard.yml`
- `remote-unlock-deploy-broker.yml`
- `remote-unlock-seed-vault-secret.yml`
- `remote-unlock-bootstrap.yml`
- `remote-unlock-preflight.yml`
- `remote-unlock-validate.yml`
- `wazuh-agent-deploy.yml`
- `wazuh-agent-validate.yml`
- `ipc-alloy-deploy.yml`
- `ipc-alloy-validate.yml`
- `edge-agent-generate-certs.yml`
- `edge-agent-deploy.yml`
- `edge-agent-validate.yml`
- `edge-agent-nats-roundtrip.yml`
- `remote-unlock-cutover.yml`
- `remote-unlock-remove-local-tpm.yml`

## Workflows exposes dans le dashboard

### 1. `full-ipc-wireguard-onboarding`

Workflow recommande pour un nouvel IPC deja joignable en SSH.

Ordre :

1. `remote-unlock-generate-certs.yml`
2. `remote-unlock-generate-broker-certs.yml`
3. `remote-unlock-stage-certs.yml`
4. `ipc-persist-network-routing.yml`
5. `remote-unlock-prepare-broker-wireguard.yml`
6. `remote-unlock-deploy-broker.yml`
7. `remote-unlock-seed-vault-secret.yml`
8. `remote-unlock-bootstrap.yml`
9. `remote-unlock-preflight.yml`
10. `remote-unlock-validate.yml`
11. `wazuh-agent-deploy.yml`
12. `wazuh-agent-validate.yml`
13. `ipc-alloy-deploy.yml`
14. `ipc-alloy-validate.yml`
15. `edge-agent-generate-certs.yml`
16. `edge-agent-deploy.yml`
17. `edge-agent-validate.yml`
18. `edge-agent-nats-roundtrip.yml`

Usage :

- premier onboarding complet
- possibilite de lancer tout le flux en `mode auto` ou seulement certaines playbooks en `mode manuel`
- bootstrap WireGuard
- capture de l'etat `ip a` / `ip route` deja valide sur l'IPC puis persistance locale au boot
- seed automatique du secret LUKS dans Vault
- reseed idempotent si la meme valeur est deja presente
- deploiement puis validation de l'agent Wazuh sur l'IPC
- deploiement puis validation de `node_exporter + Grafana Alloy` pour pousser les metriques host vers Mimir
- generation automatique du bundle TLS client edge-agent depuis Vault PKI
- propagation de la CA serveur NATS dediee jusqu'au broker et au bundle edge-agent
- validation du flux remote unlock
- deploiement edge-agent
- verification finale du round-trip NATS edge-agent via le proxy broker
- politique d'ecrasement: creation si absent, overwrite uniquement avec confirmation explicite

### 2. `remote-unlock-wireguard-validation`

Workflow cible pour valider seulement la brique remote unlock.

Ordre :

1. `remote-unlock-generate-certs.yml`
2. `remote-unlock-generate-broker-certs.yml`
3. `remote-unlock-stage-certs.yml`
4. `ipc-persist-network-routing.yml`
5. `remote-unlock-prepare-broker-wireguard.yml`
6. `remote-unlock-deploy-broker.yml`
7. `remote-unlock-seed-vault-secret.yml`
8. `remote-unlock-bootstrap.yml`
9. `remote-unlock-preflight.yml`
10. `remote-unlock-validate.yml`

Usage :

- IPC deja present dans l'inventaire
- on veut verifier WireGuard, broker et Vault avant de toucher a l'edge-agent
- la persistance reseau peut etre relancee seule en `mode manuel` pour figer un nouvel etat des interfaces apres intervention terrain
- le secret LUKS est seed si absent, reutilise tel quel si la valeur est deja la, ou ecrase seulement avec confirmation explicite

### 3. `wazuh-agent-deploy-validate`

Workflow cible pour tester seulement l'enrollment et le runtime Wazuh sur l'IPC.

Ordre :

1. `wazuh-agent-deploy.yml`
2. `wazuh-agent-validate.yml`

Usage :

- remote unlock deja en place
- le manager Wazuh expose deja `1514/TCP` et `1515/TCP`
- le chemin recommande est une IP privee ou un FQDN stable via l'overlay WireGuard du site
- le firewall / security group du manager doit accepter ces flux depuis les CIDRs ou routes overlay reellement utilises par les IPC
- l'IPC doit pouvoir joindre le repository Wazuh, sauf si on fournit ensuite un mode package stage/offline
- utile pour valider l'enrollment avant de rerunner tout l'onboarding
- si un groupe Wazuh est renseigne, il doit deja exister cote manager

### 4. `ipc-alloy-deploy-validate`

Workflow cible pour la collecte de metriques host via `node_exporter + Grafana Alloy`.

Ordre :

1. `ipc-alloy-deploy.yml`
2. `ipc-alloy-validate.yml`

Usage :

- remote unlock deja en place
- on veut rendre l'IPC visible dans Grafana/Mimir sans redeployer le reste de la pile applicative
- `node_exporter` expose CPU, RAM, disque et reseau localement sur l'IPC
- Alloy scrape localement `node_exporter`, puis pousse en remote_write vers Mimir
- le endpoint recommande cote lab est `http://10.42.1.4:9009/api/v1/push`
- le tenant Mimir est maintenant passe via `X-Scope-OrgID` (`classic`, `lts-1y`, `lts-5y`)
- le `retention_profile` reste aligne sur ce meme profil cote IPC, tandis que la retention reelle reste appliquee cote Mimir

### 5. `edge-agent-deploy-validate`

Workflow cible pour la telemetrie seulement.

Ordre :

1. `edge-agent-generate-certs.yml`
2. `edge-agent-deploy.yml`
3. `edge-agent-validate.yml`
4. `edge-agent-nats-roundtrip.yml`

Usage :

- remote unlock deja en place
- on ne veut redeployer que la pile telemetrie
- le bundle TLS client edge-agent est regenere automatiquement depuis Vault PKI avant le deploiement
- le workflow se termine par un round-trip NATS request/reply pour confirmer le chemin broker -> IPC

## Modes de lancement

Le dashboard expose maintenant deux politiques de lancement pour un meme workflow :

- `mode auto`
  - prepare le job puis execute les playbooks dans l'ordre canonique jusqu'a completion, echec ou interruption operateur
- `mode manuel`
  - prepare le meme bundle d'inventory / variables / secrets
  - permet ensuite de choisir explicitement une playbook cible a executer depuis l'UI
  - utile pour rejouer une etape precise, reseeder Vault, ou relancer la persistance reseau seule

Le `dispatch_mode` est persiste dans le contexte du job, puis rehydrate lors des
reprises pour conserver une lecture coherente de l'avancement.

## Persistance reseau IPC

Le playbook `ipc-persist-network-routing.yml` est execute apres le staging des
certificats et avant le bootstrap `WireGuard`.

Objectif :

- partir d'une premiere mise en reseau faite manuellement sur l'IPC ;
- relire l'etat courant des interfaces via `ip a` et `ip route` ;
- figer les CIDR management / uplink et la route par defaut ;
- figer aussi les routes statiques utiles au manager Wazuh lorsque ce dernier
  est atteint via une IP privee sur l'overlay/site ;
- figer de la meme facon les routes statiques utiles a `Mimir` lorsque
  `ipc_alloy_mimir_remote_write_url` pointe vers une IP privee Cloud ;
- reappliquer cet etat a chaque reboot via `systemd`.

Artefacts ecrits sur l'IPC :

- `/etc/systemd/system/cascadya-network-persist.service`

Le playbook reapplique d'abord l'etat valide immediatement via des commandes
`ip link`, `ip addr` et `ip route`, puis genere une unite `systemd` `oneshot`
avec une ligne `ExecStart=` par action reseau a rejouer. Les anciens artefacts
`network.env` et helper shell sont supprimes s'ils existent encore sur l'IPC.

### 6. `remote-unlock-cutover`

Workflow reserve a la bascule finale.

Ordre :

1. `remote-unlock-cutover.yml`
2. `remote-unlock-remove-local-tpm.yml`

Usage :

- uniquement apres validation complete du dry-run remote unlock
- ne pas lancer tant que le secret final n'est pas confirme

## Variables minimales par IPC

Le dashboard doit generer ou confirmer au moins :

- `ansible_host`
- `ansible_user`
- `remote_unlock_management_interface`
- `remote_unlock_uplink_interface`
- `remote_unlock_gateway_ip`
- `remote_unlock_transport_mode`
- `remote_unlock_broker_url`
- `network_wireguard_public_key`
- `remote_unlock_wg_interface`
- `network_bootstrap_nameservers`
- `network_wireguard_address`
- `network_wireguard_private_key`
- `network_wireguard_peer_public_key`
- `network_wireguard_endpoint`
- `network_wireguard_allowed_ips`
- `wazuh_agent_manager_address`
- `wazuh_agent_manager_port`
- `wazuh_agent_registration_server`
- `wazuh_agent_registration_port`
- `wazuh_agent_name`
- `wazuh_agent_group`
- `ipc_alloy_mimir_remote_write_url`
- `ipc_alloy_scrape_interval`
- `ipc_alloy_scrape_timeout`
- `ipc_alloy_retention_profile`
- `ipc_alloy_mimir_tenant`
- `edge_agent_modbus_host`
- `edge_agent_nats_url`

## Parametres globaux Wazuh cote control-panel

Pour eviter de ressaisir les memes valeurs sur chaque IPC, le control-panel peut
porter les valeurs globales suivantes dans
`/etc/control-panel/auth-prototype.env` :

- `AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_ADDRESS_DEFAULT`
- `AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_PORT_DEFAULT`
- `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_SERVER_DEFAULT`
- `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_PORT_DEFAULT`
- `AUTH_PROTO_PROVISIONING_WAZUH_AGENT_GROUP_DEFAULT`
- `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_PASSWORD`
- `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_CA_CERT_PATH`

Usage recommande pour le lab actuel :

- `AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_ADDRESS_DEFAULT=10.42.1.7`
- `AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_PORT_DEFAULT=1514`
- `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_SERVER_DEFAULT=10.42.1.7`
- `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_PORT_DEFAULT=1515`

Le chemin `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_CA_CERT_PATH` est
optionnel, mais recommande si l'on veut copier la CA du manager sur l'IPC
pendant l'enrollment au lieu de laisser l'agent travailler sans cette CA.

Pour eviter de dependre d'une IP publique de sortie du site qui peut changer
apres un reboot routeur, un failover WAN ou une reconnexion 4G/5G, le site
WireGuard doit annoncer une route vers l'IP privee du manager Wazuh. Dans le
lab actuel, cela signifie ajouter au peer Teltonika vers `VM_Cloud` soit :

- le `/32` de la VM Wazuh sur le reseau prive Cloud ;
- soit, si la gateway WireGuard du Cloud route deja tout le reseau prive,
  `10.42.0.0/16`.

Le mode public par IP allowlistee ne doit rester qu'un fallback temporaire de
diagnostic.

## Parametres globaux IPC Alloy / Mimir cote control-panel

Pour industrialiser la telemetrie infra des IPC sans ressaisie a chaque
provisioning, le control-panel peut aussi porter les valeurs globales
suivantes dans `/etc/control-panel/auth-prototype.env` :

- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_REMOTE_WRITE_URL_DEFAULT`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_SCRAPE_INTERVAL_DEFAULT`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_SCRAPE_TIMEOUT_DEFAULT`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_TENANT_DEFAULT`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_RETENTION_PROFILE_DEFAULT`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_USERNAME`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_PASSWORD`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_VERIFY_TLS`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_CA_CERT_PATH`

Usage recommande pour le lab actuel :

- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_REMOTE_WRITE_URL_DEFAULT=http://10.42.1.4:9009/api/v1/push`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_SCRAPE_INTERVAL_DEFAULT=15s`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_SCRAPE_TIMEOUT_DEFAULT=10s`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_RETENTION_PROFILE_DEFAULT=classic`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_TENANT_DEFAULT=classic`
- `AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_VERIFY_TLS=false` tant que le lab pousse en HTTP interne

Le mapping `tenant -> retention reelle` reste applique cote Mimir. Le control
panel prepare surtout :

- le template IPC a utiliser (`classic`, `lts-1y`, `lts-5y`)
- le header tenant `X-Scope-OrgID` pour le tenant cible
- la route statique vers la VM monitoring si le endpoint remote_write est une IP privee

Dans le lab actuel, quand l'IPC pousse vers `10.42.1.4:9009`, la VM
`monitoring-DEV1-S` doit aussi porter des routes de retour vers le LAN site
et/ou l'overlay edge. La topologie validee au 13 avril 2026 est :

- `192.168.10.0/24 via 10.42.1.5 dev ens6`
- `10.9.0.0/16 via 10.42.1.5 dev ens6`

### Validation visuelle Grafana du 13 avril 2026

Sur la topologie validee du `13 avril 2026` :

- la datasource Grafana existante `prometheus` pointe vers
  `http://10.42.1.4:9009/prometheus` ;
- la preuve minimale attendue cote operateur est
  `up{job="node-exporter",instance="<ipc>:9100"} = 1` ;
- sur `cascadya-ipc-10-109`, la requete
  `up{job="node-exporter",instance="cascadya-ipc-10-109:9100"}` retourne `1`
  depuis Grafana ;
- un dashboard operateur `IPC - cascadya-ipc-10-109` a ete valide avec les
  panneaux `IPC Up`, `CPU Usage %`, `Memory Usage %`,
  `Network RX bytes/s` et `Disk Write bytes/s` ;
- cette verification confirme la chaine complete
  `IPC -> Alloy -> Mimir -> Grafana` sans creer de datasource supplementaire.

## Valeurs de reference actuelles

Issues du repo `cascadya-edge-os-images` et du lab valide :

- `edge_agent_modbus_host = 192.168.50.2`
- `edge_agent_nats_url = tls://10.30.0.1:4222`
- `wazuh_agent_manager_port = 1514`
- `wazuh_agent_registration_port = 1515`
- `ipc_alloy_mimir_remote_write_url = http://10.42.1.4:9009/api/v1/push`
- `ipc_alloy_scrape_interval = 15s`
- `ipc_alloy_scrape_timeout = 10s`
- `ipc_alloy_retention_profile = classic`
- `remote_unlock_transport_mode = wireguard`
- `remote_unlock_broker_url = https://10.30.0.1:8443`
- `network_bootstrap_nameservers = ["1.1.1.1","8.8.8.8"]`
- `network_wireguard_allowed_ips = ["10.30.0.1/32"]`

## Regle produit pour le dashboard

Le dashboard ne doit pas reinventer les playbooks.

Il doit :

1. choisir un workflow metier
2. generer les inventories et `vars.json`
3. afficher l'ordre exact des playbooks
4. conserver le contexte du job
5. executer ensuite ce workflow de facon deterministe

La copie vendored [provisioning_ansible](c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/provisioning_ansible) reste la source de verite du control panel pour :

- l'ordre des playbooks
- les variables attendues
- les valeurs par defaut edge-agent et remote-unlock

Cette copie provient du repo historique `cascadya-edge-os-images/ansible`, mais elle vit maintenant dans `auth_prototype` pour simplifier le debug, le sync et l'evolution du dashboard.

En mode `real`, le runner FastAPI :

- execute les playbooks depuis `auth_prototype/provisioning_ansible`
- exporte automatiquement `ANSIBLE_CONFIG=/opt/control-panel/control_plane/auth_prototype/provisioning_ansible/ansible.cfg` si ce fichier existe sur la VM
- materialise les inventories/vars dans `auth_prototype/generated/`
- laisse les artefacts temporaires Ansible dans `auth_prototype/provisioning_ansible/.tmp/`
- prepare aussi un inventory/vars `remote_unlock_broker` pour publier automatiquement le peer WireGuard de l'IPC sur le broker avant le `preflight`
- prepare aussi les variables de certificat TLS du broker a partir de `remote_unlock_broker_url`
- initialise le certificat TLS du broker s'il est absent, sans le regenerer a chaque onboarding IPC
- redeploie le broker avec un certificat signe par la meme CA que `ca.crt` avant le `preflight`

## Mender et baking

L'etat Mender fait partie de la qualite de l'image USB de depart.

En pratique :

- `mender-update show-artifact` doit etre correct des la phase de baking
- le provisioning remote-unlock peut verifier et remonter cet etat pour diagnostic
- le workflow d'onboarding ne doit pas etre responsable de reparer une image deja flashee dont les metadonnees Mender sont incompletes

## Verification locale juste apres le boot de l'IPC

Avant de relancer un workflow remote unlock sur un IPC deja demarre, verifier
d'abord l'etat local de la machine :

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
findmnt /
findmnt /data
cat /etc/crypttab
systemctl status wg-quick@wg0 --no-pager
systemctl status cascadya-unlock-data.service --no-pager
sudo mender-update show-artifact
```

Points a confirmer :

- `/` est bien monte sur la partition rootfs attendue
- `/data` est deja monte, ou bien peut etre remonte proprement
- `wg0` est actif si le mode remote unlock est `wireguard`
- `cascadya-unlock-data.service` existe deja si le cutover a ete applique

Si `/data` n'est pas monte alors que la machine a deja ete preparee pour le
remote unlock, utiliser la sequence manuelle minimale avant de poursuivre :

```bash
sudo systemctl status systemd-cryptsetup@cascadya_data.service --no-pager
sudo systemctl start systemd-cryptsetup@cascadya_data.service
sudo mount -a
findmnt /data
```

Si `findmnt /data` reste vide, ne pas lancer `remote-unlock-validate.yml` ni
`edge-agent-validate.yml` tant que le montage n'est pas resolu.

## Relance manuelle depuis le shell du control panel

Quand on relance un playbook manuellement sur la VM control panel, il faut
recharger explicitement les variables shell que le runner FastAPI injecte
normalement lui-meme :

```bash
cd /opt/control-panel/control_plane/auth_prototype
export ANSIBLE_CONFIG=/opt/control-panel/control_plane/auth_prototype/provisioning_ansible/ansible.cfg

export IPC_INV=generated/<device_id>.remote-unlock.ini
export IPC_VARS=generated/<device_id>.remote-unlock.vars.json
export IPC_SECRETS=generated/<device_id>.job-<N>-remote-unlock-preflight-secrets.json

export BROKER_INV=generated/<device_id>.remote-unlock-broker.ini
export BROKER_VARS=generated/<device_id>.remote-unlock-broker.vars.json
export BROKER_SECRETS=generated/<device_id>.job-<N>-remote-unlock-deploy-broker-secrets.json
```

Verifier ensuite que les variables ne sont pas vides et que les fichiers
existent vraiment :

```bash
printf '%s\n' "$ANSIBLE_CONFIG" "$IPC_INV" "$IPC_VARS" "$IPC_SECRETS" "$BROKER_INV" "$BROKER_VARS" "$BROKER_SECRETS"
ls -l "$IPC_INV" "$IPC_VARS" "$IPC_SECRETS" "$BROKER_INV" "$BROKER_VARS" "$BROKER_SECRETS"
```

Si l'une de ces variables est vide ou pointe vers un fichier absent, Ansible
peut essayer de parser tout `/opt/control-panel/control_plane/auth_prototype`
comme source d'inventory. Le symptome typique est une avalanche de warnings sur
`frontend/node_modules`, `generated/*.json`, `provisioning_ansible/*.yml`, puis
`No inventory was parsed`.

Ordre de relance manuelle recommande pour debug :

1. `remote-unlock-deploy-broker.yml` si le broker ou son certificat ont change
2. `remote-unlock-preflight.yml`
3. `remote-unlock-seed-vault-secret.yml` si le broker repond mais `/unlock` renvoie `HTTP 500`
4. `remote-unlock-validate.yml`

Ne pas relancer `remote-unlock-remove-local-tpm.yml` tant que le reboot de
preuve du chemin remote unlock exclusif n'a pas ete valide.

## Constat du 1 avril 2026 sur les reruns partiels

Les essais reels du 1 avril 2026 ont mis en evidence un point important :

- un rerun apres echec partiel ne retombe pas toujours sur la meme erreur ;
- la cause change parfois parce qu'une partie du flux a deja laisse des
  artefacts ou une mutation reseau ;
- supprimer le job web peut faire disparaitre les fichiers
  `generated/<device_id>.job-<N>-...-secrets.json` sans supprimer l'etat
  partiel cree sur les VMs.

Exemples observes le 1 avril 2026 :

- bundle broker `.tmp` relu avec le mauvais ownership sur le control-plane ;
- relance manuelle impossible a l'identique car le `job-...-secrets.json`
  n'existe plus ;
- token probe broker disponible dans `/etc/control-panel/auth-prototype.env`
  mais non injecte uniformement dans tous les chemins de relance ;
- perte de joignabilite SSH pendant `remote-unlock-bootstrap.yml` apres mutation
  reseau sur l'IPC.

La regle operatoire retenue a partir de ce constat est :

- pour une reprise apres echec partiel, preferer une relance manuelle depuis la
  VM `control-panel` ;
- recharger les secrets depuis `/etc/control-panel/auth-prototype.env` ;
- verifier les artefacts `generated/` et `.tmp/` avant de relancer ;
- ne pas supposer qu'un rerun est "equivalent" a un run neuf.

## Reprise manuelle complete depuis la VM control-panel

Preparation minimale recommande :

```bash
sudo bash -lc '
set -a
source /etc/control-panel/auth-prototype.env
set +a
cd /opt/control-panel/control_plane/auth_prototype
export DEVICE_ID=<device_id>
export ANSIBLE_CONFIG=/opt/control-panel/control_plane/auth_prototype/provisioning_ansible/ansible.cfg
export IPC_INV=generated/${DEVICE_ID}.remote-unlock.ini
export IPC_VARS=generated/${DEVICE_ID}.remote-unlock.vars.json
export BROKER_INV=generated/${DEVICE_ID}.remote-unlock-broker.ini
export BROKER_VARS=generated/${DEVICE_ID}.remote-unlock-broker.vars.json
export EDGE_INV=generated/${DEVICE_ID}.edge-agent.ini
export EDGE_VARS=generated/${DEVICE_ID}.edge-agent.vars.json
printf "%s\n" "$ANSIBLE_CONFIG" "$IPC_INV" "$IPC_VARS" "$BROKER_INV" "$BROKER_VARS" "$EDGE_INV" "$EDGE_VARS"
ls -l "$IPC_INV" "$IPC_VARS" "$BROKER_INV" "$BROKER_VARS" "$EDGE_INV" "$EDGE_VARS"
'
```

Regles de reprise recommandees :

- pour les steps broker, preferer les secrets issus de :
  - `AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_SSH_KEY_PATH`
  - `AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_VAULT_TOKEN`
  - `AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_TOKEN`
- pour les steps IPC et edge-agent, preferer les secrets issus de :
  - `AUTH_PROTO_PROVISIONING_SSH_KEY_PATH`
  - `AUTH_PROTO_PROVISIONING_SSH_PASSWORD`
  - `AUTH_PROTO_PROVISIONING_BECOME_PASSWORD`
- verifier les droits de
  `provisioning_ansible/.tmp/cascadya-remote-unlock/` avant un rerun broker ;
- revalider la joignabilite SSH juste apres `remote-unlock-bootstrap.yml`
  avant de lancer `preflight`, `validate` puis les steps Wazuh / Alloy / edge-agent.

Ordre manuel canonique a conserver :

1. `remote-unlock-generate-certs.yml`
2. `remote-unlock-generate-broker-certs.yml`
3. `remote-unlock-stage-certs.yml`
4. `ipc-persist-network-routing.yml`
5. `remote-unlock-prepare-broker-wireguard.yml`
6. `remote-unlock-deploy-broker.yml`
7. `remote-unlock-seed-vault-secret.yml`
8. `remote-unlock-bootstrap.yml`
9. `remote-unlock-preflight.yml`
10. `remote-unlock-validate.yml`
11. `wazuh-agent-deploy.yml`
12. `wazuh-agent-validate.yml`
13. `ipc-alloy-deploy.yml`
14. `ipc-alloy-validate.yml`
15. `edge-agent-generate-certs.yml`
16. `edge-agent-deploy.yml`
17. `edge-agent-validate.yml`
18. `edge-agent-nats-roundtrip.yml`

La suite produit de ce sujet est formalisee dans :

- `PRD_LOT_6_REPRISE_IDEMPOTENCE_PROVISIONING.md`
