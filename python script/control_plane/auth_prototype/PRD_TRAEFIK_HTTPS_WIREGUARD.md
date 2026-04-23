# PRD - Integration Traefik & Passage en HTTPS pour le Control Panel

Version: 1.0
Date: 2026-03-26
Statut: cible technique suivante
Auteur: Codex

## 1. Contexte & Objectifs

### 1.1 Contexte

Le prototype actuel du Control Plane, base sur `FastAPI`, est deploye sur une VM dediee et ecoute actuellement en HTTP clair sur le port `8000`.

L'ecosysteme Cascadya utilise deja `Traefik` pour d'autres composants. Afin de rester coherent avec l'existant, le Control Panel sera expose derriere Traefik comme reverse proxy HTTPS.

L'objectif est de publier l'application derriere un nom de domaine propre tout en conservant une contrainte forte :

- l'interface web ne doit etre accessible qu'aux clients autorises ;
- en priorite, l'acces doit etre reserve aux clients du VPN WireGuard ;
- le backend FastAPI ne doit plus etre exposé directement.

### 1.2 Objectifs

- Exposer l'application derriere `https://control-panel.cascadya.com`
- Deleguer a Traefik la terminaison TLS
- Automatiser l'obtention et le renouvellement du certificat
- Restreindre strictement l'acces a l'application aux IP du VPN WireGuard et, si necessaire, a l'IP d'administration
- Empecher tout acces direct a FastAPI depuis l'exterieur

## 2. Architecture cible

### 2.1 Variante recommandee si Traefik tourne sur la meme VM

```text
Client (WireGuard 10.8.0.x)
  -> HTTPS 443
  -> Traefik
  -> Middleware ipAllowList
  -> FastAPI sur 127.0.0.1:8000
```

### 2.2 Variante si Traefik est centralise sur une autre VM

```text
Client (WireGuard 10.8.0.x)
  -> HTTPS 443
  -> Traefik Gateway
  -> Middleware ipAllowList
  -> FastAPI sur IP privee de la VM control-panel:8000
```

Dans ce second cas :

- le port `8000` ne doit pas etre expose publiquement ;
- il doit etre autorise uniquement depuis le reseau prive ou depuis la VM Traefik.

## 3. Exigence de securite

### 3.1 Acces a l'interface

L'interface web du Control Panel doit etre accessible uniquement depuis :

- `10.8.0.0/24` pour WireGuard
- `195.68.106.70/32` pour l'administration de secours si necessaire

Toute autre IP doit etre rejetee avant d'atteindre FastAPI.

### 3.2 Acces direct au backend

Le backend FastAPI ne doit plus ecouter sur `0.0.0.0:8000`.

Il doit ecouter :

- sur `127.0.0.1:8000` si Traefik est local
- sur l'IP privee uniquement si Traefik est distant

Le port `8000` ne doit pas etre accessible publiquement.

## 4. Pre-requis DNS & reseau

### 4.1 DNS

Creer un enregistrement DNS :

- `control-panel.cascadya.com`

Deux approches possibles :

#### Option A - DNS public

- `A -> IP publique de la VM`
- utilisable avec certificat public Let's Encrypt

#### Option B - Split-horizon / DNS interne

- les clients VPN resolvent `control-panel.cascadya.com` vers l'IP privee ou WireGuard
- approche plus propre si l'objectif est un acces strictement prive

### 4.2 Security Group / firewall

#### Si Traefik utilise HTTP-01 pour Let's Encrypt

- ouvrir `TCP 80`
- ouvrir `TCP 443`
- fermer `TCP 8000` au public

#### Si Traefik utilise DNS-01

- ouvrir seulement `TCP 443`
- fermer `TCP 80` si non requis
- fermer `TCP 8000` au public

### 4.3 Recommendation securite

Si l'objectif est "webpage WireGuard-only" au sens strict :

- preferer `DNS-01`
- restreindre `443` au VPN + IP admin
- garder `8000` totalement ferme publiquement

## 5. Specifications Traefik

### 5.1 Router

Le routeur HTTP doit :

- matcher `Host(\`control-panel.cascadya.com\`)`
- utiliser l'entrypoint HTTPS, par exemple `websecure`
- activer TLS
- utiliser le `certResolver` existant dans l'infra

### 5.2 Middleware IP

Le middleware doit etre de type `ipAllowList`.

CIDR autorises :

- `10.8.0.0/24`
- `195.68.106.70/32`

Toute requete hors de cette liste doit etre rejetee avec `403 Forbidden`.

### 5.3 Service backend

#### Cas Traefik local

```yaml
url: "http://127.0.0.1:8000"
```

#### Cas Traefik distant

```yaml
url: "http://10.42.x.x:8000"
```

Il faut utiliser l'IP privee reelle de la VM control-panel.

## 6. Exemple de configuration dynamique Traefik

Ce YAML suppose que Traefik tourne sur la meme VM et lit une configuration dynamique via le file provider.

```yaml
http:
  middlewares:
    control-panel-ip-allowlist:
      ipAllowList:
        sourceRange:
          - "10.8.0.0/24"
          - "195.68.106.70/32"

  routers:
    control-panel-router:
      rule: "Host(`control-panel.cascadya.com`)"
      entryPoints:
        - websecure
      middlewares:
        - control-panel-ip-allowlist
      service: control-panel-service
      tls:
        certResolver: letsencrypt

  services:
    control-panel-service:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:8000"
```

Si Traefik est sur une autre VM, remplacer uniquement l'URL du service.

## 7. Ajustements FastAPI / Uvicorn

Le service applicatif doit etre modifie pour ecouter localement et faire confiance au proxy.

Commande recommandee :

```bash
python -m uvicorn auth_prototype.app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips=127.0.0.1
```

Si Traefik est distant, remplacer `127.0.0.1` dans `--forwarded-allow-ips` par l'IP privee de la VM Traefik, ou une liste d'IP/proxys de confiance.

### Ajustements applicatifs requis

- ajouter `TrustedHostMiddleware` pour autoriser `control-panel.cascadya.com`
- passer `AUTH_PROTO_SECURE_COOKIES=true` une fois HTTPS actif
- conserver `AUTH_PROTO_SAMESITE=lax` sauf besoin contraire

## 8. Repartition des responsabilites

### 8.1 Infrastructure

Gere :

- DNS
- Security Group
- firewall
- placement reseau entre Traefik et la VM control-panel
- mode ACME choisi

### 8.2 Traefik

Gere :

- TLS
- reverse proxy
- filtrage IP
- routage par host
- renouvellement des certificats

### 8.3 VM Control Panel

Gere :

- runtime Python
- service `systemd`
- fichier d'environnement
- application FastAPI

### 8.4 Application

Gere :

- login
- session
- RBAC
- pages HTML
- API protegees

## 9. Criteres d'acceptation

- `control-panel.cascadya.com` resout correctement vers la cible attendue
- le certificat TLS est valide
- `FastAPI` n'est plus expose publiquement sur `8000`
- avec VPN ON, `https://control-panel.cascadya.com/auth/login` fonctionne
- avec VPN OFF, l'acces est refuse par Traefik via `403`
- les cookies de session fonctionnent en HTTPS
- le flux `login -> session -> /app -> /admin` fonctionne derriere Traefik
- les logs Traefik et FastAPI permettent de diagnostiquer les acces refuses

## 10. Decision recommandee

Decision recommandee :

- rester sur Traefik
- conserver le nommage `control-panel.cascadya.com`
- utiliser `ipAllowList`
- faire ecouter FastAPI en local uniquement
- fermer l'acces public direct a `8000`
- privilegier `DNS-01` si l'exposition doit etre vraiment minimale
- sinon garder `HTTP-01` si c'est deja le standard Traefik de l'infra, en acceptant l'ouverture technique de `80` pour l'ACME challenge

## 11. Point d'attention principal

Si l'objectif est "100% WireGuard only to the webpage", la cible doit respecter au minimum :

- `443` filtre WireGuard/admin
- `8000` ferme au public
- backend FastAPI non atteignable directement

Si l'objectif est strictement prive aussi au niveau des ports web, alors :

- preferer `DNS-01`
- eviter de laisser `80` expose au monde entier
- envisager un DNS interne ou split-horizon si l'architecture le permet

## 12. Sources de reference

- Traefik `ipAllowList` : https://doc.traefik.io/traefik/v3.3/middlewares/http/ipallowlist/
- Traefik routers : https://doc.traefik.io/traefik/v3.3/routing/routers/
- Traefik file provider : https://doc.traefik.io/traefik/v3.3/providers/file/
- FastAPI behind a proxy : https://fastapi.tiangolo.com/advanced/behind-a-proxy/
- Uvicorn settings : https://www.uvicorn.org/settings/
- Let's Encrypt challenge types : https://letsencrypt.org/fr/docs/challenge-types/
