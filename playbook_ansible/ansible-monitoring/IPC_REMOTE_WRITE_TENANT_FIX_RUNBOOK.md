# Runbook
# Remediation Du Remote Write IPC Vers Mimir Multi-Tenant
# Version: 1.0
# Date: 14 avril 2026
# Statut: correctif immediat valide, integration provisioning a faire

## 1. Objet

Ce document decrit :

- la panne observee sur la chaine IPC -> Alloy -> Mimir ;
- la cause racine validee ;
- le correctif manuel immediat a appliquer sur un IPC ;
- la traduction exacte a porter dans le flux de provisioning.

Ce document sert de support de remediation avant industrialisation Ansible.

## 2. Contexte

La VM `monitoring-DEV1-S` heberge maintenant une stack Mimir multi-tenant.

Le modele cible cote Grafana est deja en place :

- dossier `Mimir`
- dashboard `IPC Mimir Dashboard`
- dashboard `VM Mimir Dashboard`

Le dashboard VM fonctionne.

Le dashboard IPC est vide car les metriques IPC ne sont pas acceptees par Mimir.

## 3. Symptome Observe

Symptomes constates :

- Grafana voit bien la datasource `prometheus`
- le dashboard VM affiche les metriques correctement
- le dashboard IPC ne remonte aucune serie
- les requetes Mimir sur un IPC connu retournent `[]`

Exemple de requete vide :

```bash
curl -fsS -H 'X-Scope-OrgID: classic' \
  --get 'http://127.0.0.1:9009/prometheus/api/v1/query' \
  --data-urlencode 'query=up{instance="cascadya-ipc-10-109:9100"}'
```

## 4. Diagnostic Valide

Le diagnostic valide est :

- Alloy tourne sur l'IPC
- `node_exporter` repond localement sur `127.0.0.1:9100`
- la metrique `fanless_pc_temperature_celsius` existe localement
- les labels `source`, `node` et `site` sont bien poses dans la config Alloy IPC
- l'URL cible est correcte : `http://10.42.1.4:9009/api/v1/push`

La cause racine est visible dans les logs Alloy IPC :

```text
server returned HTTP status 401 Unauthorized: no org id
```

Conclusion :

- le probleme n'est pas Grafana ;
- le probleme n'est pas l'UID de datasource ;
- le probleme n'est pas la presence des metriques locales ;
- le probleme est l'absence du header HTTP `X-Scope-OrgID` dans le `remote_write` IPC.

## 5. Cause Racine

Mimir fonctionne maintenant en mode multi-tenant.

Dans ce mode, chaque push vers :

- `http://10.42.1.4:9009/api/v1/push`

doit porter un tenant via le header :

- `X-Scope-OrgID`

Le tenant attendu pour la chaine IPC standard est :

- `classic`

Sans ce header, Mimir rejette les samples avec :

- `401 Unauthorized: no org id`

## 6. Correctif Manuel Immediat Sur Un IPC

### 6.1 Objectif

Ajouter le header tenant dans le bloc :

- `prometheus.remote_write "mimir"`

### 6.2 Sauvegarde

```bash
sudo cp /etc/alloy/config.alloy /etc/alloy/config.alloy.bak.$(date +%Y%m%d-%H%M%S)
```

### 6.3 Correctif Exact A Appliquer

Dans `/etc/alloy/config.alloy`, remplacer le bloc `endpoint` du `remote_write` par :

```alloy
prometheus.remote_write "mimir" {
  endpoint {
    url = "http://10.42.1.4:9009/api/v1/push"
    headers = {
      "X-Scope-OrgID" = "classic",
    }
  }
}
```

### 6.4 Si La Configuration Contient Deja Des Labels Externes

Si ton bloc contient deja `external_labels`, le correctif minimal est uniquement :

```alloy
  endpoint {
    url = "http://10.42.1.4:9009/api/v1/push"
    headers = {
      "X-Scope-OrgID" = "classic",
    }
  }
```

Le reste du bloc peut etre conserve tel quel.

### 6.5 Redemarrage

```bash
sudo systemctl restart alloy
sudo systemctl status alloy --no-pager
```

## 7. Validation Immediate Apres Correctif

### 7.1 Verification Cote IPC

Verifier que les erreurs `no org id` ont disparu :

```bash
sudo journalctl -u alloy -n 50 --no-pager
```

Tu ne dois plus voir :

```text
401 Unauthorized: no org id
```

### 7.2 Verification Cote Monitoring

Depuis `monitoring-DEV1-S` :

```bash
curl -fsS -H 'X-Scope-OrgID: classic' \
  --get 'http://127.0.0.1:9009/prometheus/api/v1/query' \
  --data-urlencode 'query=up{job="node-exporter",source="ipc",node="cascadya-ipc-10-109"}'
```

Le resultat attendu est une serie avec une valeur egale a `1`.

Verifier aussi la temperature :

```bash
curl -fsS -H 'X-Scope-OrgID: classic' \
  --get 'http://127.0.0.1:9009/prometheus/api/v1/query' \
  --data-urlencode 'query=fanless_pc_temperature_celsius{job="node-exporter",source="ipc",node="cascadya-ipc-10-109"}'
```

## 8. Traduction Exacte Dans Le Flux De Provisioning

Le flux de provisioning IPC doit desormais garantir :

- un `remote_write` vers `http://10.42.1.4:9009/api/v1/push`
- un header `X-Scope-OrgID = classic`
- des labels stables compatibles Grafana

### 8.1 Variables A Exposer

Variables minimales a exposer :

- `ipc_alloy_mimir_remote_write_url`
- `ipc_alloy_mimir_tenant`
- `ipc_metrics_site`
- `ipc_metrics_node`

Valeurs initiales recommandees :

```yaml
ipc_alloy_mimir_remote_write_url: "http://10.42.1.4:9009/api/v1/push"
ipc_alloy_mimir_tenant: "classic"
ipc_metrics_site: "SITE-01"
ipc_metrics_node: "cascadya-ipc-10-109"
```

### 8.2 Bloc Alloy Cible

Le template cible doit produire un bloc de ce type :

```alloy
prometheus.remote_write "mimir" {
  external_labels = {
    source            = "ipc",
    node              = "cascadya-ipc-10-109",
    role              = "ipc",
    site              = "SITE-01",
    retention_profile = "classic",
    tenant            = "classic",
  }

  endpoint {
    url = "http://10.42.1.4:9009/api/v1/push"
    headers = {
      "X-Scope-OrgID" = "classic",
    }
  }
}
```

### 8.3 Scrape Local Cible

Le `node_exporter` local doit rester scrappe avec les labels suivants :

```alloy
prometheus.scrape "node_exporter" {
  targets = [
    {
      "__address__"       = "127.0.0.1:9100",
      "job"               = "node-exporter",
      "instance"          = "cascadya-ipc-10-109:9100",
      "source"            = "ipc",
      "node"              = "cascadya-ipc-10-109",
      "role"              = "ipc",
      "site"              = "SITE-01",
      "retention_profile" = "classic",
      "tenant"            = "classic",
    },
  ]

  forward_to = [prometheus.remote_write.mimir.receiver]
}
```

## 9. Criteres D'Acceptation Provisioning

Le provisioning IPC sera considere conforme si :

- Alloy est actif apres reboot ;
- `node_exporter` repond localement ;
- le `remote_write` pousse vers `10.42.1.4:9009/api/v1/push` ;
- `X-Scope-OrgID: classic` est bien envoye ;
- la requete `up{job="node-exporter",source="ipc",node="<ipc>"}` retourne `1` dans Mimir ;
- `IPC Mimir Dashboard` affiche les series pour l'IPC cible.

## 10. Point D'Attention

Le document historique [IPC_ALLOY_MIMIR_CHAIN_PRD.md](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/playbook_ansible/ansible-monitoring/IPC_ALLOY_MIMIR_CHAIN_PRD.md) contient une hypothese de travail plus ancienne ou le multi-tenant n'etait pas encore actif.

Pour l'etat actuel valide, la reference a suivre est :

- [IPC_ALLOY_PROVISIONING_TARGET_PRD.md](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/playbook_ansible/ansible-monitoring/IPC_ALLOY_PROVISIONING_TARGET_PRD.md)
- ce present runbook de remediation

