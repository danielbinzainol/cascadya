# PRD - Lot 7 - Wazuh Manager VM Dev1, integration IPC et visualisation dashboard

## 1. Objet

Ce document definit le lot 7 du Control Panel au 8 avril 2026.

Le lot 7 ajoute une brique de securite centralisee pour les IPC :

- creation d'une VM dediee `wazuh-Dev1-S` ;
- hebergement des composants centraux Wazuh necessaires au lab `Dev1` ;
- ouverture strictement controlee des flux reseau pour l'enrollment et la
  supervision des IPC ;
- integration effective du deploiement et de la validation de `wazuh-agent`
  dans le workflow automatise de provisioning IPC ;
- validation d'une premiere brique de remontee des alertes vers la VM
  Wazuh Manager afin d'exploiter le `Wazuh dashboard` comme surface de
  visualisation ;
- formalisation des regles a transmettre a l'equipe Terraform pour creer la VM,
  ses disques, ses tags et ses security groups.

L'objectif du lot n'est toujours pas de livrer une plateforme Wazuh
production-ready multi-noeuds. Le but est de disposer d'une premiere brique
`Dev1` fiable, securisee, integree au flux d'onboarding des IPC, et exploitable
depuis le dashboard Wazuh pour observer ce qui se passe sur le terrain.

## 2. Contexte

Le lot 4 a deja stabilise :

- le provisioning automatise des IPC ;
- le mode `auto` et le mode `manual` pour les playbooks Ansible ;
- la persistance des IP et des routages reseau sur l'IPC ;
- le bootstrap `remote-unlock`, `WireGuard`, `Vault` et `edge-agent`.

Le lot 7 ajoute la couche de securite endpoint via `Wazuh agent` et la VM
centrale `wazuh-Dev1-S`.

Le besoin suivant est maintenant de consolider deux dimensions :

- une cible centrale stable pour enroll et superviser les IPC ;
- une remontee exploitable des alertes vers la VM Wazuh Manager afin de les
  visualiser dans le dashboard.

## 3. Choix d'architecture retenu

### 3.1 Choix principal

Pour `Dev1`, nous retenons une architecture `single-node all-in-one` sur une
seule VM nommee `wazuh-Dev1-S`.

Cela signifie que la VM hebergera :

- le `Wazuh server` ;
- le `Wazuh indexer` ;
- le `Wazuh dashboard`.

### 3.2 Pourquoi ce choix

Ce choix est retenu parce qu'il :

- minimise le nombre de VMs a creer et a operer ;
- accelere la mise en service du lab `Dev1` ;
- simplifie l'integration avec le provisioning IPC existant ;
- correspond au besoin actuel de validation fonctionnelle, pas encore a une
  cible HA multi-noeuds ;
- reste aligne avec le modele officiel Wazuh `all-in-one`.

### 3.3 Ce que ce choix n'est pas

Ce choix n'est pas :

- une architecture de production HA ;
- une architecture multi-site ;
- une architecture avec separation stricte `manager/indexer/dashboard`.

Une cible `production-ready` pourra plus tard separer :

- un ou plusieurs managers ;
- un cluster d'indexers ;
- un dashboard dedie.

## 4. Objectifs du lot 7

- Creer une VM `wazuh-Dev1-S` stable et securisee.
- Exposer les ports strictement necessaires a l'enrollment et a la supervision.
- Limiter au maximum l'exposition publique de l'API et de l'indexer.
- Fournir une cible de confiance pour le deploiement effectif de `wazuh-agent`
  sur les IPC.
- Integrer `wazuh-agent-deploy.yml` et `wazuh-agent-validate.yml` au workflow de
  provisioning `auto/manual` deja existant.
- Permettre a un premier IPC reel de s'enroller et d'etre vu comme agent actif
  sur la plateforme Wazuh.
- Preparer la remontee des alertes techniques et metier vers le dashboard
  Wazuh pour visualiser l'activite de l'IPC et de la VM manager.
- Poser des regles reseau et Terraform claires pour eviter les derives.

## 5. Hors perimetre

Le lot 7 n'inclut pas encore :

- la generalisation du deploiement `wazuh-agent` a plusieurs IPC et plusieurs
  sites ;
- le mapping des groupes Wazuh par site ou par typologie d'IPC ;
- le SSO du dashboard Wazuh ;
- la production de tableaux de bord metier definitifs et de corrélations
  avancees sur les alertes Cascadya ;
- une federation multi-environnement ;
- une architecture HA ;
- l'ouverture de l'indexer a d'autres outils externes.

## 6. Architecture cible

```text
IPC
   ->
Wazuh agent
   ->
Wazuh server / manager sur wazuh-Dev1-S
   ->
Filebeat
   ->
Wazuh indexer local sur wazuh-Dev1-S
   ->
Wazuh dashboard local sur wazuh-Dev1-S
   ->
Administrateurs / exploitation
```

Modele reseau prefere :

- acces `IPC -> Wazuh` via reseau prive ou overlay `WireGuard` si possible ;
- sinon, acces par IP publique strictement allowlistee ;
- acces administrateur au dashboard via VPN ou bastion ;
- pas d'exposition publique libre de l'API `55000` ni de l'indexer `9200`.

## 7. Choix techniques cibles

### 7.1 Systeme

- OS cible : `Ubuntu 22.04 LTS`
- architecture : `x86_64`
- nom de la VM : `wazuh-Dev1-S`
- hostname recommande : `wazuh-dev1-s`
- environment tag : `dev1`

### 7.2 Taille de la VM

Base officielle Wazuh :

- `Wazuh server` : minimum `2 GB RAM / 2 vCPU`, recommande `4 GB / 8 vCPU`
- `Wazuh indexer` : minimum `4 GB RAM / 2 vCPU`, recommande `16 GB / 8 vCPU`

Choix d'implementation `Dev1` retenu pour un `all-in-one` de lab :

- `4 vCPU`
- `8 GB RAM`
- `50 GB SSD` de data minimum

Recommandation pratique si la retention, le volume d'evenements ou le nombre
d'IPC augmente vite :

- `8 vCPU`
- `16 GB RAM`
- `200 GB SSD`

Ce dimensionnement `Dev1` est un compromis de lab plus leger que les
recommandations confortables officielles, retenu pour limiter le cout
d'infrastructure initial. Il devra etre reevalue si l'indexer sature en CPU,
RAM ou stockage.

### 7.3 Disques

Modele recommande :

- disque systeme :
  - `40 a 60 GB`
- disque data dedie :
  - `50 GB`
  - cible prioritaire : `/var/lib/wazuh-indexer`

Pourquoi separer le disque data :

- meilleure lisibilite de la croissance des donnees ;
- snapshots plus simples ;
- isolement entre OS et index de securite ;
- evolution plus facile si la retention augmente.

### 7.4 Adresse IP et DNS

Recommandations :

- `private_ip` fixe obligatoire ;
- `public_ip` seulement si necessaire pour joindre les IPC hors overlay prive ;
- enregistrement DNS recommande :
  - `wazuh-dev1-s.<domaine-interne>`
  - alias eventuel `wazuh-dev1.<domaine>`

## 8. Regles reseau et ports a ouvrir

Les ports ci-dessous s'appuient sur les ports par defaut documentes par Wazuh.

### 8.1 Tableau des flux

| Port | Proto | Sens | Source autorisee | Usage | Politique |
| --- | --- | --- | --- | --- | --- |
| `22` | `TCP` | entrant | VPN admin, bastion, IPs d'admin allowlistees | SSH administration | obligatoire, restreint |
| `443` | `TCP` | entrant | VPN admin, bastion, IPs d'admin allowlistees | Dashboard Wazuh | obligatoire, restreint |
| `1514` | `TCP` | entrant | IPC via overlay prive, WireGuard, ou IPs publiques allowlistees | Connexion agent Wazuh | obligatoire |
| `1515` | `TCP` | entrant | IPC via overlay prive, WireGuard, ou IPs publiques allowlistees | Enrollment agent Wazuh | obligatoire |
| `55000` | `TCP` | entrant | `control-panel-DEV1-S`, bastion admin si necessaire | API Wazuh server | optionnel mais recommande, tres restreint |
| `1514` | `UDP` | entrant | aucune par defaut | Agent connection UDP | ferme par defaut |
| `1516` | `TCP` | entrant | aucune en single-node | Cluster daemon | ferme en `Dev1` |
| `514` | `UDP/TCP` | entrant | aucune par defaut | Syslog collector | ferme par defaut |
| `9200` | `TCP` | entrant | `localhost` seulement, ou reseau interne si besoin strict | API Wazuh indexer | jamais public |
| `9300-9400` | `TCP` | entrant | aucune en single-node | Cluster indexer | ferme en `Dev1` |

### 8.2 Regles entrantes obligatoires

- `22/TCP`
  - seulement depuis le VPN admin, un bastion, ou une courte allowlist
  d'IP administrateur ;
- `443/TCP`
  - seulement depuis le VPN admin ou le sous-reseau d'exploitation ;
- `1514/TCP`
  - seulement depuis les IPC, leurs sous-reseaux, ou leurs IP publiques
  officielles ;
- `1515/TCP`
  - meme logique que `1514/TCP` ;
- `55000/TCP`
  - seulement depuis `control-panel-DEV1-S` et eventuellement un bastion admin.

### 8.3 Regles entrantes explicitement interdites par defaut

- ne pas ouvrir `9200/TCP` au public ;
- ne pas ouvrir `9300-9400/TCP` au public ;
- ne pas ouvrir `1516/TCP` en `Dev1` ;
- ne pas ouvrir `514/TCP` ni `514/UDP` sans cas d'usage explicite ;
- ne pas ouvrir `1514/UDP` tant que l'usage n'est pas justifie.

### 8.4 Regles sortantes

Sortant minimal recommande :

- `443/TCP` vers :
  - depots Ubuntu ;
  - depots Wazuh ;
  - `cti.wazuh.com` si la fonctionnalite de threat intelligence ou de
    vulnerability feed en depend ;
- `53/TCP` et `53/UDP` vers les resolvers DNS autorises ;
- `123/UDP` vers la source NTP si la plateforme le requiert.

Si l'environnement ne doit pas sortir sur Internet, utiliser une strategie
`offline/staged` pour l'installation et les mises a jour.

## 9. Politique de security group Terraform

### 9.1 Politique par defaut

- `deny all inbound` par defaut ;
- `deny all outbound` si l'equipe reseau le permet, puis ouverture minimale ;
- sinon `allow egress` borne aux flux listes ci-dessus ;
- security groups separes si possible pour :
  - administration ;
  - agents IPC ;
  - interconnexions internes.

### 9.2 Variables Terraform recommandees

- `name = "wazuh-Dev1-S"`
- `hostname = "wazuh-dev1-s"`
- `environment = "dev1"`
- `role = "wazuh"`
- `private_ip = <fixe>`
- `public_ip_enabled = true|false`
- `admin_allowed_cidrs = [...]`
- `ipc_allowed_cidrs = [...]`
- `control_panel_allowed_cidrs = [...]`
- `root_volume_size_gb = 50`
- `data_volume_size_gb = 50`
- `backup_enabled = true`
- `monitoring_enabled = true`

### 9.3 Regles Terraform a imposer

- IP privee statique obligatoire ;
- taggage standard obligatoire ;
- chiffrement disque obligatoire ;
- snapshots / sauvegardes obligatoires ;
- pas de `0.0.0.0/0` sur `22`, `443`, `55000`, `9200`, `9300-9400` ;
- `1514` et `1515` uniquement depuis les CIDRs IPC approuves ;
- si `public_ip_enabled = false`, l'acces doit passer par VPN, bastion ou
  overlay prive ;
- si `public_ip_enabled = true`, l'allowlist doit etre documentee et revue.

## 10. Regles de securite et d'exploitation

### 10.1 Regles de securite

- changer les credentials par defaut immediatement apres installation ;
- utiliser des certificats TLS valides pour le dashboard ;
- ne jamais exposer l'indexer `9200` au public ;
- ne pas utiliser `admin/changeme` au-dela de la phase d'installation ;
- limiter l'acces SSH a un bastion ou a un VPN ;
- centraliser les secrets d'installation et de rotation dans un coffre type
  `Vault` si possible ;
- prevoir la rotation des credentials Wazuh.

### 10.2 Regles d'exploitation

- surveiller la croissance disque de l'indexer ;
- surveiller la RAM et le CPU JVM de l'indexer ;
- mettre en place des sauvegardes quotidiennes au minimum ;
- documenter une procedure de restauration ;
- conserver les mises a jour sous controle ;
- desactiver le repo Wazuh apres installation initiale si vous voulez eviter
  les upgrades accidentels.

## 11. Strategie d'installation retenue

### 11.1 Creation d'infrastructure

Terraform cree :

- la VM `wazuh-Dev1-S` ;
- les disques ;
- les security groups ;
- l'IP privee fixe ;
- le DNS ;
- les sauvegardes / snapshots ;
- les tags.

### 11.2 Configuration logicielle

La configuration Wazuh sur la VM sera faite apres Terraform, par Ansible ou
par l'assistant officiel Wazuh.

Choix recommande :

- pour `Dev1`, installation `all-in-one` ;
- utilisation des playbooks/roles officiels Wazuh via Ansible quand possible ;
- sinon usage de l'assistant officiel Wazuh pour une premiere mise en place
  rapide, puis industrialisation Ansible dans un second temps.

Pourquoi :

- alignement avec la doc officielle ;
- meilleure reproductibilite ;
- moins de scripts ad hoc ;
- meilleur passage a l'echelle plus tard.

## 12. Integration realisee avec le provisioning IPC

Le workflow IPC complet `via WireGuard` embarque maintenant la sequence Wazuh
suivante :

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

Le mode `auto` lancera la chaine complete.

Le mode `manual` permettra de relancer uniquement :

- le deploiement de l'agent Wazuh ;
- la validation de l'agent Wazuh ;
- ou un autre playbook cible.

Le comportement fonctionnel valide pour `wazuh-agent-validate.yml` est
maintenant :

- verification de la presence du paquet `wazuh-agent` ;
- verification de la presence de l'unite systemd ;
- verification des flux reseau `1514/TCP` et `1515/TCP` ;
- verification d'une session TCP etablie entre l'IPC et le manager Wazuh ;
- synthese exploitable dans les logs de job.

Le lot 7 ne vit donc plus seul dans la chaine : il doit coexister proprement
avec la persistance reseau IPC, la collecte `Alloy` vers Mimir et le
`round-trip` NATS final de l'edge-agent.

## 13. Etat valide au 7-8 avril 2026 et criteres d'acceptation

Etat valide en `real/auto` sur le premier IPC de reference :

- dates de validation :
  - `7 avril 2026` pour le chemin public ;
  - `8 avril 2026` pour le chemin prive via `WireGuard` ;
- job de reference : `#39` ;
- asset : `cascadya-ipc-10-109` ;
- uplink IPC : `192.168.10.109/24` ;
- reseau process IPC : `192.168.50.1/24` ;
- manager Wazuh atteint sur `51.15.48.174:1514` puis sur `10.42.1.7:1514` ;
- serveur d'enrollment Wazuh atteint sur `51.15.48.174:1515` puis sur
  `10.42.1.7:1515` ;
- session TCP Wazuh observee entre l'IPC et le manager sur le chemin public,
  puis sur le chemin prive ;
- `wazuh-agent` confirme `active/enabled` ;
- `gateway_modbus.service` confirme `active/enabled` ;
- `telemetry_publisher.service` confirme `active/enabled` ;
- round-trip `NATS request/reply` confirme via le proxy broker ;
- workflow complet de provisioning termine en `real` jusqu'au step
  `edge-agent-nats-roundtrip.yml`.

Ce point valide le chemin public pour le lab, mais le mode d'exploitation
durable doit ensuite preferer une IP privee fixe du manager Wazuh atteinte via
WireGuard, afin de supprimer la dependance a l'IP publique de sortie du site.

Addendum valide au `8 avril 2026` :

- le chemin prive `IPC -> Teltonika -> WireGuard -> 10.42.1.7` est valide ;
- le test de reboot du Teltonika confirme que ce chemin prive remonte seul ;
- le peer Teltonika `VM_Cloud` annonce maintenant
  `Allowed IPs = 10.8.0.0/24, 10.42.1.7/32` ;
- la VM `wazuh-dev1-s` route maintenant durablement :
  - `192.168.10.0/24 via 10.42.1.5`
  - `192.168.50.0/24 via 10.42.1.5`
  - `10.8.0.0/24 via 10.42.1.5`
- ces routes sont rendues persistantes via
  `/etc/netplan/60-wazuh-private-routes.yaml` ;
- l'IPC pointe maintenant vers `10.42.1.7` dans
  `/var/ossec/etc/ossec.conf` ;
- le control panel porte maintenant les defaults :
  - `AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_ADDRESS_DEFAULT=10.42.1.7`
  - `AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_PORT_DEFAULT=1514`
  - `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_SERVER_DEFAULT=10.42.1.7`
  - `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_PORT_DEFAULT=1515`
- la brique dashboard MVP est validee avec :
  - decodeur `cascadya_gateway`
  - regles `100520` et `100521`
  - alerte `100521` visible dans `alerts.json` pour
    `cascadya-ipc-10-109`
  - nouvelle alerte `100521` observee apres reboot du routeur site ;
- le DNS interne `wazuh.cascadya.internal` est maintenant resolu via
  `10.8.0.1 -> 10.42.1.7` ;
- le dashboard Wazuh est maintenant expose en HTTPS interne sur
  `https://wazuh.cascadya.internal` avec un certificat dedie ;
- le control panel ouvre maintenant ce FQDN interne depuis le bouton Wazuh de
  la page Alerts.

Le chemin public a donc servi de preuve initiale, mais le mode cible valide
pour le lab est desormais le chemin prive `WireGuard -> 10.42.1.7`.

Addendum valide au `13 avril 2026` :

- le rerun terrain du workflow etendu `18 steps` a revalide le chemin
  `wazuh-agent` sur `cascadya-ipc-10-109` ;
- la route IPC vers le manager Wazuh `10.42.1.7/32` est maintenant aussi figee
  par `cascadya-network-persist.service` sur l'IPC ;
- `wazuh-agent-deploy.yml` puis `wazuh-agent-validate.yml` repassent dans une
  reprise manuelle controlee depuis `control-panel-DEV1-S` ;
- la chaine complete continue ensuite vers `ipc-alloy`, `edge-agent` puis
  `edge-agent-nats-roundtrip.yml` sans regression Wazuh ;
- la route soeur vers Mimir `10.42.1.4/32` et les routes de retour sur
  `monitoring-DEV1-S` deviennent une dependance operationnelle de la meme
  topologie privee, meme si cette persistance monitoring reste a industrialiser
  dans un repo distinct.

La VM `wazuh-Dev1-S` sera consideree prete si :

- elle existe dans Terraform avec les tags standards ;
- elle dispose d'une IP privee fixe ;
- son disque data est separe du disque systeme ;
- `443/TCP` est atteignable seulement depuis les zones admin autorisees ;
- `1514/TCP` et `1515/TCP` sont atteignables depuis les IPC sur le chemin
  prive attendu ;
- `55000/TCP` n'est joignable que depuis le control panel ou un bastion admin ;
- `9200/TCP` n'est pas expose publiquement ;
- les sauvegardes sont activees ;
- l'installation Wazuh `all-in-one` peut etre executee sur cette VM ;
- un premier IPC peut enroll un agent avec succes ;
- l'agent enrolé apparait `active/enabled` et maintient une session etablie avec
  le manager ;
- l'IPC provisionne peut ensuite terminer les steps `edge-agent` et le probe
  `NATS request/reply` sans regression Wazuh ;
- une alerte Cascadya technique significative remonte effectivement dans le
  dashboard Wazuh ;
- la perte d'IP publique de sortie du site ne remet plus en cause la cible
  Wazuh tant que le tunnel `WireGuard` du site remonte correctement.

## 14. Visualisation cible des alertes dans Wazuh Dashboard

Le prochain objectif produit est de faire de `wazuh-Dev1-S` la surface unique
de visualisation securite `Dev1` pour :

- les alertes natives Wazuh des IPC ;
- les alertes techniques des briques `remote-unlock`, `WireGuard` et
  `wazuh-agent` ;
- les alertes de fonctionnement des services `edge-agent` ;
- l'etat local de la VM `wazuh-Dev1-S` elle-meme.

### 14.1 Sources a remonter dans Wazuh

Pour les IPC Cascadya, la remontee cible doit couvrir au minimum :

- `wazuh-agent.service` et son etat de connectivite ;
- `wg-quick@wg0.service` et les incidents de tunnel `WireGuard` ;
- `cascadya-network-persist.service` pour les regressions reseau ;
- les journaux `remote-unlock` ;
- `gateway_modbus.service` ;
- `telemetry_publisher.service`.

Pour la VM manager `wazuh-Dev1-S`, la cible doit aussi inclure :

- les composants locaux `Wazuh server`, `indexer` et `dashboard` ;
- l'etat de l'OS, du stockage et des services systemd critiques ;
- les alertes d'acces administrateur ou de degradation de capacite.

### 14.2 Cible technique

Validation deja obtenue :

- collecte `journald` centralisee sur un sous-ensemble de services Cascadya ;
- decodeur `cascadya_gateway` cote manager ;
- regles custom `100520` et `100521` ;
- affichage des evenements `gateway_modbus.service` dans `alerts.json` ;
- transport agent Wazuh bascule vers `10.42.1.7` via `WireGuard` ;
- DNS interne et HTTPS du dashboard Wazuh valides sur
  `https://wazuh.cascadya.internal`.

La brique a implementer apres cette validation est :

- ajouter les sources `localfile` ou journald pertinentes cote IPC pour que
  `wazuh-agent` remonte les evenements utiles ;
- ajouter des decodeurs et des regles Wazuh cote manager pour classifier les
  messages Cascadya ;
- taguer les alertes avec l'asset, le site, le composant et la severite ;
- faire pointer le trafic agent Wazuh vers l'IP privee fixe de `wazuh-Dev1-S`
  ou un FQDN interne stable transporte par WireGuard ;
- eviter que `1514/TCP` et `1515/TCP` dependent d'une IP publique NAT `/32`
  susceptible de changer apres reboot routeur, failover WAN ou reconnexion
  operateur ;
- utiliser le `Wazuh dashboard` de `wazuh-Dev1-S` comme vue d'exploitation par
  defaut pour l'equipe ;
- exposer un connecteur backend `control-panel -> Wazuh indexer` pour remonter
  les alertes recentes dans la page Alerts du control panel, avec credentials
  dedies et acces prive strictement borne.

### 14.3 Lien explicite avec la VM Wazuh Manager

Le besoin produit n'est pas seulement d'avoir un agent `active/enabled`. Il faut
que les evenements utiles remontent et soient visibles dans `wazuh-Dev1-S`.

Le chainage cible est donc :

```text
IPC
   ->
journald / fichiers surveilles / alertes applicatives
   ->
wazuh-agent
   ->
wazuh-manager sur wazuh-Dev1-S
   ->
wazuh-indexer
   ->
wazuh-dashboard
   ->
control panel Alerts + vues operateur et triage
```

Les alertes Cascadya doivent etre lisibles dans le dashboard Wazuh, et une vue
de triage rapide doit aussi etre disponible dans le control panel sans dupliquer
la logique d'analyse.

### 14.4 Exigences dashboard a couvrir

Le dashboard Wazuh doit permettre au minimum :

- de voir l'agent `cascadya-ipc-10-109` et son statut de sante ;
- de distinguer clairement les alertes provenant de `wazuh-agent`,
  `remote-unlock`, `WireGuard`, `gateway_modbus.service`,
  `telemetry_publisher.service` et de la VM `wazuh-Dev1-S` elle-meme ;
- de filtrer par `agent.name`, site, composant, severite et fenetre temporelle ;
- d'ouvrir rapidement le detail d'une alerte puis de remonter au journal source ;
- de visualiser les incidents de connectivite manager, enrollment, tunnel
  `WireGuard` et runtime edge-agent.

### 14.5 Premier backlog technique pour la visualisation

Le prochain lot d'implementation devra couvrir au minimum :

- la configuration cote IPC de sources Wazuh pertinentes :
  - journaux systemd critiques ;
  - logs `remote-unlock` ;
  - logs `gateway_modbus` ;
  - logs `telemetry_publisher` ;
- la configuration cote `wazuh-Dev1-S` de decodeurs et de regles pour classifier
  les messages Cascadya ;
- la verification que la VM manager remonte aussi ses propres evenements
  critiques au dashboard ;
- la creation d'une vue ou de saved searches dediees :
  - `IPC Health`
  - `Remote Unlock / WireGuard`
  - `Edge Agent Runtime`
  - `Wazuh Manager VM Health`
- la validation operateur depuis le dashboard, sans lecture obligatoire des logs
  SSH.

### 14.6 Resultat operateur attendu

Un operateur doit pouvoir, depuis le dashboard Wazuh :

- voir `cascadya-ipc-10-109` comme agent actif ;
- filtrer les alertes par IPC, site, service ou severite ;
- visualiser les incidents `remote-unlock`, `WireGuard`, `gateway_modbus` et
  `telemetry_publisher` ;
- visualiser aussi l'etat de la VM `wazuh-Dev1-S` ;
- comprendre rapidement si le probleme vient de l'IPC, du transport ou du
  manager.

## 15. Handoff Terraform

Le message a transmettre a l'equipe Terraform peut etre resume ainsi :

- creer une VM Ubuntu 22.04 nommee `wazuh-Dev1-S`
- architecture `single-node all-in-one` pour `Wazuh server + indexer + dashboard`
- `4 vCPU / 8 GB RAM / 50 GB SSD data` pour `Dev1`
- disque systeme et disque data separes
- IP privee fixe obligatoire
- IP publique seulement si necessaire pour joindre les IPC hors overlay prive
- ouvrir :
  - `22/TCP` depuis VPN admin / bastion uniquement
  - `443/TCP` depuis VPN admin / bastion uniquement
  - `1514/TCP` depuis les CIDRs IPC autorises ou depuis l'overlay prive
  - `1515/TCP` depuis les CIDRs IPC autorises ou depuis l'overlay prive
- `55000/TCP` seulement depuis `control-panel-DEV1-S` et eventuel bastion
- garder fermes :
  - `1514/UDP`
  - `1516/TCP`
  - `514/TCP`
  - `514/UDP`
  - `9200/TCP` au public
- `9300-9400/TCP`
- chiffrement disque, snapshots et monitoring obligatoires
- taguer clairement la VM comme composant securite `dev1`

Si le control panel lit directement les alertes recentes depuis l'indexer,
`9200/TCP` doit rester prive et etre ouvert seulement depuis
`control-panel-DEV1-S`.

Pour le lab actuel, le chemin durable valide est :

- agent IPC vers `10.42.1.7`
- via `WireGuard`
- sans dependance operationnelle au `/32` public de sortie du site

Le chemin public par IP source allowlistee peut etre conserve temporairement
comme fallback de diagnostic, mais il n'est plus la cible d'exploitation.

## 16. Prochaines etapes

Topologie logique des prochaines etapes :

```text
IPC
  -> Wazuh prive via WireGuard : valide
  -> premieres alertes Cascadya : valide
  -> extension des sources journald : a faire

wazuh-Dev1-S
  -> manager reachable en prive : valide
  -> regles custom gateway : valide
  -> regles remote-unlock / WireGuard / telemetry : a completer
  -> auto-surveillance de la VM : a completer

Control Panel
  -> defaults Wazuh prives : valides
  -> bouton Wazuh vers DNS interne : valide
  -> connecteur backend vers alertes Wazuh : implemente a activer
  -> reprovisioning avec ces defaults : pret

Terraform / reseau
  -> SG compatible chemin prive : valide
  -> fallback public encore present : retirable
```

Sequence recommande pour la suite :

1. retirer le fallback public `1514/TCP` / `1515/TCP` dependant de l'IP
   publique de sortie du site, apres validation interne finale de l'equipe ;
2. etendre les decodeurs et regles custom pour :
   - `remote-unlock`
   - `wg-quick@wg0.service`
   - `telemetry_publisher.service`
   - `cascadya-network-persist.service`
3. faire remonter explicitement les evenements critiques de `wazuh-Dev1-S`
   lui-meme dans le dashboard ;
4. preparer une vue operateur minimale dans Wazuh :
   - `IPC Health`
   - `Remote Unlock / WireGuard`
   - `Edge Agent Runtime`
   - `Wazuh Manager VM Health`
5. valider ensuite un reprovisioning complet d'un IPC de reference avec ces
   defaults Wazuh prives comme configuration nominale.

## 17. Sources officielles

- Wazuh architecture et ports requis :
  https://documentation.wazuh.com/current/getting-started/architecture.html
- Wazuh server requirements :
  https://documentation.wazuh.com/current/installation-guide/wazuh-server/index.html
- Wazuh indexer requirements :
  https://documentation.wazuh.com/current/installation-guide/wazuh-indexer/index.html
- Wazuh dashboard step-by-step :
  https://documentation.wazuh.com/current/installation-guide/wazuh-dashboard/step-by-step.html
- Wazuh deployment with Ansible :
  https://documentation.wazuh.com/current/deployment-options/deploying-with-ansible/guide/index.html
- Wazuh offline installation guide :
  https://documentation.wazuh.com/current/deployment-options/offline-installation/index.html
- Wazuh indexer API getting started :
  https://documentation.wazuh.com/current/user-manual/indexer-api/getting-started.html
- Wazuh indexer indices and `wazuh-alerts-*` :
  https://documentation.wazuh.com/current/user-manual/wazuh-indexer/wazuh-indexer-indices.html
