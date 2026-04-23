# Guide
# Grafana Pour Les Dashboards IPC Et VM
# Date: 14 avril 2026

## 1. Objectif

Ce document decrit la facon recommandee de construire les dashboards Grafana pour :

- les IPC
- les VM du serveur

Le modele retenu dans Grafana est :

- un dossier `Mimir`
- contenant `IPC Mimir Dashboard`
- et `VM Mimir Dashboard`

La collecte est deja en place :

- les IPC doivent envoyer vers Mimir tenant `classic`
- la VM Monitoring scrappe deja les `node_exporter` des VM du serveur

Le sujet ici est uniquement :

- afficher correctement ces metriques dans Grafana
- avec des listes deroulantes propres et stables

## 2. Datasource a utiliser

Pour l'etat actuel, utiliser la datasource Grafana :

- `prometheus`

Elle pointe vers Mimir sur le tenant :

- `classic`

Les datasources `mimir-lts-1y` et `mimir-lts-5y` existent pour la suite, mais ne sont pas necessaires pour les premiers dashboards IPC et VM.

## 3. Labels disponibles

### 3.1 Labels IPC attendus

Les metriques IPC doivent exposer :

- `job="node-exporter"`
- `instance="<ipc>:9100"`
- `source="ipc"`
- `node="<ipc>"`
- `role="ipc"`
- `site="<site>"`
- `retention_profile="<profile>"`
- `tenant="<tenant_label>"`

### 3.2 Labels VM actuellement valides

Les metriques VM collectees par la VM Monitoring exposent :

- `job="node-exporter"`
- `instance="<vm>:9100"`
- `source="vm"`
- `node="<vm>"`
- `role="vm"`
- `site="ams1"`
- `retention_profile="classic"`
- `tenant="classic"`

## 4. Regle de modelisation

Pour les listes deroulantes, utiliser de preference :

- `node`

et non :

- `instance`

Pourquoi :

- `node` est deja propre et lisible
- `instance` contient le suffixe `:9100`
- cela evite d'ajouter des regex de parsing inutilement fragiles

`instance` doit rester dans les series pour la compatibilite PromQL et dashboards existants, mais il ne doit pas etre la variable utilisateur privilegiee.

## 5. Dashboard IPC

## 5.1 Variables a creer

Variables recommandees :

- `site`
- `ipc`

### Variable `site`

Type :

- `Query`

Datasource :

- `prometheus`

Query :

```promql
label_values(up{job="node-exporter",source="ipc"}, site)
```

Options recommandees :

- `Multi-value`: active
- `Include All option`: active
- valeur `All`: `.*`

### Variable `ipc`

Type :

- `Query`

Datasource :

- `prometheus`

Query :

```promql
label_values(up{job="node-exporter",source="ipc",site=~"$site"}, node)
```

Options recommandees :

- `Multi-value`: active
- `Include All option`: active
- valeur `All`: `.*`

## 5.2 Filtre standard a reutiliser dans les panels IPC

Dans les requetes PromQL du dashboard IPC, utiliser le filtre de base :

```promql
{job="node-exporter",source="ipc",site=~"$site",node=~"$ipc"}
```

## 5.3 Exemples de requetes IPC

### Uptime

```promql
time() - node_boot_time_seconds{job="node-exporter",source="ipc",site=~"$site",node=~"$ipc"}
```

### CPU utilise

```promql
100 * (1 - avg by (node) (
  rate(node_cpu_seconds_total{job="node-exporter",source="ipc",site=~"$site",node=~"$ipc",mode="idle"}[$__rate_interval])
))
```

### Memoire utilisee

```promql
100 * (
  1 -
  (
    node_memory_MemAvailable_bytes{job="node-exporter",source="ipc",site=~"$site",node=~"$ipc"}
    /
    node_memory_MemTotal_bytes{job="node-exporter",source="ipc",site=~"$site",node=~"$ipc"}
  )
)
```

### Load 1 minute

```promql
node_load1{job="node-exporter",source="ipc",site=~"$site",node=~"$ipc"}
```

### Reseau recu par interface

```promql
sum by (node, device) (
  rate(node_network_receive_bytes_total{job="node-exporter",source="ipc",site=~"$site",node=~"$ipc",device!~"lo|docker.*|veth.*"}[$__rate_interval])
)
```

### Reseau emis par interface

```promql
sum by (node, device) (
  rate(node_network_transmit_bytes_total{job="node-exporter",source="ipc",site=~"$site",node=~"$ipc",device!~"lo|docker.*|veth.*"}[$__rate_interval])
)
```

## 6. Dashboard VM

## 6.1 Base recommandee

Si tu veux un dashboard VM rapide a mettre en place :

- duplique `docker_system.json`

Pourquoi :

- il est deja base sur Prometheus
- il contient deja des panels `node_exporter`
- il a deja une logique de variable de type "instance"

Important :

- les panels `cAdvisor` / containers ne sont pas adaptes aux VM distantes si celles-ci n'exposent pas `cAdvisor`
- pour un dashboard VM propre, il faut supprimer ou neutraliser ces panels

## 6.2 Variable a creer

Variable recommandee :

- `vm`

Type :

- `Query`

Datasource :

- `prometheus`

Query :

```promql
label_values(up{job="node-exporter",source="vm"}, node)
```

Options recommandees :

- `Multi-value`: active
- `Include All option`: active
- valeur `All`: `.*`

## 6.3 Filtre standard a reutiliser dans les panels VM

Dans les requetes PromQL du dashboard VM, utiliser le filtre de base :

```promql
{job="node-exporter",source="vm",node=~"$vm"}
```

## 6.4 Exemples de requetes VM

### Uptime

```promql
time() - node_boot_time_seconds{job="node-exporter",source="vm",node=~"$vm"}
```

### CPU utilise

```promql
100 * (1 - avg by (node) (
  rate(node_cpu_seconds_total{job="node-exporter",source="vm",node=~"$vm",mode="idle"}[$__rate_interval])
))
```

### Memoire utilisee

```promql
100 * (
  1 -
  (
    node_memory_MemAvailable_bytes{job="node-exporter",source="vm",node=~"$vm"}
    /
    node_memory_MemTotal_bytes{job="node-exporter",source="vm",node=~"$vm"}
  )
)
```

### Systeme de fichiers racine

```promql
100 * (
  1 -
  (
    node_filesystem_avail_bytes{job="node-exporter",source="vm",node=~"$vm",mountpoint="/",fstype!~"tmpfs|overlay"}
    /
    node_filesystem_size_bytes{job="node-exporter",source="vm",node=~"$vm",mountpoint="/",fstype!~"tmpfs|overlay"}
  )
)
```

### Load 1 minute

```promql
node_load1{job="node-exporter",source="vm",node=~"$vm"}
```

## 7. Procedure UI Grafana recommandee

### Pour le dashboard IPC

1. Ouvrir le dashboard de base oriente `node_exporter`.
2. Faire `Save as...` pour creer une copie.
3. Aller dans `Dashboard settings` -> `Variables`.
4. Ajouter la variable `site`.
5. Ajouter la variable `ipc`.
6. Remplacer les filtres statiques des panels par :

```promql
job="node-exporter",source="ipc",site=~"$site",node=~"$ipc"
```

### Pour le dashboard VM

1. Dupliquer `docker_system.json` depuis Grafana ou exporter puis reimporter.
2. Renommer le dashboard en quelque chose comme `Infrastructure VM`.
3. Remplacer la variable `instance` par `vm`.
4. Changer les filtres des requetes pour utiliser :

```promql
job="node-exporter",source="vm",node=~"$vm"
```

5. Supprimer les panels qui interrogent `cAdvisor` ou les containers si les VM ne les exposent pas.

## 8. Cas particulier du dashboard IPC actuel

Si le dashboard IPC que tu appelles "celui d'IPC" est en realite base sur :

- PostgreSQL

alors ce n'est pas la bonne base pour des metriques `node_exporter`.

Dans ce cas :

- garde ce dashboard pour la telemetrie metier
- duplique plutot un dashboard Prometheus / `node_exporter`

Dans ce repo, la meilleure base existante est :

- `roles/monitoring/files/docker_system.json`

## 9. Mise sous version dans Ansible

Si tu veux figer les dashboards dans le repo apres validation UI :

1. Exporter le JSON depuis Grafana.
2. Le placer dans `roles/monitoring/files/`.
3. Ajouter une tache `copy` dans `roles/monitoring/tasks/deploy_stack.yml`.
4. Le ranger dans le dossier Grafana approprie sous `/opt/monitoring/grafana/dashboards/...`.

Fichiers utiles dans ce repo :

- `roles/monitoring/templates/dashboards.yml.j2`
- `roles/monitoring/tasks/deploy_stack.yml`

## 10. Recommandation finale

Le chemin le plus simple et le plus robuste est :

- pour IPC : variables `site` puis `ipc`
- pour VM : variable `vm`
- toujours filtrer par `source`
- toujours utiliser `node` comme variable utilisateur
- garder `instance` uniquement pour la compatibilite des series
