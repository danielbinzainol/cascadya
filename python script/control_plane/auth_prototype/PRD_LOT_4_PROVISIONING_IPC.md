# PRD - Lot 4 - Provisioning IPC, remote-unlock WireGuard, Vault et edge-agent

## 1. Objet

Ce document fige le lot 4 du Control Panel au 31 mars 2026, apres le lot 3
`sites + inventory`.

Le lot 4 ajoute la premiere chaine de provisioning industrielle pilotee depuis
le dashboard :

- preparation d'un job de provisioning rattache a un site et a un asset ;
- orchestration pas a pas de playbooks Ansible depuis l'application ;
- choix d'un mode de dispatch `auto` ou `manual` ;
- bootstrap `remote-unlock` en mode `wireguard` ;
- persistance de la topologie IP et des routes de l'IPC apres detection de
  l'etat reseau courant ;
- deploiement et validation du broker `remote-unlock` ;
- seed du secret LUKS dans `Vault` avec protection contre l'ecrasement non
  confirme ;
- generation automatique du bundle TLS client `edge-agent` depuis `Vault PKI` ;
- deploiement et validation de l'`edge-agent` ;
- exposition, depuis l'onglet `Provisioning`, d'une recette operateur pour
  synchroniser le `modbus simulator` adjacent a l'IPC.

Le produit ne se limite plus a decouvrir et enregistrer des equipements. Il est
desormais capable de preparer et piloter un onboarding technique complet d'un
IPC dans le lab, avec des workflows explicites, versionnes et rejouables.

## 2. Contexte

Le lot 1 a apporte :

- PostgreSQL metier ;
- le catalogue RBAC ;
- les permissions et roles de base ;
- l'automatisation d'infrastructure.

Le lot 2 a apporte :

- `Keycloak` ;
- `OIDC` ;
- le `JIT user mirroring` ;
- l'enforcement des permissions metier ;
- l'administration des utilisateurs.

Le lot 3 a apporte :

- le registre `sites` ;
- le catalogue `inventory_assets` ;
- les `inventory_scans` ;
- l'onboarding metier de base d'un asset decouvert vers un asset enregistre.

Le lot 4 prolonge ce socle et transforme `sites + inventory` en point d'entree
du provisioning terrain.

## 3. Objectifs du lot 4

- Ajouter un vrai objet `provisioning_job` persistant et pilotable.
- Materialiser un contexte de workflow par job :
  - inventories ;
  - `vars.json` ;
  - secret vars ;
  - traces d'execution ;
  - progression pas a pas.
- Exposer des workflows metier lisibles dans l'UI.
- Permettre l'execution `mock` ou `real` des playbooks.
- Permettre un deroulement `auto` du workflow complet ou un ciblage `manual`
  de certains playbooks.
- Aligner le dashboard sur la copie vendored `auth_prototype/provisioning_ansible`
  comme source de verite locale.
- Couvrir un premier onboarding complet d'IPC avec :
  - `remote-unlock` ;
  - `WireGuard` ;
  - broker ;
  - `Vault` ;
  - `edge-agent`.
- Preparer un sous-arbre versionne pour le `modbus simulator`, synchronisable
  depuis le poste WSL de l'operateur vers l'adresse `192.168.50.2`.

## 4. Architecture cible du lot 4

```text
Navigateur VPN
   ->
Traefik
   ->
FastAPI Control Panel
   ->
PostgreSQL metier
   ->
tables sites / inventory / provisioning_jobs
   ->
generation d'artefacts Ansible dans auth_prototype/generated
   ->
execution des playbooks vendored dans auth_prototype/provisioning_ansible
   ->
broker remote-unlock / Vault / IPC cible
```

Composants stabilises dans le perimetre du lot :

- `Traefik`
- `FastAPI`
- `PostgreSQL`
- `Keycloak`
- `Vault`
- `WireGuard`
- `Ansible`
- la copie vendored `auth_prototype/provisioning_ansible`

## 5. Roles et permissions

Le lot 4 s'appuie sur le catalogue RBAC existant et rend utiles les permissions
de provisioning deja seedes :

- `inventory:read`
- `inventory:scan`
- `provision:prepare`
- `provision:run`
- `provision:cancel`
- `site:read`

Roles cibles :

- `viewer`
  - lecture des sites et de l'inventory, sans provisioning.
- `operator`
  - scan et lecture, sans lancement de provisioning.
- `provisioning_manager`
  - preparation, lancement et annulation des jobs.
- `admin`
  - acces complet.

## 6. Modele de donnees atteint

Le lot 4 s'appuie sur le lot 3 et stabilise l'objet `provisioning_jobs`.

### 6.1 Table `provisioning_jobs`

Champs effectivement exploites :

- `id`
- `site_id`
- `asset_id`
- `requested_by_user_id`
- `status`
- `execution_mode`
- `playbook_name`
- `inventory_group`
- `command_preview`
- `context_json`
- `secret_vars_json`
- `logs_json`
- `started_at`
- `finished_at`
- `error_message`
- `created_at`
- `updated_at`

Statuts cibles :

- `prepared`
- `running`
- `succeeded`
- `failed`
- `cancelled`

### 6.2 Enrichissement de `inventory_assets`

Le lot 4 exploite et enrichit les champs necessaires au provisioning :

- `inventory_hostname`
- `management_ip`
- `management_interface`
- `uplink_interface`
- `gateway_ip`
- `wireguard_address`
- `registration_status`
- `provisioning_vars`

Statuts metier utilises dans les parcours :

- `discovered`
- `registered`
- `provisioning`
- `provisioned`

### 6.3 Secret vars de job

Le lot 4 a ajoute une persistance dediee des secrets de workflow dans
`secret_vars_json` pour eviter de tout reposer sur les seules variables shell :

- secret LUKS a seeder dans `Vault`
- confirmation d'ecrasement du secret existant
- token `Vault` du broker remote-unlock
- token `Vault` pour la generation des certificats `edge-agent`
- fichiers temporaires de secrets materialises dans `generated/` au moment de
  l'execution

## 7. Perimetre fonctionnel atteint

### 7.1 Module provisioning dans l'application

Le Control Panel expose maintenant :

- la liste des workflows disponibles ;
- la preparation d'un job de provisioning ;
- le detail d'un job ;
- l'execution d'un job en mode `auto` ;
- l'execution ciblee d'un playbook en mode `manual` ;
- l'annulation d'un job ;
- la suppression d'un job ;
- la visualisation des logs et de la progression.

L'application materialise un contexte complet de job avant execution :

- inventory IPC ;
- inventory broker ;
- inventory edge-agent ;
- `vars.json` associes ;
- etat de progression ;
- resume des steps ;
- fichiers de secrets temporaires si necessaire.

En complement, l'onglet `Provisioning` expose une zone operateur `3 bis.
Synchroniser le modbus simulator` qui :

- reprend l'IP du simulateur associe a l'IPC quand elle est connue ;
- affiche les commandes WSL de sync et de verification ;
- ne lance pas `rsync` depuis le navigateur ;
- formalise la recette de sync comme une procedure produit versionnee.

### 7.2 Modes de dispatch `auto` / `manual`

Le module `Provisioning` distingue maintenant :

- `auto`
  - prepare le job puis deroule les steps du workflow dans l'ordre ;
- `manual`
  - prepare le meme contexte Ansible ;
  - rend les playbooks du workflow selectionnables ;
  - n'execute que l'etape choisie par l'operateur.

Le `dispatch_mode` est persiste dans le contexte du job et partage le meme
graphe d'etapes, les memes artefacts et la meme historisation de logs.

### 7.3 Execution `mock` et `real`

Le runner FastAPI sait :

- rester en `mock` pour valider les parcours UI et les transitions ;
- executer en `real` les playbooks Ansible sur la VM `control-panel-DEV1-S`.

En mode `real`, il :

- positionne `ANSIBLE_CONFIG` sur la copie vendored si elle existe ;
- execute les playbooks depuis `auth_prototype/provisioning_ansible` ;
- depose les artefacts dans `auth_prototype/generated/` ;
- conserve les bundles temporaires dans `auth_prototype/provisioning_ansible/.tmp/`.

### 7.4 Workflows exposes dans le dashboard

Le lot 4 stabilise les workflows suivants :

#### a. `full-ipc-wireguard-onboarding`

Workflow complet de reference pour un nouvel IPC joignable en SSH.

Ordre actuel :

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

#### b. `remote-unlock-wireguard-validation`

Workflow centre sur la brique remote unlock.

Il inclut aussi `ipc-persist-network-routing.yml` pour permettre a l'operateur
de figer la topologie IP de l'IPC avant ou apres un recablage terrain.

#### c. `wazuh-agent-deploy-validate`

Workflow centre sur l'enrollment Wazuh et sa verification.

Ordre actuel :

1. `wazuh-agent-deploy.yml`
2. `wazuh-agent-validate.yml`

#### d. `ipc-alloy-deploy-validate`

Workflow centre sur la collecte de metriques host `node_exporter + Alloy`.

Ordre actuel :

1. `ipc-alloy-deploy.yml`
2. `ipc-alloy-validate.yml`

#### e. `edge-agent-deploy-validate`

Workflow centre sur la pile telemetrie.

Ordre actuel :

1. `edge-agent-generate-certs.yml`
2. `edge-agent-deploy.yml`
3. `edge-agent-validate.yml`
4. `edge-agent-nats-roundtrip.yml`

#### f. `remote-unlock-cutover`

Workflow reserve a la bascule finale post-validation :

1. `remote-unlock-cutover.yml`
2. `remote-unlock-remove-local-tpm.yml`

### 7.5 Synchronisation du modbus simulator

Le lot 4 reference aussi l'outillage adjacent au provisioning IPC pour le
simulateur `Modbus TCP` branche derriere l'IPC.

Etat retenu au 2 avril 2026 :

- un sous-arbre `auth_prototype/modbus_simulator/` existe dans le repo ;
- ce sous-arbre est organise en :
  - `src/` pour le runtime Python ;
  - `systemd/` pour l'unite `modbus-serveur.service` ;
  - `scripts/` pour les helpers de sync WSL -> simulateur ;
- le formulaire `Provisioning` affiche une recette par defaut visant :
  - host `192.168.50.2`
  - user `cascadya`
  - remote dir `/home/cascadya/simulator_sbc`
  - service `modbus-serveur.service`.

Ce point reste une assistance operateur et non un job Ansible execute depuis le
backend.

### 7.6 Persistance reseau IPC

Une nouvelle etape `ipc-persist-network-routing.yml` fige maintenant les IP et
routes de l'IPC a partir de l'etat courant detecte :

- lecture des interfaces management / uplink ;
- detection des CIDR actuels ;
- detection de la gateway uplink ;
- application immediate de l'etat via `ip link` / `ip addr` / `ip route` ;
- generation d'une unite `systemd`
  `cascadya-network-persist.service` avec une ligne `ExecStart=` par action ;
- suppression des anciens artefacts shell/env si l'IPC en porte encore.

Sur le cas valide `cascadya-ipc-10-109`, les routes statiques derivees et
gelees cote IPC sont :

- `10.42.1.7/32 via 192.168.10.1 dev enp2s0` pour `wazuh-Dev1-S` ;
- `10.42.1.4/32 via 192.168.10.1 dev enp2s0` pour Mimir.

La cible produit est la suivante :

- premiere mise en reseau faite manuellement une fois ;
- puis persistance de l'etat valide depuis le Control Panel pour survivre aux
  reboot de l'IPC.

Quand la telemetrie Alloy pousse vers une IP privee Cloud telle que
`10.42.1.4`, la topologie validee impose aussi des routes de retour sur la VM
monitoring. Ce point reste distinct de `ipc-persist-network-routing.yml`, qui
gele uniquement l'etat reseau cote IPC.

## 8. Capacites techniques atteintes

### 8.1 Remote unlock

Le lot 4 couvre maintenant :

- generation de la CA et des certificats client remote-unlock ;
- generation du certificat TLS serveur du broker ;
- staging des certificats sur l'IPC ;
- preparation du peer `WireGuard` sur le broker ;
- deploiement du broker remote-unlock ;
- bootstrap remote-unlock sur l'IPC ;
- preflight reseau et broker ;
- validation fonctionnelle du dry-run remote-unlock.

### 8.2 Vault et secret LUKS

Le lot 4 integre le seed du secret LUKS dans `Vault KV` depuis le workflow UI.

Comportement produit stabilise :

- creation si le secret est absent ;
- no-op idempotent si la meme valeur est deja presente ;
- refus d'ecraser une valeur differente sans confirmation explicite ;
- passage de la confirmation via le formulaire de preparation du job ;
- nettoyage du `secret_vars_json` apres execution.

### 8.3 Generation des certificats edge-agent

Le lot 4 ajoute la generation automatique du bundle TLS client edge-agent depuis
`Vault PKI`.

Comportement stabilise :

- appel de `pki_int/issue/devices-role` ;
- CN par defaut de type `<inventory_hostname>.cascadya.local` ;
- generation de :
  - `client.crt`
  - `client.key`
  - `ca.crt`
- ecriture du bundle dans
  `auth_prototype/provisioning_ansible/.tmp/cascadya-edge-agent/<inventory_hostname>/`

### 8.4 Deploy et validate edge-agent

Le lot 4 couvre maintenant :

- copie des sources Python de l'agent sur l'IPC ;
- copie des certificats dynamiques et de la CA ;
- creation du venv ;
- installation des dependances Python ;
- deploiement des units systemd ;
- activation et demarrage des services ;
- validation structurelle :
  - presence des scripts ;
  - presence des certificats ;
  - services installes ;
  - services `enabled` ;
  - verification optionnelle de stabilite runtime.

### 8.5 Outillage de synchronisation adjacent

Le lot 4 integre des briques de support autour de l'IPC provisionne :

- exposition, dans l'UI, des commandes WSL pour pousser le `modbus simulator`
  depuis le repo courant ;
- helper shell versionne pour rejouer la sync sans reconstruire la recette a la
  main ;
- commandes de verification distantes (`systemctl status`, `journalctl`, `ls`)
  rendues visibles dans le produit.

### 8.6 Scripts edge-agent de reference

Clarification du 14 avril 2026 :

- le traducteur JSON/NATS -> Modbus de reference du repo est
  `auth_prototype/provisioning_ansible/roles/edge-agent/files/src/agent/gateway_modbus_sbc.py` ;
- le publisher de telemetrie NATS issu du monde Modbus est
  `auth_prototype/provisioning_ansible/roles/edge-agent/files/src/agent/telemetry_publisher.py` ;
- `gateway_modbus_sbc.py` porte actuellement la zone de preparation
  `%MW0-%MW16`, les bits/statuts `%MW50/%MW51`, `%MW60/%MW61`, `%MW62/%MW63`
  ainsi que les watchdogs `%MW607` et `%MW620` ;
- la pile planificateur validee en lab est exposee en `%MW100-%MW396`, avec
  `15` emplacements de `20` mots ;
- le runtime actif du simulateur/SBC de reference est expose en
  `%MW700-%MW704` ;
- `telemetry_publisher.py` lit actuellement les registres `400`, `500`,
  `%MW700-%MW704`, `410`, `420` et `430` avant publication sur
  `cascadya.telemetry.live` ;
- `gateway_modbus_sbc.py` durcit maintenant le contrat d'entree
  (`id`, `execute_at`, `c1/c2/c3` obligatoires), relit `%MW0-%MW16` avant
  validation et sait produire un snapshot canonique du planificateur via
  `read_plan` ;
- `gateway_modbus_sbc.py` impose maintenant un ciblage explicite des commandes
  NATS partagees, en acceptant les payloads adresses a l'IPC courant via
  `asset_name`, `target_asset`, `edge_instance_id` ou `inventory_hostname`, et
  en rejetant les cas `missing_target` / `target_mismatch` avant toute ecriture
  Modbus.

### 8.7 Contrat actuel Alloy IPC -> Monitoring VM

Clarification du 14 avril 2026 :

- la configuration Alloy de reference du repo est
  `auth_prototype/provisioning_ansible/roles/ipc-alloy/templates/config.alloy.j2` ;
- ses defaults sont portes par
  `auth_prototype/provisioning_ansible/roles/ipc-alloy/defaults/main.yml` ;
- Alloy scrape uniquement `node_exporter` en local sur `127.0.0.1:9100` ;
- l'intervalle retenu est `15s` avec `scrape_timeout=10s` ;
- le `remote_write` cible `http://10.42.1.4:9009/api/v1/push` ;
- le header `X-Scope-OrgID` est envoye quand un tenant Mimir est configure ;
- les labels stabilises cote IPC sont :
  - `job="node-exporter"`
  - `instance="<ipc>:9100"`
  - `source="ipc"`
  - `node="<inventory_hostname>"`
  - `role="ipc"`
  - `site="<site>"`
  - `retention_profile="<profile>"`
  - `tenant="<tenant_label>"`
- a ce stade, Alloy ne pousse pas la telemetrie JSON NATS issue de
  `telemetry_publisher.py` ; il pousse uniquement les metriques host exposees par
  `node_exporter`.

## 9. Validation acquise en lab

Validation acquise sur `control-panel-DEV1-S` et `cascadya-ipc-10-109` :

- migration Alembic appliquee jusqu'a `20260331_0004` ;
- secret LUKS deja present et coherent dans `Vault` pour l'IPC de reference ;
- `remote-unlock-seed-vault-secret.yml` valide ;
- `remote-unlock-validate.yml` valide ;
- `edge-agent-generate-certs.yml` valide ;
- `edge-agent-deploy.yml` valide ;
- `edge-agent-validate.yml` valide en mode :
  - `edge_agent_expect_runtime_connectivity=false`

Validation fonctionnelle atteinte :

- le workflow complet est expose dans le backend avec `12` etapes ;
- le bundle edge-agent est regenere depuis `Vault PKI` ;
- les artefacts sont deposes sur l'IPC ;
- les units systemd edge-agent sont installees et `enabled`.

## 9bis. Validation complementaire du 13 avril 2026

Validation complementaire acquise sur `control-panel-DEV1-S`,
`cascadya-ipc-10-109`, `wazuh-Dev1-S`, `monitoring-DEV1-S` et
`broker-DEV1-S` :

- le workflow `full-ipc-wireguard-onboarding` expose maintenant `18` steps ;
- `ipc-persist-network-routing.yml` passe en `real` et en reprise manuelle ;
- l'unite `cascadya-network-persist.service` est `enabled` et `active (exited)`
  sur l'IPC ;
- `wazuh-agent-deploy.yml` puis `wazuh-agent-validate.yml` passent sur
  `cascadya-ipc-10-109` avec le manager prive `10.42.1.7` ;
- `ipc-alloy-deploy.yml` puis `ipc-alloy-validate.yml` passent apres correction
  du template Alloy ;
- `alloy.service` et `prometheus-node-exporter.service` sont `active/running` ;
- l'IPC pousse ses metriques host vers `http://10.42.1.4:9009/api/v1/push` ;
- la datasource Grafana existante `prometheus` pointe vers
  `http://10.42.1.4:9009/prometheus` ;
- la requete
  `up{job="node-exporter",instance="cascadya-ipc-10-109:9100"}` retourne `1`
  depuis Grafana ;
- un dashboard operateur `IPC - cascadya-ipc-10-109` a ete valide avec les
  panneaux `IPC Up`, `CPU Usage %`, `Memory Usage %`,
  `Network RX bytes/s` et `Disk Write bytes/s` ;
- `edge-agent-generate-certs.yml`, `edge-agent-deploy.yml`,
  `edge-agent-validate.yml` et `edge-agent-nats-roundtrip.yml` passent en
  reprise manuelle canonique depuis `/opt/control-panel/control_plane/auth_prototype` ;
- le round-trip final `broker_proxy` retourne un `reply payload status: ok`.

Cette premiere passe du `13 avril 2026` n'a pas ete un `18/18` auto pur : le
mode auto a du etre relaie par une reprise manuelle controlee depuis la VM
`control-panel`. En revanche, il valide que la chaine produit complete est
operationnelle jusqu'au dernier step quand les checkpoints sont rejoues dans
l'ordre.

Un rerun ulterieur du meme jour valide maintenant aussi le chemin `real/auto`
complet sur le meme asset :

- le workflow se clot en `18/18` avec `DONE provisioning finished (real)` a
  `2026-04-13T14:48:14.106394+00:00` ;
- `ipc-alloy-validate.yml` confirme en automatique
  `Mimir remote_write: http://10.42.1.4:9009/api/v1/push` ;
- le step final `edge-agent-nats-roundtrip.yml` repasse en `broker_proxy`
  sans reprise manuelle intermediaire ;
- les mesures du dernier probe auto sont :
  - `Temps total observe: 235.373 ms`
  - `Composant proxy: 176.18 ms`
  - `Composant request/reply actif: 59.193 ms`
  - `Canal probe /connz: 7.447 ms`
  - `Canal gateway_modbus /connz: 244.932 ms`
  - `Canal telemetry_publisher /connz: 46.262 ms`
  - `reply payload status: ok`.

Point ouvert hors repo control-plane :

- la persistance des routes de retour sur `monitoring-DEV1-S` doit encore etre
  industrialisee dans le repo `ansible-monitoring`, meme si le chemin a ete
  valide manuellement dans le lab.

Mise a jour produit du 2 avril 2026 :

- l'onglet `Provisioning` inclut la section `3 bis. Synchroniser le modbus
  simulator` ;
- le produit expose la recette WSL/SSH sans pretendre executer lui-meme cette
  sync ;
- le sous-arbre `auth_prototype/modbus_simulator/` devient la source versionnee
  des fichiers a pousser vers `192.168.50.2`.

## 10. Etat produit retenu en fin de lot

Etat retenu comme atteint en fin de lot 4 :

- le dashboard sait preparer un onboarding IPC complet a partir d'un asset du
  lot 3 ;
- le runner sait executer les playbooks de facon deterministe ;
- le seed du secret `Vault` est protege contre l'ecrasement accidentel ;
- la pile `edge-agent` n'a plus besoin d'un bundle TLS pregene a la main ;
- le provisioning complet est pilotable depuis le produit, et non plus
  seulement depuis des commandes shell ad hoc ;
- les metriques IPC sont visibles operatoirement dans Grafana via la datasource
  `prometheus` et Mimir ;
- la procedure de sync du `modbus simulator` adjacent est documentee et exposee
  dans l'UI de provisioning.

## 11. Limites et points hors perimetre

Le lot 4 ne clot pas encore les sujets suivants :

- la preuve de connectivite runtime `NATS` temps reel n'est pas encore retenue
  comme validee automatiquement dans le lab courant ;
- le workflow `remote-unlock-cutover` reste reserve a une bascule finale
  post-validation ;
- la preuve de boot-path complete apres reboot reste un jalon distinct ;
- `Mender` reste un sujet de baking et de qualite d'image, pas un correctif du
  workflow d'onboarding.

## 12. Definition of Done retenue

Le lot 4 peut etre considere comme atteint quand :

- un nouvel IPC peut etre decouvert puis prepare depuis l'UI ;
- un job de provisioning peut etre cree, relu, rejoue, annule et supprime ;
- le workflow complet de reference affiche 12 etapes coherentes ;
- le secret LUKS peut etre seed dans `Vault` avec confirmation d'ecrasement si
  necessaire ;
- le bundle TLS edge-agent est genere automatiquement depuis `Vault PKI` ;
- le deploy edge-agent deploie bien scripts, certs, venv et services ;
- la validation edge-agent passe au moins en mode structurel ;
- la page `Provisioning` expose la recette de sync du `modbus simulator`
  versionne ;
- les limites residuelles sont clairement identifiees comme des sujets reseau ou
  post-cutover, et non comme des trous du workflow de provisioning lui-meme.

## 13. Suite logique apres le lot 4

Le lot 4 a rendu possible le provisioning complet et a mis en evidence un
sujet distinct qui ne doit plus rester implicite :

- la preuve de connectivite runtime `NATS` ;
- la separation entre le chemin reseau `IPC -> Broker` et le chemin
  `Control Plane -> Broker` ;
- l'elimination des anciens defaults `Tailscale` dans la pile edge-agent ;
- l'exposition d'un probe broker HTTPS securise pour le control plane, sans
  ouverture publique brute de `4222` ni de `8222` ;
- l'exploitation des endpoints de monitoring `NATS` (`healthz`, `varz`,
  `connz`) dans le produit.

Ces points sont formalises dans le document :

- `PRD_LOT_5_E2E_TELEMETRIE_NATS.md`
