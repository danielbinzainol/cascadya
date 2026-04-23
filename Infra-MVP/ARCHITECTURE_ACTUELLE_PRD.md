# PRD - Architecture Actuelle Infra-MVP

Version: 1.1
Date: 2026-04-14
Statut: Etat actuel du repo Terraform
Auteur: Codex

## 1. Objet

Ce document decrit l'architecture actuellement modelisee dans le repo
`Infra-MVP`, en particulier l'environnement `infrastructure/environments/dev`.

Le but est de figer une vue claire et exploitable de :

- la structure Terraform ;
- les reseaux prives et acces publics ;
- les VMs et services declares ;
- les stockages attaches ;
- les security groups et ports exposes ;
- les flux principaux entre les briques ;
- les points de vigilance et limites actuelles.

Ce document decrit la cible "selon le repo", c'est-a-dire ce que Terraform
porte aujourd'hui. Il peut exister un ecart entre :

- le code present dans le repo ;
- l'etat effectivement applique dans le cloud ;
- certains changements encore en attente de `terraform apply`.

## 2. Perimetre

Inclus :

- environnement `dev` sous `infrastructure/environments/dev`
- modules Terraform locaux :
  - `network`
  - `scaleway-instance`
  - `telemetry-db`
- VMs/services declares dans `main.tf`
- security groups dedies du broker, control panel, Wazuh, monitoring et WireGuard
- bucket Object Storage dedie a Mimir
- backend Terraform et lecture des credentials via Vault

Exclus :

- detail des applications deployees dans les VMs hors Terraform
- playbooks Ansible et logique applicative hors de ce repo
- architecture HA / production non encore modelisee ici

## 3. Sources de verite dans le repo

Fichiers principaux :

- [main.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/environments/dev/main.tf)
- [variables.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/environments/dev/variables.tf)
- [vault.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/environments/dev/vault.tf)
- [broker-sg.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/environments/dev/broker-sg.tf)
- [control-panel-sg.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/environments/dev/control-panel-sg.tf)
- [monitoring-sg.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/environments/dev/monitoring-sg.tf)
- [wireguard-sg.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/environments/dev/wireguard-sg.tf)
- [wazuh-sg.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/environments/dev/wazuh-sg.tf)
- [mimir-object-storage.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/environments/dev/mimir-object-storage.tf)

Modules :

- [network/main.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/modules/network/main.tf)
- [scaleway-instance/main.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/modules/scaleway-instance/main.tf)
- [telemetry-db/main.tf](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/Infra-MVP/infrastructure/modules/telemetry-db/main.tf)

## 4. Vue d'ensemble

L'infrastructure actuelle repose sur Scaleway, avec :

- un VPC principal ;
- trois Private Networks :
  - `public` -> `10.42.0.0/24`
  - `app` -> `10.42.1.0/24`
  - `data` -> `10.42.2.0/24`
- une couche VPN/WireGuard d'administration et d'acces prive :
  - `10.8.0.0/24` pour `wg0`
  - `10.9.0.0/16` pour `wg1`
- plusieurs VMs applicatives exposees via IP publique ;
- un broker NATS central ;
- un control panel ;
- une VM Wazuh dediee ;
- une VM monitoring dediee a `Grafana + Loki + Mimir + Alloy` ;
- un bucket Object Storage prive pour Mimir ;
- une base Telemetry PostgreSQL privee ;
- Vault utilise par Terraform pour charger les secrets Scaleway.

Vue logique simplifiee :

```text
Administrateurs
  -> Internet / WireGuard (10.8.0.0/24)
  -> VMs publiques ou privees selon SG

Sites / IPC
  -> Broker / Wazuh / control plane selon les ports ouverts

Scaleway VPC
  -> corp-public  10.42.0.0/24
  -> corp-app     10.42.1.0/24
  -> corp-data    10.42.2.0/24

VMs app:
  docmost
  control-panel
  c-market
  wireguard
  monitoring
  broker
  wazuh

VM / service data:
  vault
  telemetry-db
```

## 5. Structure Terraform

### 5.1 Environment

L'environnement principal du repo est `dev`.

Il assemble :

- le provider Scaleway ;
- le provider Vault ;
- le backend S3 Scaleway ;
- les modules reseau / VM / base ;
- des security groups dedies pour certains services sensibles.

### 5.2 Backend et secrets

Terraform state :

- bucket `terraform-state-cascadya`
- endpoint S3 Scaleway `https://s3.nl-ams.scw.cloud`

Secrets / providers :

- Terraform s'authentifie a Vault via AppRole ;
- Vault lit le secret `secret/scaleway` ;
- les credentials Scaleway sont injectes dans les providers Terraform.

Implication :

- les credentials cloud ne sont pas hardcodes dans `main.tf`
- la chaine `plan/apply` depend de Vault et du bon DNS reseau

## 6. Reseaux

### 6.1 VPC et Private Networks

Le module `network` cree :

- un VPC principal `vpc-main`
- trois Private Networks :
  - `corp-public`
  - `corp-app`
  - `corp-data`

Usage actuel :

- `app` porte la majorite des VMs applicatives
- `data` porte la base Telemetry et le NIC prive Vault
- `public` existe dans le code mais n'est pas utilise par une VM decrite ici

### 6.2 Reseau WireGuard

Le reseau `10.8.0.0/24` sert de plan d'acces prive / management / overlay
humain via `wg0`.

Le reseau `10.9.0.0/16` sert de plan WireGuard dedie aux routeurs edge /
Teltonika via `wg1`.

Il est reutilise dans :

- les allowlists d'administration ;
- certaines connexions privees vers Wazuh ;
- l'acces securise au control panel.

## 7. Inventaire des briques

### 7.1 Vault

Role :

- stockage des secrets
- source de verite pour les credentials Scaleway utilises par Terraform

Implantation :

- VM `vault-DEV1-S`
- type `DEV1-S`
- image `ubuntu_jammy`
- IP publique reservee
- volume data dedie `10 Go`
- NIC prive sur `data`
- SG : security group reseau standard

### 7.2 Docmost

Role :

- documentation / knowledge base

Implantation :

- VM `docmost-DEV1-S`
- type `DEV1-S`
- image `ubuntu_jammy`
- volume data `20 Go`
- reseau `app`
- SG : security group reseau standard

### 7.3 Control Panel

Role :

- front/back de pilotage et d'administration
- support des tests Auth / futur control plane

Implantation :

- VM `control-panel-DEV1-S`
- type `DEV1-S`
- image `ubuntu_jammy`
- volume data `20 Go`
- reseau `app`
- SG dedie `sg-control-panel`

### 7.4 C-Market

Role :

- hebergement de scripts Python lies aux algorithmes

Implantation dans le repo :

- VM `c-market-Dev1-S`
- type `DEV1-S`
- image `ubuntu_jammy`
- volume data `20 Go`
- reseau `app`
- SG : security group reseau standard

Note importante :

- cette VM est definie dans le repo
- son deploiement effectif depend du prochain `terraform apply`

### 7.5 Wazuh

Role :

- brique securite dediee de type `single-node all-in-one`
- Wazuh server
- Wazuh indexer
- Wazuh dashboard

Implantation :

- VM `wazuh-Dev1-S`
- type `BASIC2-A4C-8G`
- image `ubuntu_jammy`
- root volume `80 Go`
- volume data dedie `50 Go`
- reseau `app`
- SG dedie `sg-wazuh`
- `protected = true`

### 7.6 WireGuard

Role :

- acces VPN / management / overlay
- hub WireGuard a double interface (`wg0` et `wg1`)
- routage entre admins, routeurs edge et reseau prive `10.42.0.0/16`

Implantation :

- VM `wireguard-DEV1-S`
- type `DEV1-S`
- image `ubuntu_jammy`
- volume data `10 Go`
- reseau `app`
- SG dedie `sg-wireguard`

### 7.7 Monitoring

Role :

- brique de supervision `Grafana + Loki + Mimir + Alloy`

Implantation :

- VM `monitoring-DEV1-S`
- type `DEV1-M`
- image `ubuntu_jammy`
- root volume `20 Go`
- volume data `30 Go`
- reseau `app`
- SG dedie `sg-monitoring`
- `protected = true`

Stockage associe :

- bucket Object Storage prive dedie a Mimir

### 7.8 Broker

Role :

- broker central NATS / MQTT / flux d'integration

Implantation :

- VM `broker-DEV1-S`
- type `DEV1-S`
- image `ubuntu_jammy`
- volume data via module `scaleway-instance`
- reseau `app`
- SG dedie `sg-broker`

### 7.9 Telemetry DB

Role :

- base de donnees Telemetry

Implantation :

- `scaleway_rdb_instance`
- engine `PostgreSQL-15`
- type `DB-DEV-S`
- reseau `data`
- sauvegardes non desactivees
- IP privee geree par IPAM

## 8. Stockage

### 8.1 Volumes attaches

Volumes declares explicitement :

- Vault -> `10 Go`
- Docmost -> `20 Go`
- Control Panel -> `20 Go`
- C-Market -> `20 Go`
- Wazuh -> `50 Go` data + `80 Go` root
- WireGuard -> `10 Go`
- Monitoring -> `30 Go` data + `20 Go` root
- Broker -> volume data via module, taille par defaut du module si non surchargee

### 8.2 Object Storage Mimir

Le repo cree aussi :

- un bucket Object Storage prive dedie a Mimir
- un ACL prive explicite sur ce bucket

Ce bucket sert de backend de stockage long terme pour la stack monitoring.

### 8.3 Base Telemetry

La base Telemetry est un service RDB managé, pas une VM. Son stockage n'est pas
decrit ici comme un block volume local d'instance.

## 9. Security groups et exposition reseau

## 9.1 Security group reseau standard

Applique notamment a :

- Vault
- Docmost
- C-Market

Politique :

- inbound par defaut `drop`
- outbound par defaut `accept`
- `enable_default_security = false`

Ouvertures importantes modelisees aujourd'hui :

- `22/TCP` depuis `mgmt_cidrs`
- `22/TCP` depuis `0.0.0.0/0` via regle additionnelle
- `51820/UDP` ouvert
- tout le trafic `10.42.0.0/16`
- tout le trafic `10.8.0.0/24`
- `8200/TCP` public pour Vault
- `80/TCP` public
- `443/TCP` public
- `8080/TCP` public

Conclusion :

- ce SG est fonctionnel mais large
- il ne correspond pas encore a une posture "production minimal exposure"

## 9.2 SG Control Panel

Politique :

- inbound `drop`
- outbound `accept`

Ouvertures :

- `22/TCP` depuis `0.0.0.0/0`
- `443/TCP` depuis `10.8.0.0/24`
- `443/TCP` depuis `mgmt_cidrs`
- `9100/TCP` depuis `10.42.1.4/32` pour le scrape `node_exporter`

Note :

- l'ouverture SSH mondiale est explicitement temporaire dans le code

## 9.3 SG Broker

Politique :

- inbound `drop`
- outbound `accept`

Ouvertures :

- `8883/TCP` public
- `80/TCP` public
- `443/TCP` public
- `4222/TCP` depuis `10.42.1.0/24`
- `8222/TCP` depuis `10.42.1.0/24`
- `8443/TCP` public
- `9443/TCP` uniquement depuis l'IP publique du control panel
- `51820/UDP` public
- `8888/TCP` depuis `10.8.0.0/24`
- `22/TCP` depuis `10.8.0.0/24`
- `22/TCP` public
- `9100/TCP` depuis `10.42.1.4/32` pour le scrape `node_exporter`

## 9.4 SG Wazuh

Politique :

- inbound `drop`
- outbound `accept`

Ouvertures :

- `22/TCP` depuis `10.8.0.0/24` et `mgmt_cidrs`
- `22/TCP` public temporairement
- `443/TCP` depuis `10.8.0.0/24` et `mgmt_cidrs`
- `9100/TCP` depuis `10.42.1.4/32` pour le scrape `node_exporter`
- `1514/TCP` depuis `10.8.0.0/24`
- `1515/TCP` depuis `10.8.0.0/24`
- `1514/TCP` depuis `allowed_wazuh_ipc_public_cidrs`
- `1515/TCP` depuis `allowed_wazuh_ipc_public_cidrs`
- `55000/TCP` seulement depuis l'IP publique du control panel

Etat actuel du repo :

- `allowed_wazuh_ipc_public_cidrs = []`
- donc aucun fallback public n'est ouvert par defaut pour l'enrollment Wazuh

## 9.5 SG Monitoring

Politique :

- inbound `drop`
- outbound `accept`

Ouvertures :

- `22/TCP` depuis `10.8.0.0/24` et `mgmt_cidrs`
- `22/TCP` public temporairement
- `3000/TCP` depuis `10.8.0.0/24` et `mgmt_cidrs`
- `3100/TCP` depuis `10.42.0.0/16`
- `3100/TCP` depuis `10.8.0.0/24`
- `9009/TCP` depuis `10.8.0.0/24`

Conclusion :

- Grafana reste l'unique point d'acces humain principal
- Loki et Mimir restent exposes seulement en prive / VPN

## 9.6 SG WireGuard

Politique :

- inbound `drop`
- outbound `accept`

Ouvertures :

- `22/TCP` depuis `mgmt_cidrs`
- `22/TCP` public
- `51820/UDP` public pour `wg0`
- `51821/UDP` public pour `wg1`
- trafic `TCP/UDP/ICMP` depuis `10.42.0.0/16`

Conclusion :

- `51821/UDP` n'est expose que sur la VM WireGuard
- le repo supporte maintenant `wg0` et `wg1` sans reutiliser le SG reseau standard

## 10. Flux principaux

### 10.1 Admin -> Infra

Chemins d'acces :

- acces via Internet direct selon SG
- acces via WireGuard `10.8.0.0/24`

Le repo privilegie l'usage du reseau WireGuard comme couche d'acces privee,
mais plusieurs ouvertures publiques existent encore dans le code.

### 10.2 Terraform -> Vault -> Scaleway

Flux :

- script `plan_terraform.sh` / `apply_terraform.sh`
- login AppRole sur Vault
- lecture du secret `secret/scaleway`
- initialisation du provider Scaleway
- operations Terraform vers l'API Scaleway

### 10.3 Control Panel -> Broker

Flux porte par le repo :

- `9443/TCP` autorise seulement depuis l'IP publique du control panel

### 10.4 Control Panel -> Wazuh

Flux porte par le repo :

- `55000/TCP` autorise seulement depuis l'IP publique du control panel

### 10.5 IPC / Sites -> Wazuh

Flux cibles :

- `1514/TCP`
- `1515/TCP`

Chemins supportes dans le repo :

- via `10.8.0.0/24`
- via une allowlist publique explicite si `allowed_wazuh_ipc_public_cidrs`
  est renseignee

Etat courant du repo :

- fallback public desactive par defaut

### 10.6 VMs applicatives -> Broker

Les VMs `app` comme :

- control-panel
- c-market
- monitoring
- docmost

peuvent communiquer avec le broker via :

- le reseau prive `app`
- ou ses ports publics selon les SG et l'usage effectif

Note importante :

- ce repo ne definit pas de firewall local Linux
- seules les security groups Scaleway sont modelisees ici

### 10.7 Monitoring -> VMs scrape `node_exporter`

Flux portes par le repo :

- `monitoring-DEV1-S` scrappe les VMs via leurs IPs privees `10.42.x.x`
- `9100/TCP` est autorise depuis `10.42.1.4/32` sur les VMs a SG dedie :
  - control-panel
  - broker
  - wazuh

Implication :

- `9100/TCP` n'est pas expose publiquement
- les VMs sur SG reseau standard ou SG WireGuard n'ont pas besoin d'une regle
  supplementaire pour ce flux prive

## 11. SSH et cles

Le repo maintient un bloc `cloud-init` commun avec les cles publiques
autorisees.

Cles communes actuellement injectees :

- `~/.ssh/publickeyopenssh.pub`
- `~/.ssh/Luc.pub`
- `~/.ssh/id_ed25519.pub`
- la cle ED25519 `loris@cascadya`

Point d'exploitation important :

- le module `scaleway-instance` ignore les changements de `user_data`
- donc l'ajout d'une nouvelle cle profite automatiquement aux nouvelles VMs
- les VMs deja creees ne recoivent pas automatiquement la nouvelle cle via
  Terraform seul

## 12. Sorties Terraform utiles

Sorties actuellement exposees :

- `vault_ipv4`
- `wireguard_ipv4`
- `wireguard_private_ip`
- `control_panel_ipv4`
- `control_panel_private_ip`
- `docmost_private_ip`
- `broker_ipv4`
- `broker_private_ip`
- `broker_private_ipv6`
- `c_market_ipv4`
- `c_market_private_ip`
- `wazuh_ipv4`
- `wazuh_private_ip`
- `monitoring_ipv4`
- `monitoring_private_ip`
- `mimir_bucket_name`
- `mimir_bucket_endpoint`
- `mimir_bucket_region`
- `mimir_internal_url`
- `loki_internal_url`
- `vault_private_ip`
- `telemetry_db_host`
- `telemetry_db_port`
- `telemetry_db_name`

## 13. Fonctionnalites effectivement couvertes par le repo

Le repo couvre deja :

- creation du reseau principal Scaleway
- creation des Private Networks
- creation des IPs publiques de VM
- creation des VMs principales du lab
- creation des volumes data
- creation des SG standards et dedies
- creation de la base Telemetry
- lecture des secrets cloud depuis Vault
- injection de cles SSH via cloud-init

Le repo ne couvre pas encore completement :

- le deploiement applicatif dans chaque VM
- la propagation des nouvelles cles SSH vers les anciennes VMs
- un hardening reseau fin de type production
- un modele general de sauvegardes/snapshots pour toutes les VMs
- des firewalls Linux internes aux machines
- une HA ou segmentation multi-environnements

## 14. Limites et points de vigilance

### 14.1 Exposition publique large

Le SG reseau standard et certains SG dedies exposent encore plusieurs ports
publiquement. C'est utile pour les phases de construction et d'integration,
mais plus large que la cible finale minimaliste.

### 14.2 SSH public

Le control panel, monitoring, Wazuh et WireGuard gardent chacun au moins une
ouverture `22/TCP` publique temporaire dans leur SG dedie ou partage.

### 14.3 Cles SSH

L'ajout de la cle `loris@cascadya` est present dans le code, mais cela ne
reconfigure pas automatiquement les VMs deja en place.

### 14.4 Wazuh public fallback

Le repo modele la logique de fallback public Wazuh, mais la liste est vide par
defaut. Toute ouverture publique ponctuelle doit etre explicite et revue.

### 14.5 C-Market

`c-market-Dev1-S` est bien declare dans le repo, mais son existence effective
depend du prochain apply de l'environnement `dev`.

## 15. Synthese executive

L'architecture actuelle du repo `Infra-MVP` repose sur un VPC Scaleway simple,
avec un reseau `app` central pour les VMs applicatives, un reseau `data` pour
les briques plus sensibles, un broker central, un control panel dedie, une
base Telemetry privee, une VM Wazuh dediee, et des acces admin partiellement
portes par WireGuard.

Cette architecture est deja fonctionnelle pour :

- faire vivre un lab `dev`
- connecter des briques applicatives entre elles
- exposer des services centraux via IP publique et SG
- maintenir une base d'administration et de supervision
- exposer deux plans WireGuard distincts (`wg0` et `wg1`)
- preparer un scrape monitoring prive des VMs via `node_exporter`

Elle reste cependant une architecture de travail / integration, pas encore une
cible de production durcie. Les principaux axes de maturite a venir sont :

- reduction des expositions publiques
- durcissement SSH
- propagation d'acces et de secrets sur les VMs deja existantes
- modelisation plus stricte des flux Wazuh / IPC
- verification runtime de `node_exporter` sur chaque VM cible
- backup / snapshots standardises
