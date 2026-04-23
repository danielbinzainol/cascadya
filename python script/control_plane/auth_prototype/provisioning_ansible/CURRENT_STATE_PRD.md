# PRD - Systeme Cascadya

## 1. Objet du document

Ce document fige une vision complete de l'etat du systeme Cascadya au
21/04/2026.

Il ne sert pas seulement a decrire l'IPC. Il sert a :

- montrer ce qui a ete construit sur l'ensemble de la chaine
- distinguer ce qui est valide en reel de ce qui est seulement prepare
- relier les briques edge, cloud, reseau, telemetrie, OTA et securite
- relier aussi les briques IAM, portail, DNS interne et acces prive
- donner un point de reference clair avant la prochaine phase

Ce document est volontairement ancre dans les faits observes, les tests menes et
les composants effectivement produits.

## 2. Resume executif

Le systeme Cascadya actuel couvre des briques deja solides :

- installation zero-touch d'un IPC via cle USB
- layout disque Mender A/B reproductible
- partition `/data` separee et chiffree en LUKS
- auto-unlock local TPM2 pour `/data`
- persistance de l'etat Mender sur `/data`
- mise a jour OTA Mender validee
- architecture de messagerie securisee par mTLS
- gateway edge Modbus <-> broker
- pipeline de telemetrie edge -> broker -> base -> Grafana
- preuve de faisabilite du remote unlock via broker + Vault
- industrialisation progressive par Ansible
- stack `Control Panel` expose en prive via `Traefik + WireGuard`
- `Wazuh` et `Grafana` publies sous des hostnames internes dedies
- migration de `Keycloak` vers la VM Vault pour une identite partagee
- emergence de `portal.cascadya.internal` comme hub d'acces unique

Le projet n'est plus au stade "proof of concept fragile". Il est dans un etat
de pre-industrialisation avancee.

La situation au 21/04/2026 est la suivante :

- la fondation IPC est validee
- le flux remote unlock est valide en `direct mode`
- le transport final `WireGuard + Teltonika + broker/Vault` reste a finaliser
- la telemetrie edge est desormais deployee proprement via le role
  `edge-agent` sur l'IPC cible
- la validation Ansible de deploiement de cette brique est acquise
- la cartographie Modbus, la lecture canonique du planificateur et le ciblage
  strict par IPC ont ete revalides manuellement sur le couple simulateur + IPC
- la table d'echange rev.2, le `CRC16` planificateur et le snapshot
  `read_plan` sont maintenant alignes entre repo, gateway IPC et simulateur
- l'ecran web `Orders` du `Control Panel` a ete recable sur cette logique
  rev.2 puis redeploye sur `control-panel-DEV1-S`
- le mode Simulation/Reel est en place cote IPC avec un pare-feu memoire:
  les variables procede simulees utilisent `registre_simule = registre_reel + 9200`
- la validation terrain lab confirme `%MW9588 -> %MW388`,
  `%MW9708 -> %MW508` et `%MW9774 -> %MW574`, sans ecriture dans les
  registres terrain bas du simulateur
- une evolution `Device Profile / HAL` est cadree pour transformer LCI Rev02
  en premier profil fournisseur et preparer l'ajout futur d'autres chaudieres
  sans reecrire le gateway
- la chaine cloud `NATS -> TimescaleDB -> Grafana` et la supervision Wazuh sont
  materialisees dans le lab
- l'identite n'est plus locale au Control Panel : elle est en cours de
  convergence vers une brique partagee sur la VM Vault
- le portail devient la cible de point d'entree humain unique, meme si cette
  bascule n'est pas encore totalement terminee

## 3. Contexte produit et probleme traite

Le systeme devait resoudre simultanement plusieurs problemes :

- installer de facon repetitive des IPC industriels
- permettre une maintenance logicielle OTA sans reinstallation manuelle
- proteger les donnees persistantes
- conserver l'etat applicatif et Mender entre les reboots et les mises a jour
- assurer un flux de commande et de telemetrie fiable entre edge et cloud
- preparer un mecanisme de deverrouillage distant plus robuste que le TPM local
  seul

Le produit vise donc une chaine complete :

- edge industriel
- reseau prive / VPN
- broker central
- persistence cloud
- observabilite
- securite
- outillage d'exploitation

## 4. Chronologie de construction

### 4.1 27/02/2026

Travaux realises :

- creation de playbooks Ansible dedies aux differents certificats
  (`server`, `client`, `app/user`) avec des configurations distinctes selon les
  usages
- tests de transmission des donnees via VPN au lieu d'IP publique
- creation d'un script client universel base sur une variable d'identite
- mise en place d'un watchdog pour maintenir le dispatcher sur la VM
- ajout de commandes de pause, arret et redemarrage du dispatcher
- separation de `terraform_run.sh` en `terraform_plan.sh` et
  `terraform_apply.sh`
- modification des regles VM broker pour autoriser les flux dans les deux sens
- passage a l'usage d'un nom `BROKER_HOST` plutot qu'une IP directe

Impact :

- la brique PKI devient plus industrialisable
- le routage edge multiclient devient plus propre
- l'infrastructure cloud commence a etre exploitable de maniere stable

### 4.2 02/03/2026

Travaux realises :

- documentation de la VM broker Mosquitto
- separation des flux aller et retour en deux services watchdog distincts
- stress test MQTT sur la VM broker
- benchmark NATS Core en remplacement du dispatch Python
- activation de JetStream pour la persistence
- stress test de reconnexion JetStream
- setup WireGuard et scripts de test de reception
- developpement d'un generateur asynchrone pour simuler 200 sites
- validation des flux `1-to-Many` et `Many-to-One`

Resultats mesures :

- cible initiale MQTT : `2000 msg/s`
- limite stable MQTT observee : `1000-1100 msg/s`
- goulot d'etranglement MQTT : saturation CPU sur `2 vCPU`
- RAM non limitante : `447M / 1.91G`
- NATS Core stable a `4000 msg/s`
- charge CPU VM sous NATS : `2-3 %`
- JetStream en reconnexion : `15000 a 27700 msg/s`

Capacite validee sur MQTT :

- `1000` sites a `1 msg/s`
- `500` sites a `2 msg/s`
- `100` sites a `10 msg/s`

Decision d'architecture :

- NATS / JetStream devient la direction privilegiee

### 4.3 03/03/2026

Travaux realises :

- integration de Tailscale sur le poste Windows
- acces SSH reussi vers l'equipement industriel via l'IP VPN
- creation de benchmarks NATS vs MQTT
- tests `One-to-Many` et `Many-to-One`
- mesures de latence en conditions reelles

Resultats observes :

- RTT stable sous NATS d'environ `37 ms` depuis le WSL
- RTT stable sous NATS d'environ `55 ms` depuis le PC industriel
- latence et charge CPU largement meilleures qu'avec MQTT

Decision d'architecture :

- validation definitive de NATS / JetStream comme backbone cible

### 4.4 04/03/2026

Travaux realises :

- mise en place du VPN site-to-site WireGuard avec routeur Teltonika
- contournement du CGNAT via `PersistentKeepalive = 25`
- declaration du routeur comme peer sur la VM cloud
- alignement du LAN industriel en `192.168.50.0/24`
- restauration du simulateur Modbus
- creation de la gateway edge `gateway_modbus_sbc.py`
- validation du routage SSH en cascade
- creation d'un chrono ping a travers toute l'architecture
- developpement d'une IHM Python/WSLg

Resultats observes :

- routage interne valide jusqu'au simulateur
- RTT moyen bout en bout d'environ `70 ms`
- integrite des donnees validee a `100 %`
- architecture capable de soutenir le watchdog a `1 Hz`

### 4.5 05/03/2026

Travaux realises :

- refonte du simulateur Modbus en jumeau numerique modulaire
- creation d'une machine a etats pour les IBC
- developpement du moteur physique
- orchestration des regles de cascade
- gestion FIFO des ordres
- deployment systemd du simulateur
- creation d'un monitor CLI
- creation d'un injecteur de charge

Impact :

- le simulateur devient un vrai support de validation systeme
- les tests ne reposent plus sur un mock monolithique simpliste

### 4.6 06/03/2026

Travaux realises :

- refonte du controle-commande Modbus
- zone de preparation stricte `%MW0-%MW16`
- FIFO plus robuste et codes d'etat precis
- evolution de la gateway vers une API request/reply NATS
- ajout du watchdog `%MW620`
- ajout de la surveillance d'horloge `%MW607`
- creation de `telemetry_publisher.py`
- mise en place du pont `nats_to_timescale.py`
- transformation de la table en hypertable TimescaleDB
- integration Grafana

Impact :

- le systeme couvre a la fois les ordres, la supervision, la persistence cloud
  et la visualisation

### 4.7 10/03/2026

Travaux realises :

- ajout de `active_order` en base
- transformation de `nats_to_timescale.py` en service systemd
- resolution d'un conflit memoire Modbus sur `%MW100`
- premiere tentative de migration de `active_strategy` hors de `%MW100`
- ajustements sur l'IHM et Grafana

Impact :

- la telemetrie strategique est stabilisee
- le pipeline cloud devient continu et exploitable 24/7

### 4.8 16/03/2026

Travaux realises :

- validation OTA Mender A/B
- validation du commit final
- chiffrement de `/data` avec LUKS
- enrollment TPM2 via `systemd-cryptenroll`
- regeneration `initramfs`
- refonte de l'installateur USB zero-touch
- correction des blocages `emergency mode`
- persistance de `/var/lib/mender` sur `/data`
- correction de problemes `apt/dpkg` dans les builds

Impact :

- la fondation industrielle de l'IPC est consideree comme validee

### 4.9 17/03/2026

Travaux realises :

- validation du flux de remote unlock en dry-run
- generation et deploiement Ansible des certificats de boot unlock
- provisioning AK TPM
- deploiement du script d'unlock, du helper et de l'unit systemd
- structuration des playbooks `preflight`, `bootstrap`, `validate`,
  `cutover`, `remove-local-tpm`
- demonstration `direct mode` avec broker + Vault sur laptop
- documentation operatoire et PRD de l'etat courant
- ajout du cadre de deploiement telemetrie `edge-agent` via Ansible

Resultat cle :

- `Dry-run remote unlock completed successfully.`

### 4.10 14/04/2026

Travaux realises :

- revalidation manuelle du chemin `WSL -> simulateur Modbus -> IPC`
- correction definitive de la collision memoire entre planificateur et runtime
- stabilisation de la pile planificateur canonique en `%MW100-%MW396`
- deplacement du runtime actif en `%MW700-%MW704`
- durcissement de `gateway_modbus_sbc.py` :
  - refus des payloads incomplets
  - relecture de la zone de preparation avant activation
  - lecture canonique `read_plan`
  - ciblage strict par IPC
- alignement de `telemetry_publisher.py` sur la nouvelle cartographie runtime

Impact :

- la chaine `Control Panel / broker / gateway / simulateur` devient beaucoup
  plus fiable a diagnostiquer
- le comportement Modbus cote edge est mieux borne et moins sujet aux ambiguities
- les scripts versions dans le repo correspondent enfin a l'etat teste en lab

### 4.11 15/04/2026 - 17/04/2026

Travaux realises :

- migration de `Keycloak` hors du `Control Panel` vers la VM `vault-DEV1-S`
- publication de `auth.cascadya.internal` sur Vault
- recablage progressif des clients OIDC :
  - `control-panel-web`
  - `cascadya-features-web`
  - `grafana-monitoring`
  - portail en cours de convergence
- diagnostic puis correction de plusieurs regressions d'acces prive :
  - split DNS local sur `control-panel-DEV1-S`
  - NAT `wg0 -> ens5` sur `wireguard-DEV1-S`
  - allowlists `Traefik` apres NAT
  - publication DNS interne des hostnames `.cascadya.internal`
- revalidation de :
  - `control-panel.cascadya.internal`
  - `wazuh.cascadya.internal`
  - `grafana.cascadya.internal`
  - `portal.cascadya.internal`
  - `auth.cascadya.internal`
- formalisation de la cible `portal first` pour faire du portail le point
  d'entree humain principal

Impact :

- l'IAM devient mutualisable entre plusieurs services au lieu d'etre embarque
  localement dans le Control Panel
- les chemins d'acces internes deviennent plus clairs et plus proches d'un SI
  exploitable
- le projet ne couvre plus seulement l'edge et la telemetrie, mais aussi
  l'administration, l'identite et l'acces aux outils

### 4.12 20/04/2026

Travaux realises :

- alignement du flux Modbus sur la table d'echange rev.2 ;
- durcissement complementaire de `gateway_modbus_sbc.py` avec :
  - validation des mots `C1-1..C3-3` selon les profils `2.5.*`, `3.0.0`,
    `4.0.0`, `5.5.*`, `6.0.0`
  - calcul `CRC16` du planificateur
  - enrichissement du snapshot `read_plan` avec profil, pression, secours et
    `CRC16`
- realignement du simulateur `scheduler.py` sur les contraintes rev.2 ;
- enrichissement de `monitor.py` avec l'affichage du profil de tete de file et
  du `CRC16` ;
- recablage de l'ecran `Orders` du `Control Panel` sur :
  - les champs rev.2 de la table d'echange
  - une validation locale des bornes et obligations par profil
  - la previsualisation `CRC16`
  - l'action `read_plan` et son tableau de snapshot ;
- redeploiement du frontend `Vue` sur `control-panel-DEV1-S` avec build
  production reussi ;
- redeploiement du gateway sur l'IPC ;
- redeploiement du simulateur Modbus sur `simulateur-modbus`.

Validations observees :

- build frontend `Vue` reussi sur `control-panel-DEV1-S` ;
- service `control-panel-auth.service` redemarre correctement apres build ;
- presence verifiee sur l'IPC de `PROFILE_RULES`,
  `_validate_exchange_table`, `read_plan` et `planner_crc16` dans
  `gateway_modbus_sbc.py` ;
- presence verifiee sur le simulateur de `PROFILE_RULES`,
  `_decode_order_controls`, `planner_crc16` et de l'affichage
  `Queue Head Profile` ;
- validation manuelle depuis l'IPC d'un `upsert` rev.2 `ok` avec :
  - `mode_profile_code = 5`
  - `mode_profile_label = "5.5.*"`
  - `power_limit_kw = 400`
  - `met_activation = 5`
  - `met_type = 2`
  - `secours_enabled = true`
- validation manuelle du snapshot `read_plan` avec :
  - `count = 1`
  - `planner_crc16 = 13849`
  - `crc16 = 13849` sur l'ordre lu
  - `register_base = 100`
- validation de la RAZ planificateur avec pile vide en `%MW100+` ;
- confirmation que la RAZ ne remet toujours pas a zero le runtime actif en
  `%MW700+`, ce qui reste le comportement courant du simulateur.

Impact :

- les scripts versionnes et deployes sur site, IPC et simulateur sont de
  nouveau coherents entre eux ;
- le `Control Panel` expose enfin un ecran `Orders` qui parle la meme grammaire
  que le gateway edge ;
- la chaine de validation rev.2 devient exploitable pour les tests operateur et
  les demonstrations techniques.

### 4.13 21/04/2026

Travaux realises :

- finalisation du mode operationnel Simulation/Reel dans le gateway IPC ;
- ajout des variables systemd de mode via drop-ins :
  - `MODBUS_SIM_PROCESS_OFFSET=9200`
  - `MODBUS_REAL_HOST=192.168.1.52`
  - `MODBUS_REAL_PORT=502`
  - mapping terrain `%MW388`, `%MW390`, `%MW392`, `%MW508`, `%MW512`,
    `%MW514`, `%MW516`, `%MW574`, `%MW576`
- enrichissement du simulateur Modbus avec `rev02_process.py` pour exposer un
  miroir procede Rev02 decale ;
- confirmation que le simulateur n'ecrit pas dans les registres terrain bas :
  `%MW388-%MW392`, `%MW508-%MW516` et `%MW574-%MW576` restent a `0` dans le
  simulateur ;
- confirmation que la zone haute simulation porte les valeurs dynamiques :
  `%MW9588-%MW9592`, `%MW9708-%MW9716`, `%MW9774-%MW9776` ;
- correction du snapshot IPC pour propager `pressure_maps_to`, ce qui permet a
  l'IHM d'afficher clairement `%MW9588 -> %MW388` ;
- redemarrage reussi du simulateur Modbus apres expiration des etats TCP
  `FIN-WAIT-2` / `TIME-WAIT` sur le port `502`.

Validations observees :

- `control-panel-auth.service` actif et endpoints locaux `/healthz` et
  `/auth/login` OK sur `127.0.0.1:8000` ;
- `gateway_modbus.service` actif avec drop-in `operation-mode-lci.conf` ;
- `telemetry_publisher.service` actif avec drop-in `operation-mode-lci.conf` ;
- `modbus-serveur.service` actif avec `LISTEN 0.0.0.0:502` ;
- snapshot IPC en mode `simulation` retourne :
  - `pressure_register_label = "%MW9588"`
  - `pressure_maps_to = "%MW388"`
  - `telemetry_profile = "digital_twin"`

Impact :

- la demonstration peut maintenant expliquer les registres reels LCI et leurs
  equivalents simules sans exposer l'automate physique ;
- la separation OT de securite est claire : les ordres Rev02 restent identiques,
  mais les variables procede de simulation sont decalees ;
- le passage en mode Reel reste bloque par confirmation `LCI LIVE` et attend
  encore la connectivite terrain vers `192.168.1.52:502`.

## 5. Vision cible du produit

Le produit cible est une plateforme edge securisee et industrialisee capable de :

- demarrer automatiquement sur SSD
- maintenir un cycle de mise a jour robuste
- proteger les donnees au repos
- publier sa telemetrie et recevoir des ordres a travers un backbone securise
- s'integrer a un broker central et a un backend de persistence
- permettre un deverrouillage distant conditionnel et controle

## 6. Architecture globale du systeme

### 6.1 IHM operateur

Role :

- centre de commande
- configuration et envoi des ordres
- supervision et affichage des acquittements

Implementation actuelle dans le repo produit :

- interface web `Control Panel` pour les ecrans `Orders` / `Execution`
- backend `FastAPI`
- frontend `Vue`
- probe broker HTTPS + `NATS request/reply`

Historique important :

- une IHM Python / WSLg a bien existe dans le lab ;
- elle n'est plus la reference active du repo produit.

### 6.2 Gateway edge sur IPC

Role :

- traduire les ordres NATS en operations Modbus
- traduire l'etat Modbus en messages NATS de telemetrie
- maintenir le watchdog industriel

Implementation actuelle :

- `auth_prototype/provisioning_ansible/roles/edge-agent/files/src/agent/gateway_modbus_sbc.py`
- `auth_prototype/provisioning_ansible/roles/edge-agent/files/src/agent/telemetry_publisher.py`
- runtime cible sur `/data/cascadya/agent`
- services cibles : `gateway_modbus.service`,
  `telemetry_publisher.service`

### 6.3 Simulateur / Digital Twin

Role :

- reproduire la logique de cascade
- simuler la thermodynamique
- servir de banc de validation des flux

Implementation actuelle :

- architecture modulaire multi-fichiers
- modele de chaudiere
- moteur physique
- ordonnanceur FIFO
- service systemd

### 6.4 Broker cloud

Role :

- routage des messages
- securisation mTLS
- diffusion des ordres
- aggregation des retours

Evolution :

- Mosquitto documente et benchmarke
- NATS Core valide comme architecture plus performante
- JetStream active pour la persistence

### 6.5 Persistence cloud

Role :

- ingest telemetrie continue
- historique exploitable par supervision

Implementation actuelle :

- `nats_to_timescale.py`
- service systemd sur VM
- PostgreSQL / TimescaleDB
- hypertable et index temporels

### 6.6 Observabilite cloud

Role :

- exploitation visuelle
- supervision operationnelle
- analyse des performances et etats

Implementation actuelle :

- Grafana
- datasource PostgreSQL
- dashboards pression, demande, charge et strategie

### 6.7 Reseau et securite

Composants :

- mTLS
- PKI reutilisee entre plusieurs briques
- Tailscale pour certains acces VPN
- WireGuard
- Teltonika RUTX50
- routage prive edge <-> cloud

## 7. Flux fonctionnels du systeme

### 7.1 Flux commande `1-to-Many`

Description :

- une IHM centrale emet un ordre
- le broker le route
- l'edge recoit l'ordre
- la gateway l'ecrit en Modbus
- le systeme renvoie un acquittement

### 7.2 Flux telemetrie `Many-to-One`

Description :

- l'edge lit l'etat physique ou simule
- publie la telemetrie a `1 Hz`
- le broker route
- le pont cloud insere en base
- Grafana affiche

### 7.3 Flux remote unlock

Description :

- l'IPC contacte un broker d'unlock
- presente son certificat client
- envoie un challenge TPM et des metadonnees
- le broker consulte Vault
- le secret de deverrouillage est libere si la politique l'autorise

### 7.4 Flux OTA

Description :

- l'image standby est mise a jour
- le systeme reboot sur le slot cible
- `/data` reste coherent
- l'artefact est ensuite commit

## 8. Choix d'architecture et rationale

### 8.1 NATS / JetStream au lieu de MQTT/Mosquitto

Raisons :

- bien meilleure capacite de debit
- bien moindre charge CPU
- routage natif plus simple
- persistence JetStream plus robuste

### 8.2 `/data` persistant et separe du rootfs

Raisons :

- survivre aux bascules Mender A/B
- conserver l'etat Mender
- conserver les donnees applicatives et les certificats runtime

### 8.3 LUKS + TPM2

Raisons :

- chiffrer reellement les donnees
- autoriser un auto-unlock local securise
- preparer l'attestation vers le remote unlock

### 8.4 Ansible comme chaine d'industrialisation

Raisons :

- reproductibilite
- segmentation par phases
- deploiement propre des certificats, scripts et services
- documentation operatoire plus fiable

## 9. Etat actuel des composants

### 9.1 Fondations IPC

Valide :

- installateur USB zero-touch
- SSD bootable
- layout Mender A/B
- `/data` chiffre en LUKS
- TPM2 local pour `/data`
- persistance Mender
- OTA + commit

### 9.2 Remote unlock

Valide :

- generation des certificats
- staging sur l'IPC
- provisioning AK TPM
- script et unit de remote unlock
- validation dry-run en `direct mode`

Prepare mais non encore finalise :

- transport WireGuard cible
- passage via routeur Teltonika
- retrait du token local TPM
- verification cryptographique forte cote broker

### 9.3 Telemetrie edge

Valide historiquement hors role cible :

- gateway Modbus <-> broker fonctionnelle
- telemetrie a `1 Hz`
- usage NATS securise en mTLS

Prepare dans le repo cible :

- role Ansible `edge-agent`
- scripts de reference versionnes
- templates systemd de reference
- runtime persistant cible sous `/data/cascadya/agent`
- playbooks de deploy et de validation

Valide sur la chaine Ansible actuelle :

- deploiement terrain via `edge-agent-deploy.yml`
- presence confirmee sur l'IPC de `/data/cascadya/agent`,
  `/data/cascadya/agent/certs` et `/data/cascadya/venv`
- deploiement confirme des scripts `gateway_modbus_sbc.py` et
  `telemetry_publisher.py`
- deploiement confirme du bundle TLS runtime
- installation et activation systemd confirmees pour `gateway_modbus.service`
  et `telemetry_publisher.service`
- verification de deploiement confirmee via
  `edge-agent-validate.yml -e edge_agent_expect_runtime_connectivity=false`

Clarification du 14 avril 2026 :

- `gateway_modbus_sbc.py` est le traducteur JSON/NATS -> Modbus actuellement
  versionne dans le repo ;
- la zone de preparation validee reste `%MW0-%MW16`, avec les bits/statuts
  `%MW50/%MW51`, `%MW60/%MW61`, `%MW62/%MW63` et les watchdogs `%MW607` /
  `%MW620` ;
- la pile planificateur canonique est exposee en `%MW100-%MW396`, avec
  `15` emplacements de `20` mots pour ne pas collisionner avec les zones
  telemetrie du SBC ;
- le runtime actif a ete deplace en `%MW700-%MW704` avec la cartographie :
  `%MW700=active_strategy_code`, `%MW701=active_order_id_lo`,
  `%MW702=active_order_id_hi`, `%MW703=target_pressure_modbus`,
  `%MW704=active_stages` ;
- `telemetry_publisher.py` lit aujourd'hui les registres `400`, `500`,
  `%MW700-%MW704`, `410`, `420` et `430` avant publication sur
  `cascadya.telemetry.live` ;
- `gateway_modbus_sbc.py` rejette maintenant les payloads incomplets
  (`missing_id`, `missing_execute_at`, consignes absentes) et relit
  `%MW0-%MW16` avant d'activer `%MW50` ou `%MW60` ;
- `gateway_modbus_sbc.py` expose maintenant une lecture canonique du
  planificateur via l'action `read_plan` / `queue_snapshot` / `list_orders` ;
- `gateway_modbus_sbc.py` impose maintenant un ciblage explicite des commandes
  du sujet partage `cascadya.routing.command` et n'accepte que les payloads
  cibles sur l'IPC courant via `asset_name`, `target_asset`,
  `edge_instance_id` ou `inventory_hostname` ;
- une commande sans cible est rejetee en `missing_target`, et une commande
  destinee a un autre IPC est rejetee en `target_mismatch`, sans ecriture
  Modbus ;
- la RAZ du planificateur vide la pile `%MW100+`, mais ne remet pas a zero le
  runtime actif en `%MW700+` ;
- l'ecran web `Orders` ne doit donc pas etre interprete comme une lecture
  canonique du planificateur Modbus tant que le backend/UI n'est pas
  explicitement recable sur cette lecture `read_plan`.

Validation manuelle reussie le 14 avril 2026 :

- redeploiement WSL -> simulateur Modbus -> IPC des scripts modifies ;
- validation du simulateur : `%MW100+` porte bien la pile et `%MW700+` le
  runtime, sans collision avec `400/420/430/500/602/620` ;
- validation IPC de `telemetry_publisher.py` avec lecture correcte de
  `active_order_id`, `active_strategy_code`, `target_pressure_bar` et
  `active_stages` ;
- validation IPC de `gateway_modbus_sbc.py` avec payload complet `ok`,
  payloads incomplets rejetes et snapshot canonique du planificateur retournant
  un ordre attendu en `register_base=100` ;
- validation IPC du ciblage strict : commande acceptee quand
  `asset_name=cascadya-ipc-10-109`, commande rejetee quand la cible pointe vers
  un autre IPC, et commande rejetee quand aucun champ cible n'est fourni.

Validation manuelle reussie le 20 avril 2026 :

- redeploiement du frontend `Orders` sur `control-panel-DEV1-S` avec build
  production reussi ;
- redeploiement du gateway sur l'IPC et du simulateur sur
  `simulateur-modbus` ;
- validation d'un `upsert` rev.2 `ok` depuis l'IPC avec
  `c1=[5,400,53]`, `c2=[5,2,53]`, `c3=[1,0,0]` ;
- validation d'un snapshot `read_plan` retournant :
  - `count = 1`
  - `planner_crc16 = 13849`
  - `mode_profile_label = "5.5.*"`
  - `register_base = 100`
- validation du monitor avec affichage `Queue Head Profile` et `CRC16` ;
- validation de la RAZ planificateur avec `%MW100-103 = [0, 0, 0, 0]` ;
- confirmation de la persistance du runtime actif en `%MW700+` apres RAZ,
  comportement a garder explicite dans les diagnostics.

Reste a valider en bout en bout avec le lab complet raccorde :

- connectivite NATS/TLS effective vers le broker cible
- stabilite de `gateway_modbus.service` si le simulateur ou le SBC cible tombe
  puis revient
- stabilite runtime des deux services sans boucle de restart
- absence d'erreurs de transport dans les journaux systemd

### 9.4 Cloud et supervision

Valide :

- NATS Core
- JetStream
- ingestion continue vers TimescaleDB
- dashboards Grafana

Clarification du 14 avril 2026 :

- la collecte host IPC via Alloy est validee vers la VM monitoring ;
- Alloy scrape actuellement uniquement `node_exporter` sur l'IPC ;
- le `remote_write` cible `http://10.42.1.4:9009/api/v1/push` ;
- les metriques edge JSON publiees par `telemetry_publisher.py` ne sont pas
  encore converties en metriques Prometheus par Alloy dans ce repo.

### 9.5 Control Panel, IAM et administration

Valide :

- `control-panel.cascadya.internal` est expose en prive via `Traefik`,
  `Waitress/FastAPI` et `WireGuard`
- la base `postgres-fastapi` supporte le RBAC metier, les utilisateurs miroir et
  l'audit
- le `Control Panel` consomme bien un flux OIDC externe au lieu d'un login
  purement local
- la surface admin et les APIs admin existent et sont suffisamment avancees pour
  servir de base a une migration vers le portail

Clarification d'avril 2026 :

- l'ancien `Keycloak` embarque dans le `Control Panel` n'est plus la cible
  d'architecture
- l'identite partagee est migree vers la VM Vault via
  `auth.cascadya.internal`
- le `Control Panel` doit evoluer d'application d'entree vers microservice
  metier derriere le portail
- l'ecran `Orders` du frontend `Vue` a ete recable sur la table d'echange
  rev.2, la previsualisation `CRC16` et la lecture `read_plan`, puis redeploye
  avec succes sur `control-panel-DEV1-S` le 20/04/2026
- la preuve fonctionnelle principale du lot `Orders` reste aujourd'hui une
  validation technique backend / IPC / simulateur, meme si le build frontend
  deploye est bien en place

### 9.6 Modbus Rev02, mode Simulation/Reel et preuve IPC

Valide le 21/04/2026 :

- la table d'echange Rev02 est la source de verite pour les ordres et le
  planificateur
- les zones d'ecriture commandes restent fixes :
  - preparation `%MW1000-%MW1043`
  - trigger ajout `%MW1044` et status `%MW1045`
  - trigger suppression `%MW1056` et status `%MW1057`
  - trigger reset `%MW1068` et status `%MW1069`
- la lecture planificateur reste fixe :
  - header `%MW8100-%MW8102`
  - 10 slots de 46 mots a partir de `%MW8120`
  - dernier slot a partir de `%MW8534`
- le simulateur conserve la zone sandbox `%MW9000+` pour pression, demande,
  etats IBC et runtime actif `%MW9070-%MW9074`
- le simulateur expose aussi un miroir des registres procede Rev02 dans
  `modbus_simulator/src/rev02_process.py`, afin de lire en simulation les
  memes familles de variables que sur l'automate LCI
- ce miroir ne touche pas les registres terrain bas; il applique la regle
  `registre_simule = registre_reel + 9200`
- le monitor terminal affiche maintenant les blocs procede Rev02 :
  `PT01/RP08`, niveaux/temperatures et sante PLC
- le mode Reel LCI cible maintenant l'automate documente
  `192.168.1.52:502`
- les valeurs `REAL Float32` Rev02 sont lues/ecrites en big-endian dans chaque
  mot, avec ordre des mots Modbus `mot bas puis mot haut`
  (`MODBUS_FLOAT_WORD_ORDER=low_word_first`)
- les valeurs `UDINT` Rev02, notamment les Order ID, sont lues/ecrites en
  `mot bas puis mot haut` (`MODBUS_U32_WORD_ORDER=low_word_first`)
- le bypass de validation pour essais PLC reste disponible mais verrouille: il
  exige `validation_mode=observe_only`, `allow_invalid_order_for_test=true` et
  `validation_bypass_reason=operator_requested_plc_security_test`; les
  restrictions Rev02 sont actives par defaut
- la telemetry Reel lit les registres terrain Rev02 :
  - `%MW257-%MW260` pour defauts/alarmes automate
  - `%MW388`, `%MW390.0`, `%MW392` pour la pression vapeur
  - `%MW508-%MW516` pour l'etat et la regulation RP08
  - `%MW574`, `%MW576.0` pour la recopie charge thermoplongeur
- `gateway_modbus_sbc.py` et `telemetry_publisher.py` sont installes sur
  `/data/cascadya/agent`, compiles et executes par systemd
- les drop-ins systemd `operation-mode-lci.conf` sont en place pour
  `gateway_modbus.service` et `telemetry_publisher.service`
- le controle runtime de mapping a retourne `REGISTER_MAPPING_REV02_OK`
- le simulateur `modbus-serveur.service` est actif avec `LISTEN 0.0.0.0:502`
- la validation locale simulateur a confirme :
  - `%MW388-%MW392 = [0, 0, 0, 0, 0]`
  - `%MW508-%MW516 = [0, 0, 0, 0, 0, 0, 0, 0, 0]`
  - `%MW574-%MW576 = [0, 0, 0]`
  - `%MW9588-%MW9592` contient une pression `PT01_MESURE` simulee lisible en
    `REAL Float32` avec mots Modbus inverses
- le snapshot IPC a confirme :
  - `pressure_register_label = "%MW9588"`
  - `pressure_maps_to = "%MW388"`
  - `telemetry_profile = "digital_twin"`
- le Control Panel expose un mode `restrictions Rev02 en veille` pour les tests
  de securite PLC :
  - les erreurs de validation restent affichees cote UI et gateway
  - la desactivation demande une confirmation operateur dans l'UI
  - le payload porte `validation_mode=observe_only`,
    `allow_invalid_order_for_test=true` et
    `validation_bypass_reason=operator_requested_plc_security_test`
  - le gateway ecrit quand meme `%MW1000-%MW1043` et pose `%MW1044`
  - le code final attendu vient du PLC/SBC via `%MW1045`

Clarification importante :

- le bouton Simulation/Reel ne change pas le contrat d'ecriture Rev02
- il change la cible Modbus, le profil de lecture telemetry, la zone memoire
  procede lue et la severite watchdog
- en Simulation, les variables procede sont lues dans la zone haute de type
  `%MW9588 -> %MW388`, `%MW9708 -> %MW508`, `%MW9774 -> %MW574`
- en Reel, les memes variables sont lues aux adresses natives LCI
- la connectivite terrain vers `192.168.1.52:502` reste a confirmer quand
  l'acces LCI sera ouvert
- tant que cette connectivite n'est pas disponible, `modbus_connect_failed`
  en mode Reel est attendu et ne remet pas en cause le mapping documentaire

Roadmap multi-fournisseurs :

- LCI Rev02 devient le premier `Device Profile` de reference;
- les adresses Modbus doivent progressivement sortir des scripts Python vers un
  profil versionne;
- le Control Panel doit afficher deux notions separees :
  - `Device profile`, par exemple `LCI Rev02`
  - `Mode`, par exemple `Simulation` ou `Reel`
- la premiere etape ne doit rien casser: le profil `lci_rev02` sera d'abord lu
  en comparaison avec les constantes actuelles avant de piloter le runtime;
- l'ajout d'un second fournisseur doit commencer par un profil simulation-only,
  sans ecriture automate reelle tant que les tests de non-regression ne sont pas
  passes.

### 9.7 Portail et point d'entree unique

Valide :

- `portal.cascadya.internal` est publie en prive
- le portail joue deja le role de hub de navigation entre les services
- les cartes existent pour les principaux outils :
  - Control Panel
  - Features
  - Grafana
  - Wazuh
  - Keycloak Admin

En cours de convergence :

- faire du portail le point d'entree humain canonique
- migrer la surface admin frontend vers le portail
- migrer l'API admin publique vers le portail
- faire passer les parcours utilisateurs par des routes de lancement portail
  plutot que par la memorisation de plusieurs URLs

### 9.8 DNS interne, reseau prive et publication des services

Valide :

- `dnsmasq` sur `wireguard-DEV1-S` sert les hostnames internes du lab
- les routes privees entre le reseau WireGuard `10.8.0.0/24` et le LAN
  `10.42.0.0/16` sont operationnelles avec NAT retour adapte
- les services suivants ont ete revalides via leurs DNS internes :
  - `control-panel.cascadya.internal`
  - `auth.cascadya.internal`
  - `wazuh.cascadya.internal`
  - `grafana.cascadya.internal`
  - `portal.cascadya.internal`

Lecon importante :

- une migration applicative ne suffit pas si le chemin d'acces prive
  `DNS + routage + NAT + allowlists Traefik` n'est pas lui aussi revalide

### 9.9 Wazuh et observabilite operateur

Valide :

- la VM Wazuh dediee existe et repond via `wazuh.cascadya.internal`
- `Grafana` est publie en prive via `grafana.cascadya.internal`
- le `Control Panel` expose deja une vue `Alerts` et des integrations
  d'observabilite en cours de consolidation

En cours :

- enrichir les alertes du `Control Panel` avec les signaux monitoring `Mimir /
  Alloy`
- mieux faire converger les parcours operateur entre portail, Grafana, Wazuh et
  Control Panel

## 10. Performances et capacite

### 10.1 Resultats Mosquitto / MQTT

- cible initiale : `2000 msg/s`
- stable observe : `1000 a 1100 msg/s`
- saturation CPU sur `2 vCPU`
- RAM non limitante

### 10.2 Resultats NATS Core

- `4000 msg/s` stables
- CPU VM a `2-3 %`

### 10.3 Resultats JetStream

- livraison / ack en reconnexion : `15000 a 27700 msg/s`

### 10.4 Latence terrain observee

- `~37 ms` RTT depuis WSL dans certains tests NATS
- `~55 ms` RTT depuis le PC industriel dans certains tests NATS
- `~70 ms` RTT moyen sur l'architecture complete WSL <-> broker <-> IPC <->
  simulateur

### 10.5 Abaque de capacite valide

- `1000` sites a `1 msg/s`
- `500` sites a `2 msg/s`
- `100` sites a `10 msg/s`

## 11. Livrables techniques produits

### 11.1 Infrastructure et scripts

- PKI multi-usages
- watchdogs de broker
- scripts benchmarks
- gateway edge
- telemetrie edge
- pont TimescaleDB
- simulateur digital twin

### 11.2 Industrialisation edge

- role `edge-agent`
- role `remote-unlock`
- role `network`
- role `tpm-luks-unlock`
- role `security-hardening`

### 11.3 Playbooks clefs

- [baseline-report.yml](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible\baseline-report.yml)
- [edge-agent-deploy.yml](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible\edge-agent-deploy.yml)
- [edge-agent-validate.yml](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible\edge-agent-validate.yml)
- [remote-unlock-bootstrap.yml](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible\remote-unlock-bootstrap.yml)
- [remote-unlock-preflight.yml](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible\remote-unlock-preflight.yml)
- [remote-unlock-validate.yml](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible\remote-unlock-validate.yml)

### 11.4 Documentation clef

- [CURRENT_STATE_OPERATING_PROCEDURE.md](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible\CURRENT_STATE_OPERATING_PROCEDURE.md)
- [REMOTE_UNLOCK_RUNBOOK.md](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible\REMOTE_UNLOCK_RUNBOOK.md)
- [REMOTE_UNLOCK_DEMO.md](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\cascadya-edge-os-images\ansible\REMOTE_UNLOCK_DEMO.md)

### 11.5 Architecture IAM et acces interne

- [PRD_MIGRATION_KEYCLOAK_VERS_VAULT_VM.md](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\python script\control_plane\auth_prototype\PRD_MIGRATION_KEYCLOAK_VERS_VAULT_VM.md)
- [PRD_MIGRATION_KEYCLOAK_VERS_VAULT_VM_AJUSTE_2026-04-15.md](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\python script\control_plane\auth_prototype\PRD_MIGRATION_KEYCLOAK_VERS_VAULT_VM_AJUSTE_2026-04-15.md)
- [PRD_DNS_INTERNE_SERVICE_VM.md](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\python script\control_plane\auth_prototype\PRD_DNS_INTERNE_SERVICE_VM.md)
- [PRD_PORTAL_COMME_POINT_ENTREE_UNIQUE_ET_ADMIN.md](c:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\python script\control_plane\auth_prototype\PRD_PORTAL_COMME_POINT_ENTREE_UNIQUE_ET_ADMIN.md)

## 12. Exigences satisfaites au 21/04/2026

- un IPC vierge peut etre installe de facon reproductible
- l'IPC supporte un cycle OTA Mender A/B
- les donnees persistantes sont chiffrees
- `/data` s'ouvre automatiquement via TPM2 local
- l'etat Mender persiste entre les bascules
- l'IPC peut dialoguer avec un broker distant via mTLS
- le flux remote unlock peut etre prouve en dry-run
- la chaine Ansible de provisioning du remote unlock est fonctionnelle
- les briques cloud telemetrie sont construites et benchmarkees
- la cartographie edge Modbus/telemetrie est stabilisee et revalidee en lab
- la table d'echange rev.2, le snapshot `read_plan` et le `CRC16`
  planificateur sont de nouveau alignes entre repo, IPC et simulateur
- le mode Simulation/Reel est implemente avec contrat d'ecriture Rev02
  identique entre digital twin et automate physique
- les registres de telemetry Reel issus de la table Rev02 sont mappes dans
  `gateway_modbus_sbc.py` et `telemetry_publisher.py`
- l'IPC embarque les drop-ins systemd Reel LCI avec cible
  `192.168.1.52:502`
- la verification runtime du mapping Reel retourne `REGISTER_MAPPING_REV02_OK`
- le ciblage strict des commandes par IPC est valide
- le `Control Panel` est expose en prive avec OIDC et RBAC fonctionnels
- l'ecran `Orders` rev.2 est redeploye sur le site
  `control-panel.cascadya.internal`
- `Keycloak` est migre sur la VM Vault comme fournisseur d'identite partage
- les services internes majeurs sont joignables via DNS internes dedies
- le portail existe comme hub d'acces et sa cible `portal first` est cadree

## 13. Exigences non encore satisfaites

- transport final WireGuard/Teltonika valide de bout en bout pour le remote unlock
- retrait du mecanisme local TPM comme chemin normal
- verification cryptographique forte de la quote TPM cote broker
- connectivite terrain finale vers l'automate LCI `192.168.1.52:502`
- validation sur site des valeurs REAL terrain `%MW388`, `%MW512`, `%MW514`
  et `%MW574`
- validation terrain finale que l'automate LCI attend bien l'ordre des mots
  `low_word_first` pour les REAL32
- validation terrain finale que l'automate LCI attend bien l'ordre des mots
  `low_word_first` pour les UDINT / Order ID
- validation runtime finale du role `edge-agent` avec broker raccorde dans les
  conditions completes du lab
- convergence complete `portal first` :
  - frontend admin migre
  - backend admin public migre
  - parcours de login concurrents retires
- elimination complete du drift Ansible sur les DNS internes, les clients OIDC
  et les routes legacy
- runbook d'exploitation incident complet
- hardening final complet apres tour de non-regression

## 14. Risques et limites

### 14.1 Limites assumees de la demo actuelle

- le remote unlock actuel fonctionne en `direct mode`
- le broker/Vault de demonstration tournent localement sur laptop
- le token TPM local n'a pas encore ete retire

### 14.2 Risques techniques connus

- le transport final WireGuard remote unlock n'est pas encore revalide
- la verification TPM cote serveur est encore partielle
- la topologie demo actuelle depend de l'environnement de lab
- la telemetrie Ansible cible est deployee et validee cote IPC, mais son
  runtime de bout en bout depend encore des dependances externes du lab

### 14.3 Risques projet

- confusion possible entre "architecture cible" et "etat deja valide"
- risque de deployment manuel hors Ansible si la documentation n'est pas suivie
- risque de divergence entre scripts terrain et scripts versionnes si les
  changements ne rentrent pas dans le repo
- risque de conserver trop longtemps plusieurs portes d'entree humaines
  concurrentes (`portal`, `control-panel`, liens directs d'outils)
- risque de drift entre l'etat runtime des VMs et les playbooks si les corrections
  DNS / NAT / allowlists / OIDC ne sont pas toutes reconvergees en code

## 15. Definition of Done de la phase actuelle

La phase actuelle est consideree comme tenue si :

- la fondation IPC est validee
- l'OTA est validee
- `/data` chiffre et TPM local sont valides
- le remote unlock dry-run est valide
- la documentation operatoire est suffisante pour rejouer le setup
- le socle IAM partage et les chemins d'acces internes critiques sont stabilises

La phase peut etre consideree comme totalement closee seulement apres :

- validation runtime de bout en bout du role `edge-agent`
- revalidation du transport cible de remote unlock
- convergence complete du portail comme point d'entree principal

## 16. Preuves recommandees pour revue de management

### 16.1 Sur l'IPC

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
findmnt /
findmnt /data
cat /etc/crypttab
sudo cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2
sudo mender-update show-artifact
sudo systemctl status gateway_modbus.service --no-pager
sudo systemctl status telemetry_publisher.service --no-pager
sudo grep REMOTE_UNLOCK_BROKER_URL /etc/cascadya/unlock/unlock.env
sudo grep REMOTE_UNLOCK_TRANSPORT_MODE /etc/cascadya/unlock/unlock.env
```

### 16.2 Sur le laptop / WSL

```bash
docker ps
docker logs --tail 50 vault-demo
docker logs --tail 50 remote-unlock-demo-broker
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_transport_mode=direct
ansible-playbook -i inventory-edge-agent.ini -k -K edge-agent-validate.yml \
  -e edge_agent_expect_runtime_connectivity=false
```

## 17. Positionnement avant la phase suivante

La phase de fondation edge est terminee.

Le projet dispose deja de :

- la plateforme edge
- la couche OTA
- la couche chiffrement
- la couche broker/cloud
- la preuve du remote unlock
- un `Control Panel` prive avec IAM/RBAC
- un `Keycloak` mutualise sur Vault
- un portail interne en voie de devenir le point d'entree unique

La prochaine phase doit transformer cet ensemble en architecture finale
homogene et exploitable :

- valider le runtime de bout en bout du role `edge-agent`
- finaliser le transport WireGuard/Teltonika pour le remote unlock
- renforcer la verification TPM cote serveur
- preparer le cutover reel de boot en production
- faire converger le portail vers la vraie porte d'entree humaine
- supprimer les derniers drifts d'infrastructure entre runtime et Ansible
- introduire un HAL `Device Profile` pour rendre la couche Modbus agnostique
  fournisseur sans casser le profil LCI Rev02
- poursuivre le hardening OS et la non-regression

## 18. Conclusion

Le systeme Cascadya au 21/04/2026 est un systeme deja substantialement
construit.

Ce qui existe n'est pas une maquette ponctuelle :

- les performances de messagerie ont ete benchmarkees
- le routage et la supervision cloud existent
- le jumeau numerique existe
- la telemetrie edge existe
- l'IPC industriel est industrialise
- l'OTA et le chiffrement sont valides
- le remote unlock est prouve fonctionnellement
- un `Control Panel` et un portail internes existent
- un IAM partage sur Vault existe
- des DNS internes et des chemins prives outilles existent
- le flux rev.2 `Orders -> gateway IPC -> simulateur Modbus` est de nouveau
  coherent et valide techniquement
- le mode Simulation/Reel est desormais documente, deploye cote IPC et protege
  par un decalage memoire des registres procede en simulation

Le projet est donc dans une phase de consolidation finale, pas de recherche
initiale. La priorite n'est plus d'inventer les briques de base, mais de les
figer, les relier proprement et fermer les derniers ecarts entre la demo
controlee et la cible de production.

## 19. Synthese exploitable pour CV et rapport de stage

### 19.1 Ce que le stage / projet demontre

- conception et industrialisation d'une plateforme edge securisee
- mise en place d'un pipeline complet de telemetrie et de commande entre edge et
  cloud
- automatisation d'infrastructure et de provisioning avec Ansible
- integration d'IAM partagee avec `Keycloak`, `OIDC`, `RBAC` et portail interne
- mise sous controle de l'acces prive via `WireGuard`, `Traefik`, `dnsmasq` et
  DNS internes
- production de PRD, runbooks, procedures d'exploitation et preuves de validation

### 19.2 Formulations courtes reutilisables pour un CV

- Conception et industrialisation d'une plateforme edge securisee pour IPC
  industriels
- Deploiement d'une chaine complete `NATS / JetStream / TimescaleDB / Grafana`
  pour la telemetrie et la supervision
- Automatisation du provisioning et du durcissement des equipements avec Ansible
- Mise en place d'un IAM partage base sur `Keycloak / OIDC / RBAC`
- Migration d'un service d'identite vers une VM dediee et recablage de plusieurs
  applications internes
- Fiabilisation de l'acces prive via `WireGuard`, `Traefik`, `dnsmasq` et DNS
  internes

### 19.3 Axes a raconter dans un rapport de stage

- la progression d'un POC technique vers une pre-industrialisation
- la complementarite entre edge, cloud, reseau, securite et exploitation
- l'importance du passage du "ca marche localement" a "ca se redeploie
  proprement"
- la gestion du drift entre etat reel des VMs, scripts de deploiement et
  documentation
- la transition d'une logique d'outils separes vers une logique de portail
  d'acces unifie
