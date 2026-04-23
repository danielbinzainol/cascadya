# PRD
# Cible De Provisioning IPC Alloy Vers Mimir Multi-Tenant
# Version: 1.1
# Date: 14 avril 2026
# Statut: cible stabilisee cote Monitoring, contrat IPC a implementer

## 1. Contexte

La VM `monitoring-DEV1-S` devient la cible metriques unique pour la chaine IPC de nouvelle generation.

Le modele retenu n'est plus seulement :

- Alloy IPC -> Mimir mono-tenant

mais :

- Alloy IPC -> Mimir multi-tenant
- avec 3 profils de conservation :
  - `classic`
  - `lts-1y`
  - `lts-5y`

L'objectif de ce document est de figer le contrat que le provisioning IPC devra respecter, a partir de la nouvelle cible implementee cote VM Monitoring.

## 2. Cible cote VM Monitoring

La VM Monitoring heberge :

- `Grafana`
- `Loki`
- `Mimir`
- `Alloy`
- `Promtail`
- `cAdvisor`

Le role monitoring est maintenant prepare pour :

- activer le multi-tenant Mimir ;
- definir des retentions par tenant ;
- charger des rule files de type rollups / recording rules via le ruler Mimir ;
- exposer plusieurs datasources Grafana Mimir, dont `classic` comme datasource compatible dashboards existants.

## 3. Cible Mimir

### 3.1 Endpoint d'ingestion

Endpoint cible pour tous les IPC :

- `http://10.42.1.4:9009/api/v1/push`

Endpoint readiness :

- `http://10.42.1.4:9009/ready`

Endpoint de lecture Prometheus-compatible pour Grafana :

- `http://10.42.1.4:9009/prometheus`

### 3.2 Multi-tenant

Le modele cible est :

- `classic`
- `lts-1y`
- `lts-5y`

Le tenant est porte par le header HTTP :

- `X-Scope-OrgID`

### 3.3 Retention cible

Retentions cibles :

- `classic` -> `30d`
- `lts-1y` -> `365d`
- `lts-5y` -> `1825d`

### 3.4 Ruler / rollups

Le modele cible de "downsampling" est en realite un modele de :

- recording rules / rollups Mimir ruler

Le principe attendu est :

- series 5 min
- puis series 1 h

Ces series ne remplacent pas le stockage natif bloc par bloc ; elles le completent.

## 4. Modele Grafana attendu

Grafana doit continuer a fonctionner sans casser les dashboards existants.

### 4.1 Datasource par defaut

La datasource Prometheus-compatible historique conserve :

- son UID existant
- son nom historique `prometheus`

Mais elle pointe vers Mimir et doit representer le tenant :

- `classic`

### 4.2 Datasources additionnelles

Grafana peut exposer des datasources supplementaires :

- `mimir-lts-1y`
- `mimir-lts-5y`

Ces datasources utilisent le meme endpoint Mimir mais avec un header tenant different.

## 5. Cible Alloy cote IPC

Le provisioning IPC doit deployer Alloy de facon a :

- scrapper `node_exporter` local ;
- pousser vers Mimir ;
- envoyer un tenant explicite ;
- conserver des labels compatibles dashboards.

## 6. Contrat technique IPC Alloy

### 6.1 Services locaux attendus

Source de scrape principale :

- `node_exporter`

Service attendu :

- `prometheus-node-exporter`

Port local attendu :

- `127.0.0.1:9100`

Service Alloy attendu :

- `alloy`

Fichier de config attendu :

- `/etc/alloy/config.alloy`

### 6.2 Cadence

Cadence cible :

- `scrape_interval = 15s`
- `scrape_timeout = 10s`

### 6.3 Remote write

URL cible :

- `http://10.42.1.4:9009/api/v1/push`

Header requis :

- `X-Scope-OrgID: <tenant>`

## 7. Contrat labels IPC

Le provisioning IPC doit conserver au minimum :

- `job="node-exporter"`
- `instance="<ipc>:9100"`

Labels additionnels recommandes :

- `source="ipc"`
- `node="<inventory_hostname>"`
- `role="ipc"`
- `site="<site>"`
- `retention_profile="<profile>"`
- `tenant="<tenant_label>"`

## 8. Mapping tenant / retention_profile

Le mapping recommande est :

- `classic` -> tenant `classic`, retention_profile `classic`
- `lts-1y` -> tenant `lts-1y`, retention_profile `lts-1y`
- `lts-5y` -> tenant `lts-5y`, retention_profile `lts-5y`

Le provisioning IPC ne doit pas dissocier ces valeurs sans raison fonctionnelle forte.

## 9. Exemple de logique de decision cote IPC

Chaque IPC doit etre provisionne avec un profil cible explicite.

Exemples :

- IPC standard :
  - tenant `classic`
  - retention_profile `classic`

- IPC a besoin de retention longue 1 an :
  - tenant `lts-1y`
  - retention_profile `lts-1y`

- IPC a besoin de retention tres longue 5 ans :
  - tenant `lts-5y`
  - retention_profile `lts-5y`

## 10. Variables a exposer dans le provisioning IPC

Variables minimales a rendre configurables :

- `ipc_alloy_mimir_remote_write_url`
- `ipc_alloy_scrape_interval`
- `ipc_alloy_scrape_timeout`
- `ipc_alloy_mimir_tenant`
- `ipc_alloy_retention_profile`
- `ipc_alloy_mimir_basic_auth_username`
- `ipc_alloy_mimir_basic_auth_password`
- `ipc_alloy_mimir_verify_tls`
- `ipc_alloy_mimir_ca_source_path`
- `ipc_alloy_labels_site`
- `ipc_alloy_labels_node`

Valeurs cibles par defaut :

- `ipc_alloy_mimir_remote_write_url = http://10.42.1.4:9009/api/v1/push`
- `ipc_alloy_scrape_interval = 15s`
- `ipc_alloy_scrape_timeout = 10s`
- `ipc_alloy_mimir_tenant = classic`
- `ipc_alloy_retention_profile = classic`

## 11. Hypotheses reseau

Le lot IPC provisioning doit considerer que :

- la cible Mimir est joignable via WireGuard ;
- les IPC doivent pouvoir atteindre `10.42.1.4:9009` ;
- le reseau prive cible reste `10.42.0.0/16` ;
- le reseau WireGuard reste `10.8.0.0/24`.

Le provisioning IPC ne doit pas supposer un acces public direct a Mimir.

## 12. Rollups LTS : interpretation correcte

Le terme "downsampling" doit etre interprete ici comme :

- des recording rules Mimir ruler qui produisent des series agregees

et non comme :

- un mecanisme natif automatique de compaction multi-resolution expose directement aux IPC.

Consequence :

- Alloy IPC n'a rien de special a faire pour les rollups lui-meme
- Alloy IPC doit seulement :
  - pousser les bonnes series ;
  - dans le bon tenant ;
  - avec les bons labels

Le reste est un sujet Monitoring/Mimir.

## 13. Contrat fonctionnel entre IPC et Monitoring

Ce que l'IPC doit garantir :

- la serie brute existe dans le bon tenant
- les labels sont coherents
- le scrape est stable
- le remote write ne tombe pas en erreur

Ce que la VM Monitoring doit garantir :

- Mimir accepte les series du tenant cible
- la retention du tenant est correcte
- les rule files du tenant sont charges
- Grafana peut lire le tenant cible

## 14. Criteres d'acceptation

Le provisioning IPC est considere conforme si :

- Alloy tourne au boot
- `node_exporter` est scrape localement
- `remote_write` va vers `10.42.1.4:9009`
- `X-Scope-OrgID` est envoye quand le multi-tenant est actif
- les labels `job` et `instance` restent compatibles avec les dashboards
- les series apparaissent dans le tenant cible
- les dashboards Grafana peuvent relire ces series via la datasource Mimir appropriee

## 15. Resume executif

La nouvelle cible n'est plus un simple envoi Alloy vers un backend unique sans contexte.

La cible est :

- un Mimir multi-tenant
- 3 politiques de retention :
  - `classic`
  - `lts-1y`
  - `lts-5y`
- des rollups geres cote Monitoring par Mimir ruler
- un provisioning IPC qui choisit explicitement un tenant/profil, pousse vers `10.42.1.4:9009`, et conserve un schema de labels stable.

En pratique, l'IPC ne doit pas "gerer Mimir".

Il doit simplement respecter ce contrat :

- `remote_write` vers `http://10.42.1.4:9009/api/v1/push`
- `X-Scope-OrgID = <tenant>`
- `job="node-exporter"`
- `instance="<ipc>:9100"`
- `retention_profile` et `tenant` coherents

## 16. Etat d'avancement valide au 14 avril 2026

Ce qui est maintenant valide runtime cote Monitoring :

- la VM `monitoring-DEV1-S` expose bien `Grafana`, `Mimir`, `Loki`, `Alloy`, `Promtail` et `cAdvisor`
- `Mimir` repond sur `10.42.1.4:9009`
- la datasource Grafana `prometheus` cible bien le tenant `classic`
- l'Alloy de la VM Monitoring scrape les `node_exporter` distants des VM du serveur via leurs IP privees `10.42.x.x`

VM actuellement scrappees par la VM Monitoring :

- `c-market-Dev1-S` -> `10.42.1.8`
- `wazuh-Dev1-S` -> `10.42.1.7`
- `control-panel-DEV1-S` -> `10.42.1.2`
- `broker-DEV1-S` -> `10.42.1.6`
- `wireguard-DEV1-S` -> `10.42.1.5`
- `docmost-DEV1-S` -> `10.42.1.3`
- `vault-DEV1-S` -> `10.42.2.4`

Contrat de labels actuellement valide pour les metriques VM collectees par la VM Monitoring :

- `job="node-exporter"`
- `instance="<vm>:9100"`
- `source="vm"`
- `node="<vm>"`
- `role="vm"`
- `site="ams1"`
- `retention_profile="classic"`
- `tenant="classic"`

Validation runtime effectuee :

- la requete `up{job="node-exporter",source="vm"}` sur Mimir tenant `classic` retourne `1` pour les 7 VM cibles
- `node_exporter` a ete installe et active sur les VM manquantes `c-market-Dev1-S`, `wazuh-Dev1-S` et `control-panel-DEV1-S`
- la reachability privee `10.42.x.x:9100` est maintenant validee depuis `monitoring-DEV1-S`

Implication :

- la partie VM Monitoring est desormais prete pour alimenter des dashboards Grafana de type "Infrastructure VM"
- le prochain sujet n'est plus la collecte, mais l'exploitation Grafana via dashboards et variables

## 17. Cible Grafana pour l'exploitation IPC et VM

Le modele recommande cote Grafana est d'avoir un dossier :

- `Mimir`

contenant au minimum :

- `IPC Mimir Dashboard`
- `VM Mimir Dashboard`

Mais en conservant :

- la meme datasource `prometheus` pour le tenant `classic`
- le meme style de selection utilisateur par listes deroulantes

### 17.1 Dashboard IPC

Les dashboards IPC doivent exposer au minimum :

- une variable `site`
- une variable `ipc`

Le filtre doit s'appuyer sur les labels :

- `source="ipc"`
- `site`
- `node`

Le label `node` doit etre prefere pour la liste deroulante plutot que de parser `instance`, car il est deja proprement produit par Alloy.

### 17.2 Dashboard VM

Les dashboards VM doivent exposer au minimum :

- une variable `vm`

Le filtre doit s'appuyer sur les labels :

- `source="vm"`
- `node`

Optionnellement, une variable `site` pourra etre ajoutee plus tard si plusieurs sites VM sont exposes, mais ce n'est pas necessaire pour le besoin actuel.

### 17.3 Principe de construction recommande

Pour eviter de casser les requetes :

- dupliquer un dashboard Prometheus deja base sur `node_exporter`
- remplacer les filtres "instance brute" par des filtres explicites sur `source`, `site`, `node`
- conserver `instance="<nom>:9100"` comme contrat de compatibilite dans les series

Si le dashboard "IPC" actuel est base sur PostgreSQL et non sur Prometheus / `node_exporter`, il ne faut pas l'utiliser comme base pour les metriques systeme.

Dans ce cas, la meilleure base est :

- le dashboard `docker_system.json` pour construire un dashboard VM ou IPC orienté `node_exporter`

## 18. Document de travail associe

Le guide operationnel pour la mise en place des dashboards Grafana et des listes deroulantes est fourni dans :

- `GRAFANA_VM_IPC_DASHBOARD_GUIDE.md`
