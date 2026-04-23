# PRD - Systeme Cascadya

## 1. Objet du document

Ce document fige une vision complete de l'etat du systeme Cascadya au
17/03/2026.

Il ne sert pas seulement a decrire l'IPC. Il sert a :

- montrer ce qui a ete construit sur l'ensemble de la chaine
- distinguer ce qui est valide en reel de ce qui est seulement prepare
- relier les briques edge, cloud, reseau, telemetrie, OTA et securite
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

Le projet n'est plus au stade "proof of concept fragile". Il est dans un etat
de pre-industrialisation avancee.

La situation au 17/03/2026 est la suivante :

- la fondation IPC est validee
- le flux remote unlock est valide en `direct mode`
- le transport final `WireGuard + Teltonika + broker/Vault` reste a finaliser
- la telemetrie edge est desormais deployee proprement via le role
  `edge-agent` sur l'IPC cible
- la validation Ansible de deploiement de cette brique est acquise
- la validation runtime de bout en bout de cette brique reste a finir avec le
  simulateur Modbus et le broker reellement joignables

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
- migration de `active_strategy` vers `%MW200`
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

Implementation actuelle :

- Python
- WSL / WSLg
- TLS client
- NATS request/reply

### 6.2 Gateway edge sur IPC

Role :

- traduire les ordres NATS en operations Modbus
- traduire l'etat Modbus en messages NATS de telemetrie
- maintenir le watchdog industriel

Implementation actuelle :

- `gateway_modbus_sbc.py`
- `telemetry_publisher.py`
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

Reste a valider en bout en bout avec le lab complet raccorde :

- connectivite Modbus effective vers `192.168.50.2:502`
- connectivite NATS/TLS effective vers le broker cible
- stabilite runtime des deux services sans boucle de restart
- absence d'erreurs de transport dans les journaux systemd

### 9.4 Cloud et supervision

Valide :

- NATS Core
- JetStream
- ingestion continue vers TimescaleDB
- dashboards Grafana

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

## 12. Exigences satisfaites au 17/03/2026

- un IPC vierge peut etre installe de facon reproductible
- l'IPC supporte un cycle OTA Mender A/B
- les donnees persistantes sont chiffrees
- `/data` s'ouvre automatiquement via TPM2 local
- l'etat Mender persiste entre les bascules
- l'IPC peut dialoguer avec un broker distant via mTLS
- le flux remote unlock peut etre prouve en dry-run
- la chaine Ansible de provisioning du remote unlock est fonctionnelle
- les briques cloud telemetrie sont construites et benchmarkees

## 13. Exigences non encore satisfaites

- transport final WireGuard/Teltonika valide de bout en bout pour le remote unlock
- retrait du mecanisme local TPM comme chemin normal
- verification cryptographique forte de la quote TPM cote broker
- validation runtime finale du role `edge-agent` avec simulateur Modbus et
  broker raccordes
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

## 15. Definition of Done de la phase actuelle

La phase actuelle est consideree comme tenue si :

- la fondation IPC est validee
- l'OTA est validee
- `/data` chiffre et TPM local sont valides
- le remote unlock dry-run est valide
- la documentation operatoire est suffisante pour rejouer le setup

La phase peut etre consideree comme totalement closee seulement apres :

- validation runtime de bout en bout du role `edge-agent`
- revalidation du transport cible de remote unlock

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

La phase de fondation est terminee.

Le projet dispose deja de :

- la plateforme edge
- la couche OTA
- la couche chiffrement
- la couche broker/cloud
- la preuve du remote unlock

La prochaine phase doit transformer cet ensemble en architecture finale
homogene et exploitable :

- valider le runtime de bout en bout du role `edge-agent`
- finaliser le transport WireGuard/Teltonika pour le remote unlock
- renforcer la verification TPM cote serveur
- preparer le cutover reel de boot en production
- poursuivre le hardening OS et la non-regression

## 18. Conclusion

Le systeme Cascadya au 17/03/2026 est un systeme deja substantialement
construit.

Ce qui existe n'est pas une maquette ponctuelle :

- les performances de messagerie ont ete benchmarkees
- le routage et la supervision cloud existent
- le jumeau numerique existe
- la telemetrie edge existe
- l'IPC industriel est industrialise
- l'OTA et le chiffrement sont valides
- le remote unlock est prouve fonctionnellement

Le projet est donc dans une phase de consolidation finale, pas de recherche
initiale. La priorite n'est plus d'inventer les briques de base, mais de les
figer, les relier proprement et fermer les derniers ecarts entre la demo
controlee et la cible de production.
