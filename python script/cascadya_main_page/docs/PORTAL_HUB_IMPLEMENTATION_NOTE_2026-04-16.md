# Dossier technique - Portail Hub Cascadya MVP

## 1. Objet

Ce document explique:

- a quoi sert le portail construit dans ce repo
- ce qui a ete effectivement implemente
- comment il est heberge et publie
- comment il s'articule avec Keycloak et les autres services

## 2. Finalite du portail

Le portail n'est pas une super-application qui embarque toutes les UIs.

Sa fonction est plus simple:

- servir de point d'entree humain apres login
- centraliser les liens vers les outils Cascadya
- reutiliser la session Keycloak existante
- filtrer ce qui est visible selon les roles ou groupes utilisateur

En pratique, le portail est un hub SSO de navigation.

## 3. Perimetre fonctionnel implemente

Le MVP livre:

- un flux OIDC vers Keycloak
- un callback de retour portail
- un logout portail avec tentative de logout RP-initiated
- des pages de navigation:
  - `/`
  - `/operations`
  - `/monitoring`
  - `/security`
  - `/platform`
- un filtrage de cartes par tags
- une UX serveur simple avec templates Jinja
- des endpoints de verification:
  - `/api/healthz`
  - `/api/status`
  - `/api/me`

## 4. Architecture retenue

### 4.1 Separation des responsabilites

La separation voulue par le MVP a ete respectee:

- `auth.cascadya.internal` reste le point d'identite
- `portal.cascadya.internal` est le point d'entree humain
- les applications conservent leur domaine natif

Exemples:

- `control-panel.cascadya.internal`
- `features.cascadya.internal`
- `grafana.cascadya.internal`
- `wazuh.cascadya.internal`

### 4.2 Pas de mega reverse proxy fonctionnel

Le portail:

- ne remplace pas les routes des applications
- ne proxy pas leurs APIs metier
- n'embarque pas leurs UIs
- n'utilise pas d'iframe pour les integrer

Chaque carte ouvre le service cible sur son domaine d'origine.

## 5. Stack technique implementee

La stack retenue est volontairement legere:

- Python 3
- Flask
- templates Jinja
- CSS/JS statiques
- Waitress comme serveur HTTP applicatif

Le choix a ete fait pour:

- limiter la dette de setup
- deployer vite sur `control-panel-DEV1-S`
- rester facile a debugger

## 6. Flux d'authentification implemente

Le portail utilise un flux OIDC code classique:

1. l'utilisateur ouvre `portal.cascadya.internal`
2. s'il n'est pas authentifie, le portail le redirige vers Keycloak
3. Keycloak renvoie sur `/auth/callback`
4. le portail echange le code contre des tokens
5. le portail recupere les claims utilisateur
6. le portail cree une session HTTP locale
7. le portail affiche les cartes autorisees

Le portail lit les informations utilisateur a partir de:

- `access token`
- `id token`
- `userinfo`

Les claims sont fusionnees avant calcul des tags utilisateur.

## 7. Modele d'autorisation implemente

Le portail supporte deux niveaux de filtrage.

### 7.1 Garde globale

Variable:

- `PORTAL_REQUIRED_TAGS`

Usage:

- si vide, tout utilisateur authentifie entre dans le portail
- si renseignee, l'utilisateur doit porter au moins un des tags listes

### 7.2 Garde par carte

Chaque carte declare ses `required_tags`.

Exemple:

- `Control Panel` attend `control-panel-user` ou `portal-admin`
- `Grafana` attend `grafana-user` ou `monitoring-user` ou `portal-admin`

Le portail calcule ses tags a partir de:

- `realm_access.roles`
- `resource_access.*.roles`
- `roles`
- `groups`
- `group_membership`

## 8. Cartes implementees dans le MVP

### 8.1 Operations

- `Control Panel`
- `Features`

### 8.2 Monitoring

- `Grafana`
- `Mimir` ouvre un point d'entree Grafana-backed tant qu'il n'existe pas de vraie UI humaine distincte

### 8.3 Security

- `Wazuh`

### 8.4 Platform

- `Keycloak Admin`
- `Platform Docs` si une URL documentaire est configuree

## 9. Hebergement et exposition

### 9.1 Runtime applicatif

Le portail tourne sur `control-panel-DEV1-S`.

Emplacements principaux:

- code: `/opt/cascadya_portal_hub`
- env: `/etc/cascadya-portal/cascadya-portal.env`
- service: `/etc/systemd/system/cascadya-portal-hub.service`

Le backend ecoute localement sur:

- `127.0.0.1:8788`

### 9.2 Publication HTTPS

Traefik sur la VM Control Panel publie:

- `portal.cascadya.internal`

Le vhost dynamique est pose dans:

- `/opt/traefik-control-panel/dynamic/cascadya-portal-hub.yml`

Un certificat auto-signe local est utilise a ce stade pour le portail.

### 9.3 Filtrage reseau

Le portail a ete aligne avec la logique d'allowlist Traefik existante sur la VM.

CIDRs actuellement pris en compte pour l'acces au vhost:

- `10.8.0.0/24`
- `10.42.1.5/32`
- `195.68.106.70/32`

## 10. Methode de deploiement mise en place

Deux voies de deploiement ont ete outillees.

### 10.1 Depuis Windows

Scripts fournis:

- `scripts/deploy-live.ps1`
- `scripts/deploy-live.cmd`
- `scripts/check-live.ps1`
- `scripts/check-live.cmd`

### 10.2 Depuis WSL

Flux pratique retenu:

- `syncproject`
- `rsync` du repo vers `/opt/cascadya_portal_hub`
- `scp` du `.env`
- restart `systemd`
- verification HTTP locale

## 11. Etat reel du systeme au 16 avril 2026

Le portail est deploye et repond correctement.

Verifications validees:

- `http://127.0.0.1:8788/api/healthz` -> `{"status":"ok"}`
- `http://127.0.0.1:8788/api/status` -> `status=ok`
- `https://portal.cascadya.internal/` redirige vers `/auth/login`
- le flux Keycloak authentifie bien l'utilisateur

Le point restant au moment de la redaction n'est pas l'authentification, mais l'attribution des roles metier Keycloak permettant d'ouvrir les cartes.

## 12. Pourquoi les cartes peuvent rester verrouillees apres login

Le portail distingue:

- connexion reussie
- autorisation metier reussie

Un utilisateur peut donc:

- etre authentifie
- voir son nom et son email
- mais ne pas avoir les tags attendus pour ouvrir les cartes

Exemple constate:

- l'utilisateur recupere seulement des roles Keycloak standards
- aucune carte metier ne s'ouvre tant que les roles comme `control-panel-user` ou `monitoring-user` ne sont pas attribues

## 13. Fichiers importants du repo

- `portal_hub/config.py`
- `portal_hub/oidc.py`
- `portal_hub/auth.py`
- `portal_hub/catalog.py`
- `portal_hub/server.py`
- `deploy/cascadya-portal-hub.service.template`
- `deploy/cascadya-portal-hub.traefik.yml.template`
- `deploy/cascadya-portal-hub.env.template`

## 14. Suite logique recommandee

1. finaliser les roles Keycloak dans `vault-DEV1-S`
2. revalider l'ouverture des cartes selon les roles
3. remettre la garde globale `PORTAL_REQUIRED_TAGS=portal-access,portal-admin` si elle a ete ouverte pour les tests
4. ajouter le DNS `portal.cascadya.internal` dans `dnsmasq`
5. documenter officiellement le modele role -> cartes dans la doc plateforme
