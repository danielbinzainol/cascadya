# Dossier Technique - Ecosysteme Wazuh Dev1

Version: 1.0
Date: 2026-04-09
Statut: support de presentation technique / reference d'architecture

## 1. Objet

Ce document synthetise l'ecosysteme Wazuh actuellement mis en place sur le lab
`Dev1`, les choix techniques retenus, les protocoles et flux reseau utilises,
les integrations deja en place avec le `control panel`, ainsi que les options
et extensions possibles pour la suite.

Il est concu pour servir :

- de support de presentation technique a l'equipe ;
- de reference d'architecture pour le lot Wazuh ;
- de photographie de l'etat actuel reellement valide ;
- de base de discussion pour les prochaines decisions.

## 2. Resume executif

Au `9 avril 2026`, l'ecosysteme Wazuh Dev1 fonctionne autour d'une architecture
simple, volontairement pragmatique, et deja exploitable :

- une VM unique `wazuh-Dev1-S` heberge le triplet `manager + indexer + dashboard` ;
- les IPC rejoignent Wazuh via `wazuh-agent` ;
- le chemin cible valide n'est plus le chemin public, mais le chemin prive
  `IPC -> Teltonika -> WireGuard -> 10.42.1.7` ;
- la VM Wazuh a des routes persistantes vers les reseaux site via
  `wireguard-DEV1-S` ;
- le dashboard Wazuh est expose en HTTPS interne sur
  `https://wazuh.cascadya.internal` ;
- le `control panel` sait ouvrir directement ce dashboard interne ;
- le `control panel` sait aussi interroger le flux d'alertes Wazuh via un
  connecteur backend vers l'indexer, sous reserve de credentials adaptes ;
- le provisioning IPC sait deployer l'agent Wazuh, le configurer, le valider,
  et persister les routes necessaires pour les nouveaux IPC.

En pratique, on a donc deja :

- une brique Wazuh centrale operationnelle ;
- un premier IPC reel valide ;
- un transport prive stabilise ;
- un premier niveau d'integration produit dans le `control panel`.

## 3. Ce que nous avons mis en place

## 3.1 Architecture retenue

Le choix retenu pour `Dev1` est une architecture `single-node all-in-one`.

La VM `wazuh-Dev1-S` heberge donc :

- `Wazuh server / manager`
- `Wazuh indexer`
- `Wazuh dashboard`

Ce choix a ete retenu pour :

- aller vite ;
- limiter le nombre de VMs ;
- reduire l'operabilite initiale ;
- livrer une premiere brique securite exploitable ;
- rester compatible avec une evolution ulterieure vers une architecture plus
  separee.

Ce choix n'est pas une cible HA ni une cible production definitive.

## 3.2 Noeuds principaux

Noeuds impliques dans l'ecosysteme Wazuh actuel :

- `wazuh-Dev1-S`
  - IP publique : `51.15.48.174`
  - IP privee : `10.42.1.7`
- `wireguard-DEV1-S`
  - IP publique : `51.15.84.140`
  - IP privee : `10.42.1.5`
  - WireGuard hub : `10.8.0.1/24`
- `control-panel-DEV1-S`
  - IP publique : `51.15.115.203`
  - IP privee : `10.42.1.2`
- `Teltonika RUTX50`
  - WireGuard site : `10.8.0.5`
  - LAN site : `192.168.10.1/24`
- `cascadya-ipc-10-109`
  - uplink IPC : `192.168.10.109/24`
  - reseau process : `192.168.50.1/24`

## 3.3 Vue logique

```text
Administrateur
  -> WireGuard client 10.8.0.2
  -> wireguard-DEV1-S (10.8.0.1 / 10.42.1.5)
  -> wazuh-Dev1-S (10.42.1.7)
  -> dashboard Wazuh interne

IPC
  -> Teltonika
  -> WireGuard site
  -> wireguard-DEV1-S
  -> wazuh-Dev1-S
  -> Wazuh manager
  -> Wazuh indexer
  -> Wazuh dashboard
  -> control panel (vue operateur / lien externe / flux live)
```

## 4. Comment Wazuh fonctionne dans notre contexte

## 4.1 Chaine technique

Dans notre implementation, la chaine technique est la suivante :

```text
Service IPC / journald / modules Wazuh
  ->
wazuh-agent sur l'IPC
  ->
connexion agent TCP vers Wazuh manager
  ->
analyse manager (decodeurs / regles / enrichissement)
  ->
indexation dans Wazuh indexer
  ->
consultation via Wazuh dashboard
  ->
eventuellement lecture recentre par le control panel
```

## 4.2 Composants et role de chacun

### Wazuh agent

Le `wazuh-agent` tourne sur l'IPC et sert a :

- maintenir une connexion avec le manager ;
- remonter des logs, notamment via `journald` / `localfile` ;
- fournir les fonctions Wazuh natives comme `syscheck`, `sca`,
  `syscollector`, etc. ;
- executer le bootstrap d'enrollment vers le manager.

### Wazuh manager

Le manager :

- recoit la connexion des agents ;
- gere l'enrollment ;
- applique les decodeurs et les regles ;
- transforme les evenements bruts en alertes Wazuh exploitables ;
- alimente ensuite l'indexer via la pile Wazuh locale.

### Wazuh indexer

L'indexer stocke les evenements et alertes dans des index
`OpenSearch-compatible`, notamment `wazuh-alerts-*`.

Il sert :

- au dashboard Wazuh ;
- au connecteur backend du `control panel` lorsqu'on veut afficher une file
  operateur Wazuh dans l'UI interne.

### Wazuh dashboard

Le dashboard fournit :

- la visualisation native Wazuh ;
- le triage securite detaille ;
- la recherche par agent, severite, regle, groupe, periode ;
- les vues de supervision et de sante.

### Control panel

Le `control panel` ne remplace pas Wazuh. Son role est plutot de :

- servir de point d'entree operateur ;
- fournir un bouton de renvoi direct vers le dashboard Wazuh ;
- afficher une file simplifiee d'alertes recentes via le backend ;
- conserver un workflow de qualification local si besoin.

Le detail d'analyse reste du ressort de Wazuh.

## 5. Protocoles et ports utilises

## 5.1 Flux actuellement utiles

| Port | Protocole | Sens | Usage |
| --- | --- | --- | --- |
| `22` | TCP | admin -> VMs | SSH |
| `443` | TCP | admin -> `wazuh-Dev1-S` | dashboard Wazuh HTTPS |
| `1514` | TCP | IPC -> manager | transport agent Wazuh |
| `1515` | TCP | IPC -> manager | enrollment Wazuh |
| `55000` | TCP | `control-panel` -> Wazuh | API manager optionnelle |
| `9200` | TCP | `control-panel` -> Wazuh | acces indexer prive pour flux d'alertes |
| `51820` | UDP | WireGuard peers | tunnel WireGuard |
| `53` | UDP/TCP | clients WG -> `wireguard-DEV1-S` | DNS interne `dnsmasq` |

## 5.2 Protocoles dans l'ecosysteme

### WireGuard

Utilise pour :

- l'administration privee ;
- l'acces aux VMs privees ;
- le transport IPC -> Wazuh prive ;
- la resolution DNS interne via le hub.

Sous-reseaux principaux :

- admin overlay : `10.8.0.0/24`
- cloud prive : `10.42.0.0/16`
- LAN site : `192.168.10.0/24`
- reseau process : `192.168.50.0/24`

### Wazuh agent transport

Le couple principal est :

- `1515/TCP` pour l'enrollment ;
- `1514/TCP` pour la connexion agent/manager.

Dans notre design cible, ces ports ne doivent plus dependre du NAT public du
site.

### HTTPS dashboard

Le dashboard Wazuh est maintenant expose en HTTPS interne sur :

- `https://wazuh.cascadya.internal`

Le certificat est actuellement un certificat dedie autosigne genere par
Ansible.

### DNS interne

Le DNS interne est fourni par `dnsmasq` sur `wireguard-DEV1-S`.

Resolution cible validee :

- `control-panel.cascadya.internal -> 10.42.1.2`
- `wazuh.cascadya.internal -> 10.42.1.7`

### Indexer HTTPS

Le `control panel` peut lire les alertes recentes via l'indexer Wazuh sur :

- `https://10.42.1.7:9200`

Ce flux est prive, borne au backend, et n'est pas un endpoint admin a exposer
publiquement.

## 6. Configuration actuellement en place

## 6.1 Couche infrastructure / Terraform

Dans le repo `Infra-MVP`, le SG Wazuh est aujourd'hui modele de facon assez
propre :

- `22/TCP` limite aux CIDRs admin autorises ;
- `443/TCP` limite aux CIDRs admin autorises ;
- `1514/TCP` et `1515/TCP` limites a `allowed_wazuh_ipc_cidrs` ;
- `allowed_wazuh_ipc_cidrs = [10.8.0.0/24]` ;
- `allowed_wazuh_ipc_public_cidrs = []` ;
- `55000/TCP` autorise uniquement depuis l'IP publique du control panel.

Cela traduit la cible suivante :

- administration Wazuh via VPN / IPs admin ;
- transport agent Wazuh via overlay WireGuard ;
- plus de fallback public par defaut pour `1514` et `1515`.

## 6.2 Couche routage / WireGuard

Les changements reseau les plus importants sont :

- le Teltonika annonce maintenant `10.42.1.7/32` dans son peer `VM_Cloud` ;
- `wazuh-dev1-s` route de facon persistante :
  - `192.168.10.0/24 via 10.42.1.5`
  - `192.168.50.0/24 via 10.42.1.5`
  - `10.8.0.0/24 via 10.42.1.5`
- ces routes sont persistees via :
  - `/etc/netplan/60-wazuh-private-routes.yaml`
- le test de reboot Teltonika a confirme que le chemin prive remonte seul.

Choix important :

- nous avons privilegie le **routage propre** via `wireguard-DEV1-S`
- et non un SNAT opaque comme solution durable.

## 6.3 Couche Wazuh manager / dashboard

Les elements validates cote Wazuh sont :

- VM `wazuh-Dev1-S` en mode `all-in-one`
- dashboard HTTPS
- FQDN interne `wazuh.cascadya.internal`
- certificat dedie pour ce FQDN
- service `wazuh-dashboard` configure avec :
  - `server.name = wazuh.cascadya.internal`
  - `server.host = 0.0.0.0`
  - `server.port = 443`
  - `server.ssl.enabled = true`

## 6.4 Couche provisioning IPC

Le role `wazuh-agent` est maintenant integre au provisioning.

Ce que fait le playbook :

- installe le paquet `wazuh-agent`
- gere le repo apt Wazuh
- rend le paquet `hold`
- remplace le bloc `<client>` de `ossec.conf`
- configure :
  - manager address
  - enrollment server
  - port `1514`
  - port `1515`
  - agent name
  - groupe Wazuh eventuel
  - password d'enrollment eventuel
  - CA d'enrollment eventuelle
- redemarre proprement l'agent si necessaire

Le playbook de validation confirme :

- presence du paquet
- presence du service
- reachability `1514/TCP`
- reachability `1515/TCP`
- session TCP etablie
- journal agent exploitable

## 6.5 Defaults du control panel

Les defaults Wazuh importants du `control panel` pointent maintenant vers
l'IP privee du manager :

- `AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_ADDRESS_DEFAULT=10.42.1.7`
- `AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_PORT_DEFAULT=1514`
- `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_SERVER_DEFAULT=10.42.1.7`
- `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_PORT_DEFAULT=1515`

Cela garantit que les futurs IPC provisionnes heritent par defaut du bon
chemin prive.

## 6.6 Dashboard Wazuh dans le control panel

Le `control panel` expose un endpoint backend `/api/ui/config` qui fournit
l'URL du dashboard Wazuh.

Aujourd'hui, la cible est :

- `AUTH_PROTO_WAZUH_DASHBOARD_URL=https://wazuh.cascadya.internal`

Le bouton Wazuh de la page `Alerts` ouvre donc le vrai dashboard Wazuh
interne, et non un faux panneau du `control panel`.

## 6.7 Flux live d'alertes vers le control panel

Le backend `control-panel-auth` expose un endpoint :

- `/api/alerts/live`

Ce flux :

- interroge l'indexer prive ;
- lit les index `wazuh-alerts-*` ;
- normalise les hits Wazuh dans un format de file operateur ;
- alimente la page Alerts du `control panel`.

Les variables de configuration prevues pour ce connecteur sont :

- `AUTH_PROTO_WAZUH_ALERTS_INDEXER_URL`
- `AUTH_PROTO_WAZUH_ALERTS_INDEXER_USERNAME`
- `AUTH_PROTO_WAZUH_ALERTS_INDEXER_PASSWORD`
- `AUTH_PROTO_WAZUH_ALERTS_INDEX_PATTERN`
- `AUTH_PROTO_WAZUH_ALERTS_VERIFY_TLS`
- `AUTH_PROTO_WAZUH_ALERTS_CA_CERT_PATH`

Important :

- dans le repo, l'URL est deja pre-rensee vers `https://10.42.1.7:9200` ;
- en revanche, les credentials indexer ne sont pas stockes en clair dans le
  repo ;
- l'activation reelle depend donc d'un injection secrete cote runtime.

## 7. Ce qui a deja ete valide

Validations obtenues sur le premier IPC de reference :

- `cascadya-ipc-10-109` provisionne avec succes ;
- `wazuh-agent` `active/enabled` ;
- connexion agent validee d'abord en public puis en prive ;
- bascule finale vers `10.42.1.7` ;
- `gateway_modbus.service` remonte dans Wazuh ;
- decodeur `cascadya_gateway` valide ;
- regles custom `100520` et `100521` valides ;
- `100521` observee apres reboot du Teltonika, donc sans dependance au NAT
  public du site.

Ces validations sont tres importantes, car elles montrent que nous ne sommes
plus seulement au niveau "installation Wazuh", mais deja au niveau "chaine
metier instrumentee et visible".

## 8. Choix techniques retenus et pourquoi

## 8.1 All-in-one plutot que multi-noeuds

Choix retenu :

- `all-in-one`

Pourquoi :

- plus rapide a livrer ;
- plus facile a operer ;
- suffisant pour un premier lab `Dev1` ;
- cout plus faible.

Limite :

- pas HA ;
- pas d'isolation forte entre stockage / moteur / interface.

## 8.2 Transport prive WireGuard plutot que dependance au public

Choix retenu :

- chemin prive `WireGuard -> 10.42.1.7`

Pourquoi :

- supprime la dependance au NAT public du site ;
- plus stable ;
- plus proche de la cible securisee ;
- deja aligne avec l'architecture admin privee existante.

Limite :

- demande de gerer les routes aller et retour ;
- demande de maintenir la sante du hub WireGuard et du routeur site.

## 8.3 DNS interne + HTTPS interne

Choix retenu :

- `wazuh.cascadya.internal`
- DNS interne via `dnsmasq`
- HTTPS interne dedie

Pourquoi :

- meilleur UX operateur ;
- plus propre qu'une IP ou un tunnel local `8443` ;
- facilite le renvoi depuis le `control panel`.

Limite :

- certificat encore autosigne ;
- devra evoluer vers une vraie CA interne si l'on veut un parcours sans
  warning navigateur.

## 8.4 Control panel comme point d'entree, pas comme remplacant de Wazuh

Choix retenu :

- le `control panel` sert de point d'entree et de file simplifiee ;
- Wazuh reste la source d'analyse detaillee.

Pourquoi :

- evite de dupliquer un SIEM dans le `control panel` ;
- garde un vrai outil securite comme surface de triage detaille ;
- laisse au `control panel` le role orchestration / operations.

## 8.5 Provisioning idempotent

Choix retenu :

- faire porter la configuration Wazuh et les routes derives dans les playbooks.

Pourquoi :

- tous les nouveaux IPC doivent reproduire le meme comportement que l'IPC de
  reference ;
- on veut eviter les patchs manuels machine par machine ;
- on veut pouvoir rejouer sans effets de bord.

## 9. Options que nous avons encore

## 9.1 Options d'architecture Wazuh

### Option A - garder le modele all-in-one

Adapte si :

- peu d'IPC ;
- faible retention ;
- besoin de vitesse et de simplicite.

### Option B - separer manager / indexer / dashboard

Adapte si :

- volumetrie en hausse ;
- besoin d'isoler le stockage ;
- besoin d'un meilleur tuning de performance ;
- preparation d'une cible plus proche de la production.

### Option C - cluster HA

Adapte si :

- plusieurs environnements ;
- besoin de resilience forte ;
- criticite plus elevee.

Ce n'est pas une priorite a court terme pour `Dev1`.

## 9.2 Options de collecte cote IPC

### Option A - config centralisee manager-side via groupes Wazuh

C'est l'option la plus souple pour iterer vite.

Avantages :

- permet de faire evoluer `agent.conf` sans redeployer tous les IPC ;
- tres bien adaptee a une phase MVP / lab.

### Option B - config `ossec.conf` pilotee entierement par provisioning

Avantages :

- tres deterministe ;
- pleinement versionnee dans notre repo.

Limites :

- moins flexible ;
- plus lourd a faire evoluer.

### Option C - syslog forwarding

Possible, mais pas recommande pour les IPC deja equipes d'un agent Wazuh.

### Option D - command monitoring

Interessant pour :

- `systemctl is-active gateway_modbus.service`
- `systemctl is-active telemetry_publisher.service`
- `systemctl is-active wg-quick@wg0.service`

Bonne option en phase 2 si l'on veut des etats explicites au-dela des logs.

### Option E - file integrity monitoring

Tres utile plus tard pour :

- les certificats ;
- les bundles de cle ;
- les repertoires `unlock` ;
- les fichiers de persistence reseau.

## 9.3 Options d'integration avec le control panel

### Option A - simple deep link vers le dashboard Wazuh

Deja en place.

### Option B - file live via indexer `9200`

Deja implementee cote code, a finaliser cote credentials si necessaire.

### Option C - integration via API manager `55000`

Possible plus tard pour :

- enrichir des workflows ;
- piloter certaines operations Wazuh ;
- synchroniser des vues plus riches.

### Option D - SSO / federation d'identite

Pas encore en place.

Ce serait une evolution logique si l'on veut :

- un acces fluide depuis le `control panel` ;
- une meilleure gestion des roles ;
- une experience plus propre pour les equipes.

## 10. Ce que nous pouvons encore faire avec Wazuh

## 10.1 Cas d'usage techniques immediats

Nous pouvons etendre rapidement Wazuh pour couvrir :

- `remote-unlock`
- `wg-quick@wg0.service`
- `cascadya-network-persist.service`
- `telemetry_publisher.service`
- la sante locale de `wazuh-Dev1-S`
- les alertes administrateur / sudo / SSH sur les VMs critiques

## 10.2 Cas d'usage operations / production

Wazuh peut aussi devenir un vrai socle de supervision securite et exploitation
pour :

- statut agent par IPC ;
- perte de connectivite d'un site ;
- derive de configuration ;
- invalidation ou disparition de certificats ;
- incident runtime edge-agent ;
- verification que le chemin `WireGuard -> broker -> IPC` reste sain ;
- inventaire logiciel / systeme via `syscollector` ;
- posture securite via `SCA` ;
- veille de changements sensibles via `syscheck`.

## 10.3 Cas d'usage de visualisation

Nous pouvons construire des vues dediees :

- `IPC Health`
- `Remote Unlock / WireGuard`
- `Edge Agent Runtime`
- `Wazuh Manager VM Health`
- `Site Security Overview`

## 10.4 Cas d'usage d'automatisation

Plus tard, Wazuh peut aussi servir de declencheur pour :

- notifications Teams / mail ;
- remediations bornees ;
- workflows operateur dans le `control panel`.

Il faudra etre prudent avec les `active response` automatiques, afin de ne pas
creer de reactions parasites sur des sites industriels.

## 11. Limites et points d'attention actuels

## 11.1 Pas encore une cible production HA

Le lab est robuste pour `Dev1`, mais :

- pas de HA ;
- pas de cluster indexer ;
- pas de separation forte des roles.

## 11.2 Certificats du dashboard

Le dashboard interne fonctionne, mais :

- le certificat est dedie et autosigne ;
- il faudra une CA interne pour une industrialisation propre.

## 11.3 Connecteur live du control panel

Le connecteur backend vers l'indexer existe, mais :

- il depend d'un couple `username/password` dedie ;
- il faut une gestion secrete propre ;
- il faudra idealement activer une verification TLS stricte avec CA dediee.

## 11.4 Couverture d'alertes encore partielle

Aujourd'hui, nous avons valide la brique `gateway_modbus`.

Il reste a enrichir :

- `remote-unlock`
- `WireGuard`
- `telemetry_publisher`
- `network-persist`
- la sante locale de `wazuh-Dev1-S`

## 11.5 Discipline de securite a garder

Le principe a maintenir est :

- ne pas reouvrir des ports publics par confort ;
- garder le chemin prive comme mode nominal ;
- garder `9200` hors exposition publique ;
- limiter `55000` au `control panel` / bastion ;
- eviter de deriver vers une duplication du dashboard Wazuh dans le `control panel`.

## 12. Recommandations concretes pour la suite

## 12.1 Court terme

1. Finaliser la collecte des services critiques cote IPC :
   `remote-unlock`, `WireGuard`, `telemetry_publisher`, `network-persist`.
2. Finaliser les decodeurs et regles custom Cascadya cote manager.
3. Stabiliser les credentials du connecteur `control panel -> indexer`.
4. Verifier que toutes les ouvertures reseau publiques exceptionnelles ont bien
   ete retirees apres migration privee.

## 12.2 Moyen terme

1. Ajouter des vues dashboard Wazuh dediees a l'exploitation.
2. Mettre en place un vrai `nats.cascadya.internal` sur le meme modele que le
   dashboard Wazuh.
3. Enrichir les groupes Wazuh par site ou typologie d'IPC.
4. Ajouter de la supervision locale de la VM Wazuh elle-meme.

## 12.3 Plus long terme

1. SSO / federation avec le `control panel`.
2. Durcissement TLS complet avec CA interne.
3. Revue d'une architecture plus separee si la volumetrie augmente.
4. Eventuelle integration de workflows de remediation bornees.

## 13. Message cle a presenter a l'equipe

Le message principal a faire passer demain est le suivant :

- nous avons deja une brique Wazuh fonctionnelle et reliee a un IPC reel ;
- nous avons quitte un mode de preuve par IP publique pour un mode prive plus
  propre via WireGuard ;
- nous avons deja un dashboard interne accessible proprement ;
- nous avons deja un debut d'integration produit avec le `control panel` ;
- nous avons une base saine pour passer d'un "agent connecte" a une vraie
  supervision securite et runtime des IPC ;
- la suite ne demande pas un redesign complet, mais un enrichissement progressif
  des sources, des decodeurs, des vues et des secrets d'integration.

## 14. Trame de presentation conseillee

Si tu veux une trame courte de presentation a 10h :

1. Expliquer le besoin :
   centraliser la securite et la sante runtime des IPC.
2. Montrer l'architecture :
   IPC -> Wazuh agent -> manager/indexer/dashboard.
3. Expliquer le changement cle :
   passage du chemin public au chemin prive WireGuard.
4. Montrer la valeur immediate :
   alertes `gateway_modbus`, dashboard Wazuh interne, file operateur.
5. Expliquer les choix :
   `all-in-one`, DNS interne, HTTPS interne, provisioning idempotent.
6. Expliquer la suite :
   plus de services collects, plus de regles, plus de vues, meilleure
   integration control panel.

## 15. Sources de verite dans le repo

Documents et fichiers les plus utiles pour justifier cette architecture :

- `PRD_LOT_7_WAZUH_MANAGER_VM.md`
- `DOC_TOPOLOGIE_WIREGUARD_WAZUH_2026-04-07.md`
- `WAZUH_MVP_LINK_PLAN.md`
- `ansible/roles/wazuh_dashboard/tasks/main.yml`
- `provisioning_ansible/roles/wazuh-agent/tasks/main.yml`
- `provisioning_ansible/wazuh-agent-validate.yml`
- `app/config.py`
- `app/main.py`
- `app/wazuh_alerts.py`
- `frontend/src/modules/alerts/views/AlertsView.vue`
