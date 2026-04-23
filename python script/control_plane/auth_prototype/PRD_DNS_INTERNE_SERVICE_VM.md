# PRD - Configuration d'un DNS interne pour un service heberge sur une VM

Date de reference : 2026-04-16

## 1. Objet

Ce document decrit le modele cible, les prerequis techniques, le cablage Ansible
et la procedure de validation pour exposer un service interne via un FQDN
`*.cascadya.internal`.

Le but n'est pas seulement "d'ajouter un nom DNS".

Dans l'etat reel du lab, un service interne accessible par un nom prive
`*.cascadya.internal` depend de cinq couches qui doivent toutes etre coherentes :

- le service applicatif lui-meme ;
- le reverse proxy / frontal HTTP de la VM cible ;
- le DNS interne sur la gateway WireGuard ;
- la resolution DNS cote clients WireGuard et cote VMs consommatrices ;
- le transport reseau de retour entre `10.8.0.0/16` et `10.42.0.0/16`.

Ce PRD formalise le pattern standard a retenir pour publier correctement un
service interne sur une VM.

## 2. Contexte actuel

### 2.1 Domaine et DNS internes

Le domaine interne retenu dans le repo est :

- `cascadya.internal`

Le DNS interne est aujourd'hui fourni par `dnsmasq` sur :

- VM : `wireguard-DEV1-S`
- IP tunnel : `10.8.0.1`
- role Ansible : [wireguard_dns/tasks/main.yml](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/ansible/roles/wireguard_dns/tasks/main.yml)
- template `dnsmasq` : [cascadya-internal.conf.j2](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/ansible/roles/wireguard_dns/templates/cascadya-internal.conf.j2)

Les enregistrements internes sont portes aujourd'hui par :

- [all.yml](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/ansible/inventory/group_vars/all.yml)
- variable : `wireguard_dns_records`

Exemples deja en place :

- `control-panel.cascadya.internal -> 10.42.1.2`
- `wazuh.cascadya.internal -> 10.42.1.7`
- `auth.cascadya.internal -> 10.42.2.4`
- `portal.cascadya.internal -> 10.42.1.2`
- `features.cascadya.internal -> 10.42.1.2`
- `mosquitto.cascadya.internal -> 10.42.1.6`

### 2.2 Topologie reseau utile

Plans reseau principaux :

- clients WireGuard admin : `10.8.0.0/16`
- gateway WireGuard :
  - IP publique : `51.15.84.140`
  - IP privee : `10.42.1.5`
  - IP tunnel : `10.8.0.1`
- LAN prive cloud : `10.42.0.0/16`

Exemples de VMs service :

- `control-panel-DEV1-S` : `10.42.1.2`
- `monitoring-DEV1-S` : `10.42.1.4`
- `wazuh-DEV1-S` : `10.42.1.7`
- `vault-DEV1-S` : `10.42.2.4`

### 2.3 Pattern d'exposition actuellement utilise

Le pattern reel du repo est :

- le service applicatif tourne localement sur la VM, souvent sur `127.0.0.1`
  ou un port prive ;
- un frontal local (`Traefik` ou `nginx`) termine TLS et route sur le `Host`
  interne ;
- le DNS interne renvoie l'IP privee de la VM ;
- les clients WireGuard et les VMs consommatrices resolvent le nom via
  `10.8.0.1`.

Exemples :

- `control-panel.cascadya.internal`
  - appli FastAPI sur `127.0.0.1:8000`
  - frontal Traefik local sur `:443`
- `wazuh.cascadya.internal`
  - dashboard Wazuh sur la VM Wazuh
  - TLS local sur la cible
- `auth.cascadya.internal`
  - historiquement via Traefik sur la VM Control Panel
  - desormais publie via `nginx` sur la VM Vault
- `portal.cascadya.internal`
  - portail Flask/Waitress sur `127.0.0.1:8788`
  - frontal Traefik local sur `control-panel-DEV1-S`

## 3. Probleme a resoudre

Quand un nouveau service doit etre expose en `*.cascadya.internal`, il faut
eviter les erreurs suivantes :

- creer seulement l'enregistrement DNS sans configurer le frontal HTTP ;
- publier un FQDN qui pointe vers la mauvaise VM ;
- oublier la resolution DNS interne sur les VMs consommatrices ;
- oublier le transport reseau de retour pour les clients WireGuard ;
- oublier d'adapter les allowlists IP du frontal ;
- casser un service existant en modifiant `dnsmasq` ou un vhost de maniere
  non additive.

Le DNS interne doit donc etre traite comme une fonctionnalite transverse, pas
comme un simple ajout de ligne dans un inventaire.

## 4. Objectif cible

Pouvoir ajouter un service interne `nom-service.cascadya.internal` avec les
proprietes suivantes :

- resolution DNS stable via `10.8.0.1` ;
- routage vers l'IP privee correcte de la VM cible ;
- TLS termine sur la VM cible avec un certificat coherent avec le FQDN ;
- acces depuis un client WireGuard admin ;
- acces depuis les VMs applicatives qui doivent consommer ce service ;
- provisioning reproductible via Ansible ;
- non-regression des autres services `*.cascadya.internal`.

## 5. Hors perimetre

Ce PRD ne couvre pas :

- un DNS public Internet ;
- la publication d'un service directement sur son IP publique sans DNS interne ;
- la federation multi-zone DNS externe ;
- l'authentification metier du service lui-meme ;
- la PKI complete, au-dela de l'exigence "le certificat doit correspondre au
  FQDN interne".

## 6. Architecture cible standard

### 6.1 Vue logique

Le pattern a retenir est :

1. un service tourne sur une VM cible ;
2. un frontal local sur cette VM route `Host: service.cascadya.internal` ;
3. `dnsmasq` sur `wireguard-DEV1-S` repond avec l'IP privee de la VM ;
4. les clients et VMs resolvent `service.cascadya.internal` via `10.8.0.1` ;
5. le reseau permet le trajet aller et retour entre client et VM cible.

### 6.2 Vue composant

Composants impliques :

- gateway DNS interne :
  - `wireguard-DEV1-S`
  - `dnsmasq`
  - `10.8.0.1`
- VM cible :
  - service applicatif
  - reverse proxy local (`Traefik` ou `nginx`)
  - certificat TLS adapte au FQDN interne
- VMs consommatrices :
  - `systemd-resolved` / `systemd-networkd` ou equivalent
- clients WireGuard :
  - DNS du tunnel pointe vers `10.8.0.1`

### 6.3 Principe de nommage

Le FQDN interne doit :

- etre stable ;
- representer le service, pas l'implementation ;
- rester decouple d'un port ou d'une techno.

Exemples corrects :

- `control-panel.cascadya.internal`
- `wazuh.cascadya.internal`
- `auth.cascadya.internal`
- `nats.cascadya.internal`

Exemples a eviter :

- `fastapi-control-panel.cascadya.internal`
- `service-8081.cascadya.internal`
- `nginx-vault-auth.cascadya.internal`

## 7. Cablage technique obligatoire

### 7.1 Cote VM cible

Pour qu'un service puisse etre servi par un FQDN interne, la VM cible doit
fournir :

- une IP privee stable sur `10.42.0.0/16` ;
- un service local ;
- un frontal local qui route le bon `Host` ;
- un certificat qui correspond au FQDN ;
- un port d'entree TCP atteignable depuis les clients autorises.

Ce frontal peut etre :

- `Traefik` si la VM suit le pattern Control Panel ;
- `nginx` si la VM suit le pattern Vault ;
- le service lui-meme si l'exposition TLS est geree nativement et proprement.

Le service ne doit pas etre publie "par hasard".

Le FQDN DNS doit toujours correspondre a une route HTTP ou TLS explicite.

### 7.2 Cote DNS interne

Le DNS interne est configure via :

- role : [wireguard_dns/tasks/main.yml](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/ansible/roles/wireguard_dns/tasks/main.yml)
- template : [cascadya-internal.conf.j2](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/ansible/roles/wireguard_dns/templates/cascadya-internal.conf.j2)
- inventory : [all.yml](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/ansible/inventory/group_vars/all.yml)

Le modele actuel de record est :

```yaml
wireguard_dns_records:
  - name: service.cascadya.internal
    address: 10.42.x.y
```

Le template `dnsmasq` produit ensuite :

```text
address=/service.cascadya.internal/10.42.x.y
```

### 7.3 Cote VMs consommatrices

Le point critique revele par la migration Keycloak est le suivant :

- avoir un DNS interne fonctionnel sur `wireguard-DEV1-S` ne suffit pas ;
- encore faut-il que les VMs clientes l'interrogent vraiment pour
  `.cascadya.internal`.

Pour une VM Linux basee sur `systemd-resolved` / `systemd-networkd`, le pattern
recommande est un drop-in sur l'interface privee.

Exemple valide sur `control-panel-DEV1-S` :

```ini
[Network]
DNS=10.8.0.1
Domains=~cascadya.internal

[DHCP]
UseDNS=false
RouteMetric=50
UseMTU=true
```

Objectif :

- forcer les requetes `*.cascadya.internal` vers `10.8.0.1` ;
- sans casser les autres resolvers utilises pour Internet ou metadata.

Ce besoin doit etre gere en Ansible, pas seulement via `resolvectl` runtime.

### 7.4 Cote clients WireGuard

Les clients WireGuard doivent recevoir :

- un DNS de tunnel : `10.8.0.1`
- les routes / `AllowedIPs` adaptees au LAN prive cible

Ce point est deja le modele du lab pour les postes admin.

### 7.5 Cote transport reseau

Le DNS seul ne suffit pas.

Pour qu'un service interne soit effectivement joignable via son FQDN :

- le trafic client doit atteindre la gateway WireGuard ;
- la gateway doit router ou NATer vers `10.42.0.0/16` ;
- la VM cible doit pouvoir renvoyer les paquets.

Constat terrain important :

- en l'absence de route retour des VMs `10.42.1.x` vers `10.8.0.0/16`,
  l'acces depuis un poste admin WireGuard casse, meme si le DNS est bon ;
- la correction operationnelle constatee a consiste a ajouter un `MASQUERADE`
  `wg0 -> ens5` sur `wireguard-DEV1-S`.

Conclusion :

- le DNS interne depend aussi du design de retour reseau ;
- toute publication de nouveau service interne doit valider la couche transport.
- si le transit admin repose sur un NAT `10.8.0.0/16 -> 10.42.0.0/16`, les
  allowlists des frontaux doivent etre alignees sur la source visible
  `10.42.1.5/32`.

### 7.6 Cote allowlists de frontaux

Si le trafic admin est NATe par `wireguard-DEV1-S`, le frontal peut voir la
source :

- `10.42.1.5`

et non plus :

- `10.8.0.x`

Exemple reel :

- le Control Panel etait protege par une allowlist Traefik `10.8.0.0/24` ;
- apres ajout du NAT `wg0 -> ens5`, le service est devenu reachable mais
  renvoyait `403 Forbidden` ;
- la cause etait l'absence de `10.42.1.5/32` dans l'allowlist.

Conclusion :

- si un service est filtre par CIDR, il faut valider quelle IP source il verra
  reellement apres routage / NAT.

Dans l'etat actuel du lab :

- `10.42.1.5/32` doit etre considere comme une source admin legitime pour les
  frontaux exposes via `dnsmasq`.

### 7.7 Point d'exploitation important sur `dnsmasq`

Retour terrain valide le 2026-04-16 :

- `dnsmasq` charge tous les fichiers presents sous `/etc/dnsmasq.d` ;
- laisser un backup du type `*.bak` dans ce dossier peut casser le demarrage du
  service avec une erreur `illegal repeated keyword` ;
- les backups operationnels doivent etre deplaces hors de `/etc/dnsmasq.d`,
  par exemple sous `/root/dnsmasq-backups`.

## 8. Standard de mise en oeuvre pour un nouveau service

### 8.1 Decision d'architecture

Avant toute implementation, il faut figer :

- le FQDN interne ;
- la VM cible ;
- l'IP privee cible ;
- le frontal choisi (`Traefik`, `nginx`, autre) ;
- le certificat a utiliser ;
- la liste des consommateurs :
  - postes admin WireGuard
  - VMs applicatives
  - autres services

### 8.2 Publication du service sur la VM cible

La VM cible doit etre provisionnee pour servir le service en local, par exemple :

- `127.0.0.1:8000`
- `127.0.0.1:8081`
- `10.42.2.4:8081`

Puis un frontal local doit publier :

- `https://service.cascadya.internal`

Ce frontal doit :

- router le bon `Host`
- servir le bon certificat
- ne pas casser les vhosts existants

### 8.3 Publication DNS

Ajouter le record dans :

- `wireguard_dns_records`

Exemple :

```yaml
wireguard_dns_records:
  - name: service.cascadya.internal
    address: 10.42.2.4
```

Puis rejouer le role `wireguard_dns`.

### 8.4 Resolution DNS cote VMs

Pour chaque VM qui doit consommer le service :

- verifier si elle interroge deja `10.8.0.1` pour `.cascadya.internal`
- sinon ajouter un mecanisme persistant de split DNS

Le modele recommande est :

- `DNS=10.8.0.1`
- `Domains=~cascadya.internal`
- `UseDNS=false` sur l'interface privee concernee

### 8.5 Validation transport

Il faut verifier :

- reachability IP entre le client et l'IP privee de la VM cible
- reachability TCP sur le port publie
- retour reseau correct
- impact eventuel du NAT sur la source vue par le service

### 8.6 Validation fonctionnelle

Il faut verifier ensuite :

- `nslookup service.cascadya.internal 10.8.0.1`
- `resolvectl query service.cascadya.internal`
- `getent hosts service.cascadya.internal`
- `curl -k -I https://service.cascadya.internal/`
- comportement du frontal avec le vrai `Host`

## 9. Cablage Ansible recommande

### 9.1 Role existant a reutiliser

Le role central pour la couche DNS interne est :

- [wireguard_dns/tasks/main.yml](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/ansible/roles/wireguard_dns/tasks/main.yml)

Il couvre aujourd'hui :

- installation de `dnsmasq`
- deploiement de `/etc/dnsmasq.d/cascadya-internal.conf`
- activation de `ip_forward`
- ancrage de regles de forwarding WireGuard
- verifications `nslookup`

### 9.2 Extension recommandee du standard

Pour industrialiser correctement un nouveau service interne, il faut distinguer
quatre responsabilites :

1. `service_vm_publish`
   - configure le service local
   - configure le frontal local
   - configure le certificat

2. `wireguard_dns`
   - publie l'enregistrement DNS interne
   - maintient `dnsmasq`

3. `vm_internal_dns_client`
   - configure les VMs consommatrices pour utiliser `10.8.0.1` sur
     `.cascadya.internal`

4. `wireguard_lan_return_path`
   - assure le retour reseau entre `10.8.0.0/24` et `10.42.0.0/16`
   - gere eventuellement le NAT `wg0 -> ens5`

### 9.3 Variables recommandees

Variables DNS :

```yaml
internal_dns_zone: cascadya.internal
internal_dns_server_ip: 10.8.0.1
internal_dns_records:
  - name: service.cascadya.internal
    address: 10.42.2.4
```

Variables service :

```yaml
internal_service_domain: service.cascadya.internal
internal_service_private_ip: 10.42.2.4
internal_service_https_port: 443
internal_service_backend_url: http://127.0.0.1:8081
```

Variables client DNS :

```yaml
internal_dns_consumer_interface: ens6
internal_dns_consumer_domains:
  - "~cascadya.internal"
internal_dns_consumer_server: 10.8.0.1
```

### 9.4 Ordre de deploiement recommande

Ordre cible :

1. provisionner la VM service et son frontal local
2. verifier le service par IP / `Host` force si necessaire
3. publier le record dans `wireguard_dns_records`
4. rejouer le role `wireguard_dns`
5. configurer les resolvers des VMs consommatrices
6. valider depuis :
   - la VM cible
   - une VM consommatrice
   - un poste admin WireGuard

## 10. Procedure de validation

### 10.1 Sur la gateway WireGuard

Verifier que `dnsmasq` sert bien le record :

```bash
nslookup service.cascadya.internal 10.8.0.1
```

Attendu :

- l'IP privee de la VM cible

### 10.2 Sur une VM consommatrice

Verifier la resolution et l'acces :

```bash
SYSTEMD_PAGER=cat resolvectl query service.cascadya.internal
getent hosts service.cascadya.internal
curl -k -I https://service.cascadya.internal/
```

Attendu :

- le nom se resout vers l'IP privee attendue
- le frontal HTTP/TLS repond

### 10.3 Depuis un poste admin WireGuard

Sous Windows, verifier :

```powershell
Resolve-DnsName service.cascadya.internal
curl.exe -k -I --connect-timeout 10 https://service.cascadya.internal/
```

Attendu :

- le DNS retourne l'IP privee attendue
- l'acces HTTPS repond
- pas de `timeout`
- pas de `403` lie a une allowlist incoherente

### 10.4 Si le service est protege par un frontal

Verifier aussi :

- la source IP visible par le frontal
- la compatibilite avec ses CIDR autorises

## 11. Critere d'acceptation

La configuration DNS interne d'un service est consideree comme terminee si :

- le service est atteignable en prive par son FQDN interne ;
- `dnsmasq` retourne l'IP privee attendue ;
- les VMs consommatrices resolvent correctement le nom ;
- le poste admin WireGuard resolvent et atteint correctement le service ;
- le certificat et le `Host` presentes correspondent au FQDN ;
- le retour reseau est valide ;
- l'allowlist du frontal est compatible avec l'IP source reelle ;
- le provisioning Ansible est idempotent ;
- aucun service `*.cascadya.internal` existant n'est casse.

Validation terrain supplementaire sur les services deja publies :

- `auth.cascadya.internal` doit repondre a la discovery OIDC complete depuis le
  poste admin ;
- `portal.cascadya.internal` doit au minimum repondre `303` vers son login ;
- `control-panel.cascadya.internal`, `features.cascadya.internal` et
  `wazuh.cascadya.internal` ne doivent pas regresser lors d'une modification
  `dnsmasq`.

## 12. Rollback

Rollback minimal :

- retirer le record de `wireguard_dns_records`
- rejouer le role `wireguard_dns`
- remettre si besoin la config precedente du frontal local
- remettre si besoin la config DNS cliente precedente
- retirer si besoin la regle de transport / NAT ajoutee specifiquement

Important :

- ne jamais basculer un hostname interne critique sans garder la cible
  precedente tant que la validation n'est pas complete.

## 13. Risques et points de vigilance

Principaux risques :

- record DNS pointant vers la mauvaise VM
- frontal non configure pour le `Host`
- certificat ne correspondant pas au FQDN
- resolver de VM qui n'interroge pas `10.8.0.1`
- retour reseau absent
- NAT qui change la source visible et casse une allowlist
- collision avec un service existant
- confusion entre FQDN interne et IP publique

## 14. Decision d'architecture a retenir

Le standard a retenir pour `*.cascadya.internal` est :

- DNS interne central sur `dnsmasq` via `wireguard-DEV1-S`
- record A vers l'IP privee de la VM cible
- service expose via un frontal local sur cette VM
- split DNS explicite sur les VMs consommatrices
- validation reseau aller + retour
- validation des allowlists apres routage / NAT
- publication et maintenance via Ansible

Ce document doit etre utilise comme reference pour tout nouveau service interne
du type :

- `service.cascadya.internal`
- `api.cascadya.internal`
- `auth.cascadya.internal`
- `portal.cascadya.internal`
- `grafana.cascadya.internal`
- `nats.cascadya.internal`

et plus generalement pour tout service prive qui doit etre partage entre :

- les postes admin WireGuard
- les VMs applicatives cloud
- et les autres briques internes du SI Cascadya.
