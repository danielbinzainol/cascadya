# PRD - Lot 5 - E2E telemetrie NATS, WireGuard-only et observabilite broker

## 1. Objet

Ce document definit le lot 5 du Control Panel au 1 avril 2026, dans la
continuite du lot 4 `provisioning IPC + remote-unlock + edge-agent`.

Le lot 5 ajoute une premiere capacite d'observabilite temps quasi reel
orientee usage terrain :

- tester le flux telemetrie entre `Control Panel VM`, `Broker VM` et
  `Industrial PC` ;
- distinguer plusieurs flux observables, notamment `ems-site` et
  `ems-light` ;
- mesurer un round-trip `request/reply` NATS pilote depuis le dashboard ;
- exploiter les endpoints de monitoring NATS `healthz`, `varz` et `connz` ;
- observer le flux `Orders` vu par le broker et l'exposer dans un panneau
  dedie ;
- fournir un premier panneau `Execution` pour envoyer des commandes placeholder
  vers le PLC via le broker ;
- rendre explicite la separation entre :
  - l'URL NATS utilisee par l'IPC ;
  - l'URL NATS utilisee par le control plane pour lancer un probe E2E ;
- eliminer les dependances implicites a des adresses `Tailscale` dans le
  provisioning edge-agent.

L'objectif n'est pas encore de livrer une plateforme complete d'observabilite
historisee. Le but est de poser un premier chemin produit fiable pour :

- prouver qu'un IPC parle bien au broker ;
- afficher des mesures interpretable par un operateur ;
- preparer une IHM web d'execution pour la partie commandes et supervision active ;
- rendre visible les trous de routage entre control plane, broker et IPC.

## 2. Contexte

Le lot 4 a apporte :

- le provisioning complet `full-ipc-wireguard-onboarding` ;
- la generation du bundle TLS edge-agent ;
- le deploiement et la validation structurelle de l'edge-agent ;
- la mise en place du broker `remote-unlock` et du lien `WireGuard`.

Les tests du 31 mars 2026 et du 1 avril 2026 ont montre un point important :

- l'IPC joignait le broker NATS via `WireGuard` sur `10.30.0.1:4222` ;
- les anciens defaults `tls://100.103.71.126:4222` etaient des reliquats
  `Tailscale` et n'etaient plus valides ;
- le control plane ne disposait pas, a ce stade, d'un chemin reseau
  equivalente vers ce meme endpoint ;
- un seul champ `edge_agent_nats_url` ne suffit donc pas a couvrir
  simultanement :
  - la connectivite runtime de l'IPC ;
  - le probe E2E lance depuis le control plane.

Le lot 5 formalise cette realite reseau dans le produit.

## 3. Objectifs du lot 5

- Ajouter un test E2E NATS pilotable depuis l'UI.
- Ajouter une API backend dediee au probe E2E.
- Ajouter un step de verification NATS au catalogue de workflows.
- Basculer les defaults edge-agent vers un mode `WireGuard-only`.
- Introduire des variables distinctes pour les chemins reseau :
  - `edge_agent_nats_url`
  - `edge_agent_probe_nats_url`
  - `edge_agent_probe_broker_url`
  - `edge_agent_nats_monitoring_url`
  - `edge_agent_probe_monitoring_url`
- Permettre a l'UI E2E de basculer entre un flux `ems-site` cible par IPC et
  un flux global singleton `ems-light`.
- Exploiter `/healthz`, `/varz` et `/connz` du broker NATS pour presenter
  des mesures operateur lisibles.
- Eviter qu'un probe control-plane reutilise silencieusement une URL reservee
  a l'IPC.
- Permettre au broker de publier un endpoint HTTPS de probe dedie au control
  plane, sans exposition publique brute de `4222` ni de `8222`.
- Ajouter un ecran `Orders` dans la topbar pour :
  - visualiser le FIFO des ordres observes sur le broker ;
  - regler la frequence de refresh ;
  - envoyer des commandes placeholder request/reply vers le PLC.

## 4. Perimetre fonctionnel

### 4.1 Dashboard E2E

Le dashboard doit permettre :

- d'ouvrir une vue `Test E2E` depuis un site ;
- de selectionner un type de flux ;
- de selectionner un `industrial_pc` actif quand le flux choisi est
  `ems-site` ;
- de choisir un mode `manuel` ou `auto` ;
- de lancer ensuite un test `request/reply` via le broker ;
- d'afficher :
  - le round-trip global ;
  - une cascade temporelle avec le total sur une ligne dedicate et les
    composants actifs sur des lignes separees mais a la meme echelle ;
  - les composantes actives du test ;
  - les canaux NATS distincts issus de `connz` ;
  - le payload envoye ;
  - le payload recu ;
  - les warnings de monitoring.

Comportement retenu au 2 avril 2026 :

- le select `Flux` propose `ems-site` et `ems-light` ;
- `ems-site` conserve le select `Industrial PC` ;
- `ems-light` masque ce select car il s'agit d'un singleton global partage par
  tout le systeme ;
- le choix `Mode manuel` / `Mode auto` ne lance rien a lui seul ; il ne fait
  qu'exposer les options du mode courant ;
- en `mode manuel`, l'UI expose :
  - `Mesures`
  - `Cadence mesures`
  - un unique bouton `Lancer`
- en `mode auto`, l'UI expose :
  - `Frequence auto`
  - un unique bouton `Lancer` / `Arreter auto`
- les options du mode non selectionne sont masquees ;
- un bouton `Reset graph` vide l'historique local du graphe ;
- en `mode manuel`, `N mesures` a `1 mesure / Xs` doivent produire `N points`
  distincts dans le temps ;
- les RTT issus de `/connz` sont presentes comme des snapshots de canaux et non
  comme des segments additifs du total ;
- la cascade du haut somme uniquement les composantes du test actif.

### 4.2 API E2E

Le backend doit exposer un endpoint dedie :

- `POST /api/e2e/tests`

Ce endpoint doit :

- verifier que l'asset selectionne existe ;
- verifier qu'il est rattache au bon site ;
- verifier que le chemin de probe control-plane disponible est coherent :
  - bundle TLS edge-agent si le control plane parle directement au broker NATS ;
  - token + CA broker si le control plane passe par le proxy HTTPS du broker ;
- lancer le probe NATS direct ou via le proxy broker ;
- retourner un JSON exploitable directement par l'UI.

Le payload de requete peut maintenant expliciter :

- `flow_key=ems_site`
- `flow_key=ems_light`

Le backend doit appliquer les regles suivantes :

- `ems_site` requiert un asset IPC cible ;
- `ems_light` n'en requiert pas et observe la connexion singleton
  `iec104-bridge` cote broker.

Precondition produit :

- si `iec104-bridge` n'est pas visible dans `/connz`, le flux `ems-light` est
  considere comme indisponible et le broker retourne une erreur explicite.

### 4.3 Verification dans les workflows

Le catalogue de workflows de provisioning doit inclure un step de verification
NATS explicite :

- `edge-agent-nats-roundtrip.yml`

Ce step doit :

- etre visible dans le workflow ;
- utiliser le meme moteur de probe que l'API E2E ;
- savoir appeler le proxy HTTPS du broker quand aucun acces direct `4222` n'est
  disponible depuis le control plane ;
- etre capable de se terminer proprement si aucun endpoint control-plane
  joignable n'est configure.

### 4.4 Ecran Orders et execution placeholder

Le produit expose aussi une entree `Orders` dans la topbar.

Cet ecran doit permettre :

- de lire le flux `cascadya.routing.command` vu par le broker ;
- d'afficher un FIFO de messages retenus ;
- de regler la frequence de refresh et la profondeur affichee ;
- d'ouvrir le detail d'un ordre observe ;
- de montrer un panneau `Execution` web dedie aux commandes et au watchdog.

Clarification du 14 avril 2026 :

- l'ecran `Orders` observe aujourd'hui le flux broker et non l'etat canonique du
  planificateur Modbus expose en `%MW100+` ;
- il constitue donc un outillage d'observabilite et de test de commandes, pas
  encore une lecture fidele du planificateur SBC.

La zone `Execution` couvre a ce stade :

- un `watchdog ping` sur `cascadya.routing.ping` ;
- des presets temporels ;
- des profils de consigne (`Elec Priority`, `Gas Standby`, `Degraded`) ;
- un planificateur placeholder pour `upsert`, `delete` et `reset` ;
- un `Execution log` FIFO cote UI.

### 4.5 API Orders

Le backend doit exposer :

- `GET /api/orders/live`
- `POST /api/orders/dispatch`

Capacites cibles :

- lecture du flux Orders via le proxy broker ;
- retention FIFO bornee cote broker ;
- publication request/reply de commandes placeholder ;
- retour de payloads exploitables directement par l'UI.

Etat implemente et retenu au 14 avril 2026 :

- `GET /api/orders/live` lit le flux `Orders` via le proxy broker ;
- `POST /api/orders/dispatch` envoie des commandes request/reply vers le sujet
  partage `cascadya.routing.command` ;
- la gateway IPC impose maintenant une cible explicite sur ce sujet partage et
  rejette les commandes sans cible ou destinees a un autre IPC ;
- cette API ne relit pas encore le planificateur `%MW100+` du SBC, meme si la
  gateway IPC expose maintenant une action canonique `read_plan`.

## 5. Architecture cible du lot 5

```text
Navigateur VPN
   ->
Traefik
   ->
FastAPI Control Panel
   ->
API /api/e2e/tests
   ->
choix du chemin de probe control-plane
   ->
  A. acces direct NATS TLS avec bundle edge-agent
     ->
     Broker NATS
  B. proxy HTTPS dedie sur le broker
     ->
     probe NATS local au broker
     ->
     Broker NATS
    ->  request/reply sur cascadya.routing.ping
Industrial PC

En parallele :
Broker monitoring endpoints (locaux au broker ou proxifies)
   ->
/healthz
/varz
/connz
   ->
dashboard E2E
```

Important :

- le chemin `IPC -> Broker` peut etre `WireGuard-only` ;
- le chemin `Control Plane -> Broker` peut etre different ;
- le produit doit le modeliser explicitement au lieu de supposer qu'une seule
  URL convient a tous les usages.
- quand le control plane ne peut pas joindre directement `4222/8222`, le
  broker doit pouvoir exposer un endpoint HTTPS borne et authentifie.

## 6. Variables et conventions cibles

### 6.1 Variables IPC

`edge_agent_nats_url`

- usage : connexion runtime de l'IPC vers le broker ;
- cible par defaut en environnement `WireGuard-only` :
  - `tls://10.30.0.1:4222`

`edge_agent_nats_monitoring_url`

- usage : endpoint de monitoring du broker associe a l'URL IPC ;
- exemple :
  - `http://10.30.0.1:8222`

### 6.2 Variables probe control-plane

`edge_agent_probe_nats_url`

- usage : URL NATS joignable depuis le control plane pour le test E2E ;
- elle ne doit pas etre deduite automatiquement depuis `edge_agent_nats_url`
  si la topologie reseau est differente.

`edge_agent_probe_monitoring_url`

- usage : endpoint `connz/varz/healthz` joignable depuis le control plane ;
- optionnel mais fortement recommande pour afficher les mesures enrichies.

`edge_agent_probe_broker_url`

- usage : endpoint HTTPS du broker dedie au probe control-plane ;
- attendu quand le control plane ne peut pas joindre directement `4222` ;
- exemple :
  - `https://51.15.64.139:9443`

### 6.3 Variables broker-side proxy

Variables cote control plane :

- `AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_URL_DEFAULT`
- `AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_TOKEN`
- `AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_CA_CERT_PATH`
- `AUTH_PROTO_PROVISIONING_NATS_SERVER_CA_CERT_PATH`

Variables cote broker deployment :

- `remote_unlock_broker_control_plane_probe_enable`
- `remote_unlock_broker_control_plane_probe_bind_port`
- `remote_unlock_broker_control_plane_probe_nats_url`
- `remote_unlock_broker_control_plane_probe_monitoring_url`
- `remote_unlock_broker_control_plane_probe_ca_cert_src`

Variables cote generation du bundle edge-agent :

- `edge_agent_nats_server_ca_cert_path`

Regle de separation des CAs :

- `AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_CA_CERT_PATH` sert a
  verifier le certificat HTTPS du proxy broker vu depuis le control plane ;
- `AUTH_PROTO_PROVISIONING_NATS_SERVER_CA_CERT_PATH` sert a verifier le
  certificat TLS du vrai serveur NATS ;
- ces deux CAs peuvent etre differentes et ne doivent plus etre confondues ;
- quand la CA serveur NATS est fournie :
  - le broker la recoit pour son probe NATS local ;
  - le bundle edge-agent la recoit comme `nats-ca.crt` ;
  - `ca.crt` reste reserve a la chaine attendue pour le certificat client
    edge-agent.

Contrainte de securite :

- le proxy broker expose un endpoint HTTPS borne ;
- l'acces est protege par un bearer token ;
- le broker effectue lui-meme le probe NATS local ;
- le produit n'expose pas publiquement `4222` ni `8222`.

## 7. Metriques NATS cibles

Le lot 5 s'appuie sur la documentation officielle NATS pour le monitoring :

- `/healthz`
- `/varz`
- `/connz`

Mesures minimales attendues dans le dashboard :

- statut `healthz` ;
- nom et version du broker depuis `varz` ;
- nombre de connexions, de messages et de slow consumers ;
- snapshots `connz` pour :
  - la connexion du probe control-plane ;
  - `gateway_modbus_edge:<inventory_hostname>` ;
  - `telemetry_publisher_edge:<inventory_hostname>` ;
  - `iec104-bridge` pour le flux `ems-light`

Mesures derivees cibles :

- `Control Panel -> Broker RTT`
- `Traitement broker`
- `Broker -> IPC gateway RTT`
- `Broker -> IPC telemetry RTT`
- `Broker -> ems-light RTT`
- `Control Panel -> Broker -> IPC -> Broker -> Control Panel`

Presentation operateur retenue au 2 avril 2026 :

- la terminologie visible cote UI emploie `Traitement broker` plutot que
  `Broker proxy processing` ;
- `ems-site` et `ems-light` exposent tous deux :
  - `RTT actif (avec traitement broker)`
  - `RTT actif (sans traitement broker)`
- `ems-site` reconstitue :
  - `Control Panel <-> Broker VM`
  - `Traitement broker`
  - `Broker VM <-> Industrial PC`
  - `Industrial PC <-> Modbus Simulator`
- `ems-light` reconstitue :
  - `Control Panel <-> Broker VM`
  - `Traitement broker`
  - `Broker VM <-> ems-light`

Regle d'interpretation retenue :

- les RTT `/connz` sont des snapshots de connexions broker-side ;
- ils sont utiles pour l'observabilite et le diagnostic reseau ;
- ils ne constituent pas, a eux seuls, la mesure canonique de la latence
  applicative de bout en bout ;
- la latence du `hot flow` telemetrie doit etre mesuree par instrumentation
  applicative ou scripts horodates par segment.

## 8. Capacites techniques cibles

### 8.1 Nommage des connexions NATS

Les services edge-agent doivent publier un nom de connexion stable et lisible
par `connz` :

- `gateway_modbus_edge:<inventory_hostname>`
- `telemetry_publisher_edge:<inventory_hostname>`

Le probe control-plane doit publier un nom ephemere mais identifiable :

- `control_panel_e2e_probe:<inventory_hostname>:<request_id>`

### 8.2 Payload du probe

Le probe doit envoyer un payload JSON contenant au minimum :

- `compteur`
- `request_id`
- `control_panel_sent_at`
- `asset_name`

La reponse edge-agent doit renvoyer au minimum :

- `status`
- `valeur_retour`
- `request_id`
- `edge_instance_id`
- `edge_received_at`
- `edge_replied_at`

### 8.3 Restitution UI

La vue E2E doit presenter :

- un select `Flux` ;
- un select d'IPC seulement pour `ems-site` ;
- un choix explicite `Mode manuel` / `Mode auto` ;
- un bouton `Lancer` distinct du choix de mode ;
- des cards de synthese ;
- une cascade de temps avec total et composants actifs ;
- un graphe a points montrant l'evolution du RTT dans le temps ;
- une table de statistiques batch (`min`, `avg`, `median`, `p95`, `max`,
  `std dev`) ;
- une section distincte pour les canaux NATS observes via `connz` ;
- un tableau des connexions broker ;
- les payloads bruts ;
- les warnings.

### 8.4 Multiplexage des flux E2E

Le lot 5 couvre maintenant deux flux visibles dans la meme page :

- `ems-site`
  - chemin cible : `Control Panel -> Broker -> Industrial PC`
  - selection d'un IPC requise ;
- `ems-light`
  - chemin cible : `Control Panel -> Broker -> ems-light`
  - aucun IPC particulier a selectionner.

Le flux `ems-light` reste un singleton global :

- sa visualisation ne doit pas dependre d'une fiche site ;
- sa connexion broker-side est observee via `iec104-bridge`.

Nuance d'exploitation retenue au 2 avril 2026 :

- dans le lab courant, la disponibilite de `iec104-bridge` peut dependre de la
  machine amont qui porte effectivement la connectivite ou la session utile ;
- si cette machine perd sa connectivite, `ems-light` peut disparaitre de
  `/connz` et redevenir indisponible cote produit.

### 8.5 Panneau Orders

Le panneau `Orders` doit presenter :

- un resume du flux Orders observe sur le broker ;
- un select de refresh (`manuel`, `1s`, `2s`, `5s`, `10s`, `30s`) ;
- un select de profondeur FIFO (`25`, `50`, `100`, `200`) ;
- le detail du dernier ordre ou de l'ordre selectionne ;
- les warnings et l'etat de connexion du tap broker.

Le FIFO cote broker doit :

- retenir un nombre borne de messages ;
- evincer les plus anciens quand la limite est atteinte ;
- exposer le nombre total vu et le nombre retenu.

### 8.6 Panneau Execution

Le panneau `Execution` constitue l'IHM web cible pour les commandes et le watchdog.

Etat retenu au 2 avril 2026 :

- la zone `Controls` a ete remontee sous le nom `Execution` ;
- elle regroupe watchdog, quick tools, profils et planificateur placeholder ;
- elle reutilise les sujets :
  - `cascadya.routing.ping`
  - `cascadya.routing.command`
- elle garde volontairement un perimetre placeholder tant que la traduction
  JSON <-> Modbus cote IPC n'est pas completement recablee.

Le sous-arbre legacy `auth_prototype/legacy_wsl_ihm/` n'est plus conserve dans le
repo produit. La reference active est l'IHM web du control panel.

Clarification du 14 avril 2026 :

- le champ `target asset` n'est plus un simple hint : il fait maintenant partie
  du contrat de commande attendu par la gateway IPC ;
- le sujet `cascadya.routing.command` reste partage, mais il est maintenant
  protege par un filtrage cible explicite cote gateway ;
- la convergence Modbus cote edge a progresse : la pile canonique est
  maintenant lue en `%MW100+` via `read_plan`, tandis que le runtime actif a ete
  deplace en `%MW700+` ;
- les champs de ciblage supportes cote gateway sont `asset_name`,
  `target_asset`, `edge_instance_id` et `inventory_hostname` ;
- une commande sans cible est rejetee en `missing_target`, et une commande pour
  un autre IPC est rejetee en `target_mismatch` ;
- aucun bouton web distinct d'activation/desactivation du pilotage distant
  SteamSwitch n'est encore expose dans l'ecran `Execution` ;
- la zone `Execution` reste donc un write path de test et non encore l'IHM
  operateur finale du process SteamSwitch/SBC.

## 9. Etat de depart retenu au 1 avril 2026

Etat observe et retenu comme reference de depart :

- le dashboard E2E et l'API de probe existent ;
- un step `edge-agent-nats-roundtrip` existe dans le backend ;
- le probe control-plane sait lire `healthz`, `varz` et `connz` ;
- les services edge-agent sont nommes cote NATS ;
- les anciens defaults pointaient encore vers une adresse `Tailscale`
  invalide ;
- l'IPC joignait bien `10.30.0.1:4222` via `WireGuard` ;
- le control plane ne joignait pas encore ce meme endpoint ;
- le besoin d'un proxy broker HTTPS borne et securise est devenu explicite.

Decision produit associee :

- le default edge-agent doit passer a `tls://10.30.0.1:4222` ;
- le test E2E control-plane ne doit plus supposer que cette meme URL est
  joignable depuis la VM control-panel ;
- le champ `edge_agent_probe_nats_url` devient le point d'entree explicite
  pour activer le test E2E depuis le dashboard.

## 9bis. Validation reelle du 1 avril 2026

Le correctif de separation des CAs et le workflow complet ont ete valides sur un
run `real` du workflow `IPC complet via WireGuard` pour l'asset
`cascadya-ipc-10-109`.

Resultat constate :

- `ready_for_real_execution=true` ;
- `13/13` etapes validees ;
- fin du run a `2026-04-01T15:18:05.827352+00:00` ;
- enchainement complet valide de `remote-unlock-generate-certs.yml` a
  `edge-agent-nats-roundtrip.yml` ;
- dernier step reussi via `broker_proxy`, sans reprise manuelle intermediaire.

Cause racine corrigee :

- le proxy broker et l'edge-agent ne devaient pas verifier le serveur NATS avec
  la CA issue du role Vault `devices-role` ;
- le certificat serveur NATS etait signe par une autre CA, distincte de celle
  utilisee pour les certificats clients edge-agent ;
- le produit distingue maintenant explicitement :
  - la CA HTTPS du proxy broker ;
  - la CA TLS du serveur NATS.

Implementation retenue :

- la VM `control-panel` fournit la CA serveur NATS via
  `AUTH_PROTO_PROVISIONING_NATS_SERVER_CA_CERT_PATH` ;
- le role broker recopie cette CA via
  `remote_unlock_broker_control_plane_probe_ca_cert_src` pour le probe local ;
- `edge-agent-generate-certs.yml` recopie cette meme CA dans le bundle
  edge-agent comme `nats-ca.crt` ;
- le probe control-plane via `https://51.15.64.139:9443` continue, lui, a se
  verifier avec la CA HTTPS du broker.

Indices de validation observes :

- `remote-unlock-preflight.yml` confirme le chemin `WireGuard-only` avec
  `Broker URL: https://10.30.0.1:8443` et la route
  `10.30.0.1 dev wg0 src 10.30.10.109` ;
- `remote-unlock-validate.yml` confirme `WireGuard status: active` et un
  dry-run remote unlock reussi ;
- `edge-agent-generate-certs.yml` publie un bundle contenant `nats-ca.crt` ;
- `edge-agent-validate.yml` confirme `gateway_modbus.service` et
  `telemetry_publisher.service` en `active/enabled` ;
- les journaux edge-agent montrent `Connecting NATS TLS (tls://10.30.0.1:4222)`
  puis un service `running` ;
- `edge-agent-nats-roundtrip.yml` retourne :
  - `Probe mode: broker_proxy`
  - `Broker proxy URL: https://51.15.64.139:9443`
  - `NATS URL: tls://host.docker.internal:4222`
  - `Monitoring URL: http://host.docker.internal:8222`
  - `Round-trip total: 65.277 ms`
  - `Control Panel -> Broker RTT: 7.367 ms`
  - `Broker -> IPC gateway RTT: 52.769 ms`
  - `Broker -> IPC telemetry RTT: 75.437 ms`
  - `Reply payload status: ok`
  - `Monitoring warnings: []`

Conclusion produit :

- le flux `IPC complet via WireGuard` est valide en conditions reelles ;
- le lot 5 n'est plus seulement une cible d'architecture, mais un chemin
  produit verifie de bout en bout ;
- la suite logique ne concerne plus la connectivite NATS elle-meme, mais la
  reprise idempotente et resume-safe des jobs de provisioning.

## 9ter. Extensions UI et exploitation du 2 avril 2026

Apres la validation reelle du 1 avril 2026, le lot 5 a ete etendu sur
l'interface operateur :

- ajout du select `Flux` dans `Test E2E` ;
- ajout du flux singleton `ems-light` ;
- remplacement de la waterfall trompeuse par une cascade a composantes
  explicites ;
- alignement de `ems-light` sur la meme logique de decomposition que
  `ems-site`, avec separation entre acces broker, traitement broker et lien
  downstream ;
- separation visuelle entre :
  - composantes actives du test ;
  - snapshots de canaux NATS `/connz` ;
- ajout d'un `mode manuel` et d'un `mode auto` sur la page E2E ;
- ajout d'une serie de mesures batch parametree par nombre d'echantillons et
  cadence inter-mesures ;
- ajout d'un graphe de tendance a points pour suivre l'evolution du RTT dans le
  temps ;
- ajout d'un bouton `Reset graph` ;
- renommage de la notion `Broker proxy` en `Traitement broker` dans les libelles
  operateur ;
- ajout d'un ecran `Orders` dans la topbar ;
- ajout d'un panneau `Execution` web pour les commandes et le watchdog ;
- ajout d'un log FIFO d'execution cote UI avec acquittements `request/reply`.

Comportements de mesure retenus :

- le mode `manuel` trace un point par mesure individuelle ;
- le mode `auto` trace un point par cycle periodique ;
- les statistiques batch calculent `min`, `avg`, `median`, `p95`, `max` et
  `std dev` sur la serie ;
- le `RTT actif (avec traitement broker)` et le `RTT actif (sans traitement
  broker)` sont exposes pour aider les futures decoupes du hot flow.

## 10. Milestones recommandes

### 10.1 Milestone 5A - Nettoyage des defaults reseau

Objectif :

- supprimer la dependance implicite a `Tailscale` dans les defaults edge-agent.

Livrables :

- `edge_agent_nats_url` par defaut sur `tls://10.30.0.1:4222` ;
- docs et exemples mis a jour ;
- onboarding UI aligne sur le mode `WireGuard-only`.

### 10.2 Milestone 5B - Probe E2E control-plane

Objectif :

- rendre le test E2E visible et actionnable depuis l'UI.

Livrables :

- page `sites/:siteId/e2e` ;
- endpoint `POST /api/e2e/tests` ;
- moteur de probe NATS partage entre UI et Ansible ;
- affichage des mesures `connz`.

### 10.3 Milestone 5C - Separation des chemins reseau

Objectif :

- distinguer clairement la connectivite IPC et la connectivite control-plane.

Livrables :

- `edge_agent_probe_nats_url`
- `edge_agent_probe_monitoring_url`
- workflow `edge-agent-nats-roundtrip` qui se skippe proprement si aucun
  chemin control-plane n'est configure.

### 10.4 Milestone 5D - Route control-plane vers le broker

Objectif :

- fournir un chemin `Control Panel -> Broker` compatible avec la politique
  `Tailscale-free`.

Livrables minimaux :

- un listener HTTPS dedie au probe sur le broker ;
- un bearer token distinct pour le control plane ;
- un client NATS local au broker pour lancer le `request/reply` ;
- la lecture locale de `healthz`, `varz` et `connz` par le broker ;
- l'integration du proxy broker dans l'API E2E et dans le workflow
  `edge-agent-nats-roundtrip`.

Options d'evolution ulterieure :

- ajout du control plane au reseau `WireGuard` operateur ;
- tunnel applicatif dedie ;
- durcissement du proxy broker (allowlist IP, cert dedie, rotation du token).

Cette milestone ne doit pas rouvrir une dependance `Tailscale`.

## 11. Validation attendue

Le lot 5 sera considere valide si :

- un IPC provisionne parle bien au broker NATS via `WireGuard` ;
- `gateway_modbus` et `telemetry_publisher` apparaissent dans `connz` ;
- l'UI E2E peut lancer un test pour un IPC cible ;
- le backend retourne un resultat ou un message d'erreur explicite ;
- les defaults edge-agent ne pointent plus vers des IP `Tailscale` obsoletes ;
- le workflow de provisioning affiche la verification NATS sans casser le lot 4 ;
- le broker peut exposer un probe HTTPS dedie sans exposition publique brute de
  `4222` ni `8222` ;
- le dashboard E2E peut utiliser ce proxy broker quand le control plane ne
  joint pas directement NATS ;
- le dashboard E2E permet de basculer entre `ems-site` et `ems-light` ;
- les RTT `/connz` ne sont plus presentes comme une pseudo-somme du total ;
- la page E2E expose clairement `RTT actif avec traitement broker` et `RTT actif
  sans traitement broker` ;
- la page E2E permet un mode `manuel` batch et un mode `auto` periodique avec
  graphe de tendance ;
- l'ecran `Orders` expose un FIFO operateur avec refresh reglable ;
- le panneau `Execution` permet au minimum le watchdog ping et l'envoi de
  commandes placeholder ;
- le produit ne masque plus les limites reseau par des fallbacks implicites.

Validation reelle initiale acquise le 1 avril 2026 :

- workflow `IPC complet via WireGuard` execute en mode `real` ;
- asset cible : `cascadya-ipc-10-109` ;
- `13/13` steps valides, dont `edge-agent-nats-roundtrip.yml`.

### Validation complementaire du 13 avril 2026

Le lot 5 a ete revalide le `13 avril 2026` sur le meme asset
`cascadya-ipc-10-109`, mais cette fois dans la version etendue du workflow a
`18` steps incluant `wazuh-agent` et `ipc-alloy`.

Resultat constate :

- le chemin final `edge-agent-nats-roundtrip.yml` repasse en `broker_proxy`
  apres une reprise manuelle controlee depuis `control-panel-DEV1-S` ;
- le proxy HTTPS du broker reste `https://51.15.64.139:9443` ;
- le serveur NATS vu par le probe reste `tls://host.docker.internal:4222` ;
- la supervision NATS vue par le probe reste
  `http://host.docker.internal:8222` ;
- le `reply payload` remonte `status=ok` pour
  `cascadya-ipc-10-109`.

Mesures observees sur le dernier run valide :

- `Temps total observe: 384.444 ms`
- `Composant proxy: 336.305 ms`
- `Composant request/reply actif: 48.139 ms`
- `Canal probe /connz: 6.986 ms`
- `Canal gateway_modbus /connz: 91.367 ms`
- `Canal telemetry_publisher /connz: 47.679 ms`

Preconditions produit reobservees pendant ce rerun :

- `cascadya-network-persist.service` est `active (exited)` sur l'IPC ;
- les routes `10.42.1.7/32` et `10.42.1.4/32` sont presentes sur l'IPC ;
- `alloy.service` est `active (running)` et pousse vers
  `http://10.42.1.4:9009/api/v1/push` ;
- `gateway_modbus.service` et `telemetry_publisher.service` sont
  `active/enabled` ;
- les logs `telemetry_publisher` montrent une emission continue avant le probe
  final.

Addendum produit retenu :

- la reprise manuelle du step final ne doit pas dependre d'un secret
  ephemere de job ;
- `edge-agent-nats-roundtrip.yml` sait maintenant relire le bearer token proxy
  depuis `AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_TOKEN` quand
  l'operateur relance le step directement depuis la VM `control-panel`.

Validation auto complementaire du `13 avril 2026` :

- un rerun ulterieur du meme jour termine aussi le workflow `real/auto` en
  `18/18`, jusqu'au message `DONE provisioning finished (real)` a
  `2026-04-13T14:48:14.106394+00:00` ;
- le dernier step `edge-agent-nats-roundtrip.yml` reste en `broker_proxy`
  sans reprise manuelle intermediaire ;
- le `reply payload` remonte toujours `status=ok` pour
  `cascadya-ipc-10-109` ;
- les mesures du dernier probe auto valide sont :
  - `Temps total observe: 235.373 ms`
  - `Composant proxy: 176.18 ms`
  - `Composant request/reply actif: 59.193 ms`
  - `Canal probe /connz: 7.447 ms`
  - `Canal gateway_modbus /connz: 244.932 ms`
  - `Canal telemetry_publisher /connz: 46.262 ms`.

## 12. Hors perimetre volontaire du lot 5

Le lot 5 ne couvre pas encore :

- une historisation longue duree des mesures E2E ;
- des graphes multi-sites ou des percentiles ;
- un moteur complet d'alerting ;
- une exposition publique brute de `8222` sans garde-fous ;
- une couche complete SLO/SLA produit ;
- la mesure canonique du hot flow telemetrie a partir des seuls RTT `/connz` ;
- la traduction finale JSON <-> Modbus cote IPC pour les commandes PLC ;
- la correlation complete Orders -> ACK PLC metier.

## 13. Definition of Done retenue

Le lot 5 pourra etre considere comme atteint quand :

- la topologie `WireGuard-only` est la reference pour l'IPC ;
- les anciens defaults `Tailscale` ont disparu du produit et des docs actives ;
- le dashboard sait lancer un vrai probe NATS ;
- le broker monitoring est exploitable depuis le produit quand un chemin reseau
  existe ;
- un chemin `control plane -> broker` borne et securise existe sans retour a
  `Tailscale` ;
- le produit sait distinguer les flux `ems-site` et `ems-light` dans la meme
  UX E2E ;
- la decomposition `acces broker` / `traitement broker` / lien downstream est
  lisible par un operateur non expert ;
- les ecrans `Orders` et `Execution` fournissent un premier outillage operateur
  sur le broker sans shell ad hoc ;
- l'absence de chemin control-plane n'est plus un bug silencieux mais une
  limitation visible et explicite ;
- la suite logique vers l'observabilite historique et l'audit trail peut etre
  engagee sur une base produit propre.

Etat initial au 1 avril 2026 :

- cette definition of done est atteinte sur un run `real` complet `13/13`.

Etat complementaire au 13 avril 2026 :

- la meme definition of done reste validee sur le workflow etendu a `18` steps,
  d'abord avec reprise manuelle canonique depuis `control-panel-DEV1-S`,
  puis sur un rerun `real/auto` complet le meme jour jusqu'au probe NATS final.

## 14. Suite logique apres le lot 5

Les tests reels du 1 avril 2026 ont montre qu'un sujet adjacent doit desormais
etre traite explicitement :

- la reprise deterministe apres echec partiel de provisioning ;
- la difference entre un playbook idempotent pris seul et un workflow
  resume-safe de bout en bout ;
- la conservation des secrets et artefacts necessaires a une reprise manuelle
  depuis la VM `control-panel` ;
- les gates reseau et SSH entre les steps `remote-unlock` et `edge-agent`.

Ces points sont formalises dans le document :

- `PRD_LOT_6_REPRISE_IDEMPOTENCE_PROVISIONING.md`
