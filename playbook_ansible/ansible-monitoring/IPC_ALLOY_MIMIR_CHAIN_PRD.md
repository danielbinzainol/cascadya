# PRD
# Mise En Place De La Chaine IPC Alloy -> Mimir
# Version: 1.0
# Date: 13 avril 2026
# Statut: cible d'implementation Ansible

## 1. Contexte

La stack de monitoring centrale est maintenant deployee sur `monitoring-DEV1-S` et fonctionne autour de :

- `Grafana`
- `Loki`
- `Mimir`
- `Alloy`
- `Promtail`
- `cAdvisor`

Le prochain lot consiste a completer la chaine cote IPC pour que les metriques systeme et applicatives des IPC soient collectées par Alloy puis envoyees vers Mimir.

Le point de focalisation n'est pas Grafana, mais bien la facon dont `Mimir` est actuellement expose, configure, alimente et interroge, afin d'aligner correctement la configuration Alloy sur les IPC.

## 2. Etat actuel valide de la VM monitoring

Etat runtime valide :

- `grafana` expose `3000/TCP`
- `loki` expose `3100/TCP`
- `mimir` expose `9009/TCP`
- `alloy` expose son interface locale sur `127.0.0.1:12345`
- `promtail` tourne
- `cadvisor` tourne

Etat reseau valide :

- IP publique monitoring : `51.15.83.22`
- IP privee monitoring : `10.42.1.4`
- acces Grafana attendu via WireGuard sur `http://10.42.1.4:3000`
- acces Mimir interne attendu via `http://10.42.1.4:9009`
- acces Loki interne attendu via `http://10.42.1.4:3100`

Etat reseau important pour la chaine Alloy :

- le monitoring SG autorise `9009/TCP` depuis `10.8.0.0/24`
- la VM monitoring a besoin d'une route de retour vers `10.8.0.0/24` via `10.42.1.5`
- cette route est actuellement assuree runtime par le service systemd `wireguard-return-route.service`

Conclusion :

- la chaine IPC -> WireGuard -> Mimir est viable
- mais elle depend du modele routé entre `10.8.0.0/24` et `10.42.0.0/16`
- le playbook IPC Alloy doit donc assumer que la cible Mimir est joignable sur `10.42.1.4:9009` via WireGuard

## 3. Objectif produit

Mettre en place, sur chaque IPC, une brique Alloy capable de :

- collecter les metriques locales utiles ;
- pousser ces metriques vers Mimir ;
- conserver un schema de labels compatible avec les dashboards Grafana existants ou a venir ;
- fonctionner de facon stable apres reboot ;
- etre deployee de maniere declarative via Ansible.

## 4. Architecture cible

### Cote monitoring

`Mimir` joue le role de backend metriques unique.

Flux cibles :

- `IPC exporters -> IPC Alloy`
- `IPC Alloy -> Mimir`
- `Grafana -> Mimir`

### Cote IPC

Chaque IPC devra idealement executer :

- `node_exporter`
- `alloy`

Optionnellement :

- un ou plusieurs exporters applicatifs/metier ;
- un scraper additionnel si une application expose deja `/metrics`.

## 5. Structure actuelle de Mimir

La configuration actuelle de Mimir sur la VM monitoring est la suivante :

- mode monolithique
- `multitenancy_enabled: false`
- port HTTP : `9009`
- backend objet : `S3 Scaleway`
- stockage local :
  - `/data/tsdb`
  - `/data/compactor`
  - `/data/ruler`
  - `/data/tsdb-sync`

Config observee cote Ansible :

- template Mimir : `roles/monitoring/templates/mimir.yml.j2`
- endpoint remote write cible : `/api/v1/push`
- endpoint Grafana Prometheus-compatible : `/prometheus`
- endpoint readiness : `/ready`

Implication importante pour les IPC :

- pas de multitenancy a gerer ;
- pas de header `X-Scope-OrgID` requis ;
- pas d'authentification Mimir actuellement configuree pour l'ingestion ;
- Alloy cote IPC peut utiliser un remote write simple vers `http://10.42.1.4:9009/api/v1/push`.

## 6. Structure actuelle de l'Alloy sur la VM monitoring

L'Alloy de la VM monitoring sert de reference de conception.

Comportement actuel :

- remote write vers `http://mimir:9009/api/v1/push`
- collecte des metriques systeme locales via `prometheus.exporter.unix`
- relabel pour fixer :
  - `job = "node-exporter"`
  - `instance = "<nom-noeud>:9100"`
- scrape optionnel de `cadvisor`

Ce point est essentiel car il donne le modele de labels a reproduire sur les IPC.

## 7. Decision de modelisation des labels

Pour rester compatible avec les dashboards de type node-exporter / PromQL, le role Alloy des IPC doit conserver un schema simple et previsible.

Schema recommande pour les metriques systeme :

- `job = "node-exporter"`
- `instance = "<ipc-name>:9100"`

Labels additionnels recommandes :

- `source = "ipc"`
- `node = "<ipc-name>"`
- `site = "<site-id>"` si pertinent
- `role = "ipc"` si pertinent

Pourquoi :

- les dashboards existants utilisent deja des selectors de type `instance="$instance:9100"`
- garder ce pattern minimise la casse cote Grafana

## 8. Endpoint Mimir a cibler depuis les IPC

Endpoint recommande :

- `http://10.42.1.4:9009/api/v1/push`

Endpoint de verification :

- `http://10.42.1.4:9009/ready`

Endpoint de requete Grafana :

- `http://10.42.1.4:9009/prometheus`

Decision :

- ne pas faire pointer Alloy des IPC vers le nom Docker `mimir`
- utiliser l'IP privee monitoring `10.42.1.4`
- s'appuyer sur WireGuard comme plan d'acces

## 9. Hypotheses reseau cote IPC

Hypothese cible :

- l'IPC rejoint l'overlay WireGuard
- l'IPC recupere une IP `10.8.0.x`
- l'IPC route `10.42.0.0/16` dans le tunnel
- l'IPC pousse ses metriques vers `10.42.1.4:9009`

Contrainte importante :

- si l'IPC n'est pas encore sur WireGuard, il ne faut pas supposer que l'ingestion Mimir sera joignable
- le fallback public n'est pas actif par defaut ;
- il n'existe qu'une liste vide `allowed_mimir_public_ipc_cidrs` dans Terraform

Conclusion :

- le lot IPC Alloy doit etre pense comme un lot WireGuard-first

## 10. Ce que le playbook IPC Alloy doit faire

Le futur role Ansible IPC doit au minimum :

- installer Alloy
- deployer son fichier de configuration
- activer Alloy au boot
- pointer Alloy vers `10.42.1.4:9009/api/v1/push`
- scrapper `node_exporter`
- fixer les labels `job` et `instance`
- verifier la sante locale du service
- verifier que Mimir est joignable

Il peut aussi :

- verifier la presence de `node_exporter`
- l'installer si absent
- scrapper des exporters applicatifs supplementaires

## 11. Recommandation de mode de deploiement Alloy sur IPC

Recommandation principale :

- deployer Alloy en service systemd natif sur l'IPC

Pourquoi :

- moins de dependances que Docker sur un IPC
- footprint plus simple
- plus previsible sur une ligne de provisioning industrielle
- plus simple pour journald, restart policy et supervision

Alternative acceptable :

- Alloy en conteneur si l'IPC est deja normalise Docker-first

## 12. Fichiers recommandes pour le futur repo/role IPC

Structure cible recommandee :

- `inventory/hosts.ini`
- `inventory/group_vars/ipc.yml`
- `playbooks/ipc-alloy.yml`
- `roles/ipc_alloy/defaults/main.yml`
- `roles/ipc_alloy/tasks/main.yml`
- `roles/ipc_alloy/tasks/install.yml`
- `roles/ipc_alloy/tasks/configure.yml`
- `roles/ipc_alloy/tasks/verify.yml`
- `roles/ipc_alloy/handlers/main.yml`
- `roles/ipc_alloy/templates/config.alloy.j2`
- `roles/ipc_alloy/templates/alloy.service.j2` si service custom

## 13. Variables attendues cote IPC

Variables minimales :

- `ipc_name`
- `alloy_listen_port` si UI locale active
- `alloy_storage_path`
- `mimir_remote_write_url`
- `node_exporter_target`
- `alloy_scrape_interval`
- `alloy_scrape_timeout`

Variables recommandees :

- `ipc_site`
- `ipc_role`
- `ipc_enable_node_exporter_scrape`
- `ipc_enable_app_metrics_scrape`
- `ipc_app_metrics_targets`
- `ipc_alloy_enable_http_ui`

Valeurs cibles actuelles :

- `mimir_remote_write_url: "http://10.42.1.4:9009/api/v1/push"`
- `node_exporter_target: "127.0.0.1:9100"`

## 14. Exemple de logique Alloy attendue sur IPC

Comportement cible :

- un `prometheus.remote_write "mimir"`
- un bloc scrape pour `node_exporter`
- un `relabel` pour fixer `job="node-exporter"`
- un `relabel` pour fixer `instance="<ipc-name>:9100"`

Option applicative :

- un ou plusieurs blocs scrape additionnels vers des exporters locaux
- labels explicites par application

## 15. Exigences de compatibilite Grafana / dashboards

Pour eviter de casser l'exploitation :

- conserver le schema `instance="<nom>:9100"` pour les metriques node-exporter
- conserver `job="node-exporter"` pour les metriques systeme
- ne pas introduire de labels exotiques a la place des labels standards
- eviter les renommages de jobs si non necessaire

Point de vigilance :

- le dashboard `docker_system.json` actuel a ete pense pour des patterns `instance="$instance:9100"` et `instance="$instance:8080"`
- si l'IPC n'utilise pas `cadvisor`, seule la partie node-exporter sera naturellement reutilisable

## 16. Exigences Mimir cote ingestion

Le lot IPC Alloy doit considerer Mimir comme suit :

- backend Prometheus-compatible en ecriture via remote write
- pas de tenant requis
- pas d'auth sur l'ingestion aujourd'hui
- bucket S3 entierement gere cote monitoring/Terraform/Ansible

Le role IPC n'a pas a connaitre :

- les secrets S3
- la configuration bucket
- la config interne compactor/ruler/store-gateway

Le role IPC n'a besoin que de :

- l'URL d'ingestion
- la connectivite reseau

## 17. Multi-tenant, retention et LTS

### Etat actuel du repo monitoring

Au moment de cette PRD, le repo `ansible-monitoring` ne montre pas encore une mise en oeuvre complete de :

- `multitenancy_enabled: true`
- plusieurs tenants Mimir
- retention differenciee par tenant
- `runtime_config` / `overrides`
- limites par tenant
- chargement automatique de regles de recording/downsampling

Le constat actuel est donc :

- Mimir existe et ingere ;
- Alloy existe et pousse ;
- Grafana lit Mimir ;
- mais la politique `classic / lts-1y / lts-5y` n'est pas encore visible comme contrat implemente dans le playbook.

### Modele cible a clarifier avec l'equipe monitoring

Le contrat a figer cote Mimir doit repondre explicitement a ces questions :

1. Active-t-on le multi-tenant dans Mimir ?
2. Les profils `classic`, `lts-1y`, `lts-5y` sont-ils de vrais tenants distincts ?
3. Quelle retention exacte par tenant ?
4. Le terme `LTS` signifie-t-il uniquement retention longue, ou retention + downsampling ?
5. Grafana doit-il avoir une datasource Mimir unique ou une datasource par tenant ?
6. Alloy IPC doit-il envoyer `X-Scope-OrgID` ?

### Recommandation de modelisation

Le modele le plus clair pour l'IPC serait :

- tenant `classic`
- tenant `lts-1y`
- tenant `lts-5y`

avec :

- une URL d'ingestion commune
- un header `X-Scope-OrgID` par IPC selon la politique cible
- un label `retention_profile` conserve en plus pour l'observabilite produit

Dans ce modele :

- le tenant porte la politique technique effective ;
- le label porte le contexte metier et facilite la lecture dans Grafana.

## 18. Downsampling : ce que votre exemple implique

Le fichier de type :

```yaml
groups:
  - name: downsampling_5min
    interval: 5m
    rules:
      - record: cascadya:node_cpu_usage:avg5m
      - record: cascadya:node_memory_used_bytes:avg5m
      - record: cascadya:node_network_bytes:rate5m
  - name: downsampling_1h
    interval: 1h
    rules:
      - record: cascadya:node_cpu_usage:avg1h
      - record: cascadya:node_memory_used_bytes:avg1h
      - record: cascadya:node_network_bytes:rate1h
```

est coherent comme **strategie de recording rules**, mais cela ne veut pas dire que le repo actuel le fait deja.

Pour que cela fonctionne reellement cote monitoring, il faut au minimum :

- un chargement des rule groups dans Mimir ;
- une brique ruler effectivement exploitee ;
- un chemin ou backend de regles provisionne par Ansible ;
- une convention claire de labels, notamment `site` ;
- une decision produit sur l'usage de ces series :
  - lecture dashboard
  - retention longue
  - ou deux

### Point important

Ce que vous proposez n'est pas un "downsampling automatique" natif au sens stockage bloc compacté multi-resolution.

C'est plutot :

- des **recording rules** qui produisent des series agregees a 5 min puis 1 h

Cela peut tres bien servir de strategie LTS, mais il faut l'assumer comme tel dans la documentation.

### Ce qu'il manque aujourd'hui dans le playbook monitoring pour supporter cela

Je ne vois pas encore dans `ansible-monitoring` :

- de dossier `rules/` pour Mimir ;
- de volume Docker dedie a des rules Mimir ;
- de template Ansible qui deploie des regles de ruler ;
- de montage Docker dedie pour des fichiers de regles Mimir ;
- de config Mimir indiquant le chargement de namespaces/groups de regles ;
- de `runtime_config` de type tenant/limits/retention.

Conclusion :

- votre exemple aide beaucoup a cadrer la cible ;
- mais il ne prouve pas que la cible est deja implementee ;
- il faut l'utiliser comme base de question/spec pour l'equipe monitoring.

### Ajustements recommandes sur les expressions

Deux remarques importantes avant de proposer des rule files comme contrat officiel :

- CPU :
  - `avg by (site) (rate(node_cpu_seconds_total{mode!="idle"}[5m]))` ne donne pas proprement un pourcentage CPU site
  - il vaut mieux normaliser par la somme de tous les modes CPU
- RAM :
  - `avg by (site)` donne une moyenne par site
  - si le besoin est le total de RAM consommee par site, il faut plutot `sum by (site)`

## 19. Contrat recommande cote IPC Alloy si le multi-tenant arrive

Si l'equipe monitoring confirme un modele multi-tenant, le role Alloy IPC devrait idealement exposer :

- `ipc_alloy_mimir_remote_write_url`
- `ipc_alloy_mimir_tenant`
- `ipc_alloy_retention_profile`
- `ipc_alloy_scrape_interval`
- `ipc_alloy_scrape_timeout`

Comportement recommande :

- `ipc_alloy_mimir_tenant` alimente `X-Scope-OrgID`
- `ipc_alloy_retention_profile` reste un label envoye avec les series
- `job="node-exporter"` et `instance="<ipc>:9100"` restent stables

Exemple de mapping recommande :

- `classic` -> tenant `classic`
- `lts-1y` -> tenant `lts-1y`
- `lts-5y` -> tenant `lts-5y`

## 20. Exigences de verification

Le futur playbook IPC Alloy doit verifier :

- que l'IPC voit `10.42.1.4:9009`
- que `node_exporter` repond localement
- que le service Alloy tourne
- que la config Alloy est syntaxiquement valide si l'outil le permet
- qu'un test `up{instance="<ipc-name>:9100"}` devient visible dans Mimir/Grafana

Verification cote monitoring recommandee :

- `curl http://127.0.0.1:9009/ready`
- query Grafana/PromQL pour retrouver l'instance IPC

## 21. Risques et points d'attention

### Risque reseau

Le plus gros risque n'est pas Alloy lui-meme mais le chemin reseau :

- WireGuard non etabli
- route `10.42.0.0/16` absente cote IPC
- route de retour `10.8.0.0/24` absente cote monitoring

### Risque labels

Si l'IPC envoie des labels incompatibles avec les dashboards existants :

- les dashboards ne remontent rien
- l'instance n'est pas retrouvable via les variables Grafana

### Risque de faux positif

Le simple fait qu'Alloy tourne ne prouve pas que Mimir recoive les metriques.

Il faut valider la chaine complete.

### Risque produit sur le terme "downsampling"

Le mot "downsampling" peut recouvrir deux choses differentes :

- de vraies series derivees par recording rules ;
- ou une politique de retention/compaction attendue nativement du stockage

Il faut lever cette ambiguite avant de coder le contrat IPC.

## 22. Criteres d'acceptation

Le lot IPC Alloy est considere termine si :

- l'IPC rejoint correctement WireGuard
- l'IPC peut joindre `10.42.1.4:9009`
- Alloy tourne au boot sur l'IPC
- Alloy scrappe `node_exporter`
- Alloy remote-write vers Mimir sans erreur
- les metriques de l'IPC sont visibles dans Mimir
- Grafana peut interroger ces metriques via la datasource Mimir existante
- les labels `job` et `instance` restent compatibles avec les conventions actuelles

## 23. Ordre de developpement recommande

1. Figer les conventions de labels IPC.
2. Figer l'URL Mimir cible.
3. Construire le template Alloy de base pour `node_exporter`.
4. Ajouter les checks de connectivite reseau.
5. Ajouter les checks de sante du service Alloy.
6. Faire confirmer le contrat multi-tenant / retention / LTS.
7. Si retenu, integrer `X-Scope-OrgID` dans Alloy IPC.
8. Si retenu, definir les recording rules/downsampling cote monitoring.
9. Valider la visibilite des metriques dans Mimir.
10. Ajouter ensuite les exporters applicatifs supplementaires.

## 24. Message pret a coller dans le chat monitoring

```text
J'ai verifie le playbook ansible-monitoring actuel.

Constat repo :
- Mimir est deploye mais reste en mono-tenant (`multitenancy_enabled: false`)
- je ne vois pas de `runtime_config`, `overrides`, `limits`, ni de retention par tenant
- je ne vois pas non plus de chargement de regles de ruler/downsampling dans le repo actuel
- Alloy scrape en 15s et push vers Mimir via `/api/v1/push`
- Grafana interroge Mimir via `/prometheus`

J'ai en revanche une proposition de downsampling sous forme de recording rules, par exemple :
- series `avg5m`
- puis series `avg1h`

Avant de finaliser Alloy cote IPC, j'ai besoin du contrat cible Mimir :
1. Active-t-on vraiment le multi-tenant ?
2. Veut-on 3 tenants distincts : `classic`, `lts-1y`, `lts-5y` ?
3. Quelle retention exacte par tenant ?
4. "LTS" = retention seule ou retention + recording rules/downsampling ?
5. Si downsampling, est-ce bien Mimir ruler qui doit porter ces recording rules ?
6. Alloy IPC doit-il envoyer `X-Scope-OrgID` ?
7. On garde une datasource Grafana Mimir unique ou une par tenant ?
8. Confirme-t-on bien l'endpoint IPC -> Mimir : `http://10.42.1.4:9009/api/v1/push` via WireGuard ?
9. Confirme-t-on la convention labels IPC pour compatibilite dashboard :
   - `job="node-exporter"`
   - `instance="<ipc>:9100"`
   - `site=<site>`

Par defaut, cote IPC, je pars sinon sur :
- scrape local `node_exporter`
- intervalle `15s`
- remote_write vers Mimir
- labels stables `job` / `instance`
- tenant optionnel seulement si Mimir passe en multi-tenant
```

## 25. Resume executif

La VM monitoring est deja correctement structuree pour recevoir des metriques Alloy via Mimir.

Les points structurants a retenir pour le lot IPC sont :

- la vraie cible metriques est `Mimir`, pas Grafana ;
- l'endpoint a viser est `http://10.42.1.4:9009/api/v1/push` ;
- Mimir est en monolithique, sans multitenancy active ;
- le schema de labels doit rester compatible avec `job="node-exporter"` et `instance="<ipc-name>:9100"` ;
- la viabilite de la chaine depend autant du reseau WireGuard et de la route de retour que de la config Alloy elle-meme.

Autrement dit :

- la couche de collecte IPC doit etre simple ;
- la couche Mimir existe deja ;
- le vrai enjeu est d'aligner Alloy IPC sur les conventions de labels et sur le chemin reseau deja valide vers `10.42.1.4:9009`.
