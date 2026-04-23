# PRD - Etat actuel du Control Panel sur VM DEV1-S

Version: 1.1
Date: 2026-04-14
Statut: reference technique courante
Auteur: Codex

## 1. Objet du document

Ce document decrit l'etat actuel de ce qui a ete mis en place pour preparer le Control Panel Cascadya sur une VM dediee Scaleway.

Il sert a:

- documenter l'infrastructure actuellement provisionnee;
- cadrer les composants necessaires pour se connecter a la VM;
- lister les composants applicatifs utiles pour tester la partie Auth;
- fournir une base claire pour la suite du developpement et du deploiement du control panel sur serveur.

Ce document couvre l'etat reel au 2026-04-14, apres les mises a jour
Terraform des security groups et des outputs prives.

## 2. Resume executif

Une nouvelle VM Scaleway `DEV1-S` a ete ajoutee dans l'environnement `dev` pour heberger les premiers tests serveur du futur control panel.

Etat actuel:

- VM creee avec succes via Terraform;
- nom de VM: `control-panel-DEV1-S`;
- IPv4 publique: `51.15.115.203`;
- IPv4 privee: `10.42.1.2`;
- disque de donnees additionnel: `20 Go`;
- rattachement reseau prive: segment `app`;
- security group dedie cree pour ne pas exposer le port de test Auth aux autres VMs;
- acces HTTPS cible: `443/TCP` uniquement depuis `10.8.0.0/24` et le CIDR d'administration;
- scrape `node_exporter` autorise sur `9100/TCP` uniquement depuis `10.42.1.4/32`;
- acces SSH actuellement ouvert publiquement de facon temporaire;
- prototype Auth existant en local, pret a etre deploye manuellement sur la VM.

Objectif immediat:

- deployer le prototype `FastAPI` d'authentification sur la VM;
- verifier le flux de login, session cookie et RBAC depuis un vrai serveur;
- preparer ensuite le passage vers un vrai control plane / control panel plus complet.

## 3. Contexte de decision

Une VM `DEV1-S` supplementaire a ete validee pour supporter les tests du control panel cote serveur.

Hypothese budget retenue:

- compute: `6.30 EUR / mois`
- IP publique: `2.85 EUR / mois`
- stockage `20 Go`: `1.70 EUR / mois`
- total supplementaire: `10.85 EUR / mois`
- cout total serveur estime apres ajout: `101.07 EUR / mois`

Contrainte budgetaire partagee:

- coupon restant: `584.51 EUR`
- horizon estime restant: `6 mois`

## 4. Infrastructure provisionnee

### 4.1 Ressources creees

Les ressources suivantes ont ete creees par Terraform dans `infrastructure/environments/dev`:

- `scaleway_instance_security_group.control_panel`
- `module.control_panel.scaleway_instance_ip.server_ip`
- `module.control_panel.scaleway_block_volume.data_volume`
- `module.control_panel.scaleway_instance_server.server`

Resultat du dernier `apply`:

- `4 added`
- `0 changed`
- `0 destroyed`

### 4.2 Caracteristiques de la VM

- Nom: `control-panel-DEV1-S`
- Type: `DEV1-S`
- Image: `ubuntu_jammy`
- Region/zone cible: `nl-ams-1`
- IP publique: `51.15.115.203`
- Volume additionnel: `control-panel-DEV1-S-data`
- Taille du volume: `20 Go`
- Reseau prive: `module.network.private_network_ids["app"]`

### 4.3 Sortie Terraform disponible

Des sorties Terraform sont disponibles pour faciliter la recuperation des IPs:

- `control_panel_ipv4`
- `control_panel_private_ip`

## 5. Composants Terraform importants

### 5.1 Module VM

La nouvelle VM est declaree dans:

- `infrastructure/environments/dev/main.tf`

Bloc ajoute:

- module `control_panel`
- source `../../modules/scaleway-instance`
- type `DEV1-S`
- image `ubuntu_jammy`
- volume `20 Go`
- `user_data = local.user_data_common`

Le module `scaleway-instance` fournit:

- une IP publique;
- un volume block storage;
- une instance Scaleway;
- l'attachement eventuel a un private network;
- un `ignore_changes = [user_data]` pour eviter le bruit Terraform apres creation.

### 5.2 Security group dedie

Un fichier dedie a ete ajoute:

- `infrastructure/environments/dev/control-panel-sg.tf`

But:

- isoler les regles du control panel;
- eviter d'ouvrir des ports applicatifs et de scrape sur d'autres serveurs;
- garder un modele simple pour les tests.

### 5.3 Centralisation du CIDR d'administration

Le CIDR d'administration est maintenant centralise dans:

- `infrastructure/environments/dev/variables.tf`

Local defini:

- `local.mgmt_cidrs = ["195.68.106.70/32"]`

Ce CIDR est reutilise:

- par le module reseau principal;
- par le SG dedie du control panel.

## 6. Modele d'acces reseau actuel

### 6.1 Acces SSH

Le SSH vers `control-panel-DEV1-S` est autorise depuis:

- `0.0.0.0/0` de facon temporaire
- `10.8.0.0/24` via la couche WireGuard / administration
- `195.68.106.70/32` via le CIDR d'administration

Point d'attention:

- l'ouverture `22/TCP` mondiale est temporaire et devra etre refermee une fois
  les acces admin stabilises via WireGuard ou `/32` dedies.

### 6.2 Acces applicatif Auth

Le port expose par Terraform pour l'acces applicatif est:

- `TCP 443`

Il est autorise depuis:

- `10.8.0.0/24`
- `195.68.106.70/32`

Il n'est pas ouvert a `0.0.0.0/0`.

Note importante:

- le port `8000/TCP` n'est plus ouvert par Terraform sur le SG courant ;
- si le prototype Auth doit encore ecouter en `8000`, cela devra passer par un
  tunnel SSH, un reverse proxy local ou une evolution explicite du SG.

### 6.3 Communication privee intra-VPC

Le SG dedie autorise explicitement :

- `9100/TCP` depuis `10.42.1.4/32`

Usage vise :

- permettre a `monitoring-DEV1-S` de scrapper `node_exporter` sur le control
  panel via l'IP privee `10.42.1.2`.

### 6.4 Note importante sur le SMTP

Le SG dedie du control panel a `enable_default_security = true` par defaut cote Scaleway, car ce parametre n'a pas ete desactive sur ce SG specifique.

Impact:

- pour de simples tests Auth, ce n'est pas bloquant;
- si le control panel doit plus tard envoyer des mails SMTP sortants, il faudra probablement ajuster ce point.

## 7. Acces et connexion a la VM

### 7.1 Cible

- IP publique: `51.15.115.203`

### 7.2 Prerequis poste operateur

Pour se connecter proprement a la VM il faut:

- une cle SSH deja presente dans `local.user_data_common`;
- etre sur le reseau VPN `10.8.0.0/24` ou depuis le CIDR `195.68.106.70/32`;
- disposer des droits d'administration habituels sur le projet.

### 7.3 Injection des cles SSH

La VM est creee avec le `cloud-init` commun defini dans:

- `infrastructure/environments/dev/variables.tf`

Ce `cloud-init` injecte les cles publiques suivantes si elles existent sur la machine qui lance Terraform:

- `~/.ssh/publickeyopenssh.pub`
- `~/.ssh/Luc.pub`
- `~/.ssh/id_ed25519.pub`

### 7.4 Mode de connexion attendu

Connexion de reference:

```bash
ssh ubuntu@51.15.115.203
```

Le nom d'utilisateur exact depend de l'image Ubuntu et des usages deja en place sur vos autres VMs, mais `ubuntu` est l'hypothese naturelle sur `ubuntu_jammy`.

## 8. Prototype Auth disponible pour deploiement

### 8.1 Emplacement local

Le prototype a deployer se trouve hors repo Infra, dans:

- `C:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\python script\control_plane\auth_prototype`

### 8.2 Nature du prototype

Le prototype actuel est une petite application web `FastAPI` server-rendered, destinee a valider:

- le flux de connexion operateur;
- la protection de routes HTML;
- la protection de routes API JSON;
- une premiere couche RBAC `operator` / `admin`;
- la gestion de session via cookie signe.

### 8.3 Dependances Python

Fichier:

- `python script/control_plane/auth_prototype/requirements.txt`

Dependances:

- `fastapi`
- `uvicorn[standard]`
- `jinja2`
- `python-multipart`
- `itsdangerous`

### 8.4 Parametres runtime actuels

Fichier:

- `python script/control_plane/auth_prototype/app/config.py`

Variables d'environnement supportees:

- `AUTH_PROTO_APP_NAME`
- `AUTH_PROTO_SESSION_SECRET`
- `AUTH_PROTO_SESSION_COOKIE`
- `AUTH_PROTO_SECURE_COOKIES`
- `AUTH_PROTO_SAMESITE`
- `AUTH_PROTO_SESSION_TTL_SECONDS`

Valeurs importantes par defaut:

- secret de session par defaut non securise pour exposition Internet;
- `secure_cookies = false` par defaut;
- `same_site = "lax"`
- TTL de session `28800` secondes

Conclusion:

- acceptable pour un test serveur controle;
- insuffisant tel quel pour une exposition publique durable.

## 9. Composants applicatifs importants pour la connexion

### 9.1 Middleware de session

Le prototype repose sur `SessionMiddleware` de Starlette, configure dans:

- `python script/control_plane/auth_prototype/app/main.py`

Responsabilite:

- generer et verifier le cookie de session signe;
- garder l'etat de l'utilisateur cote client;
- permettre les redirects et la protection des pages.

### 9.2 Moteur HTML

Le rendu HTML est base sur `Jinja2Templates`.

Templates utiles:

- `login.html`
- `dashboard.html`
- `admin.html`
- `unauthorized.html`

Interet cote VM:

- permet un test navigateur immediat sans front React;
- reduit la friction pour valider la couche serveur.

### 9.3 Verification des credentials

Fichier:

- `python script/control_plane/auth_prototype/app/security.py`

Points clefs:

- comptes de demo statiques `operator` et `admin`;
- mots de passe verifies avec `hashlib.scrypt`;
- comparaison securisee avec `hmac.compare_digest`;
- creation d'un payload de session minimal.

### 9.4 Comptes de demo actuels

- `operator / operator123!`
- `admin / admin123!`

Usage:

- `operator` pour valider le dashboard et `GET /api/me`
- `admin` pour valider `/admin` et `GET /api/admin/audit`

### 9.5 Endpoints utiles pour le test

- `GET /healthz`
- `GET /auth/login`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /app`
- `GET /admin`
- `GET /api/me`
- `GET /api/admin/audit`

## 10. Mode de lancement sur la VM

### 10.1 Hypothese de travail actuelle

Le prototype doit d'abord etre lance en mode simple pour valider le comportement sur serveur, sans systeme de deployment complexe.

Commande de reference:

```bash
python -m uvicorn auth_prototype.app.main:app --host 0.0.0.0 --port 8000
```

Important:

- `--host 0.0.0.0` est necessaire pour ecouter depuis l'exterieur de la VM;
- le SG dedie autorise deja `TCP 8000` depuis VPN + CIDR d'administration;
- cela suffit pour une premiere validation manuelle.

### 10.2 URL de test cible

Une fois l'application lancee sur la VM:

- `http://51.15.115.203:8000/auth/login`

Cette URL ne sera accessible que:

- depuis le VPN;
- ou depuis le CIDR d'administration.

## 11. Parcours de dev cote VM

### 11.1 Parcours minimal recommande

1. SSH sur `control-panel-DEV1-S`
2. installer Python/venv si necessaire
3. copier ou cloner `auth_prototype`
4. installer les dependances
5. definir un vrai `AUTH_PROTO_SESSION_SECRET`
6. lancer `uvicorn` sur `0.0.0.0:8000`
7. tester `/healthz`, `/auth/login`, `/api/me`

### 11.2 Variables a fixer avant test serieux

Au minimum:

- `AUTH_PROTO_SESSION_SECRET`
- `AUTH_PROTO_SECURE_COOKIES=false` tant qu'on reste en HTTP simple

Plus tard, avec HTTPS:

- `AUTH_PROTO_SECURE_COOKIES=true`

### 11.3 Ce que la VM permet maintenant

La VM permet immediatement:

- de valider le prototype Auth hors local;
- de verifier le comportement reel des cookies de session;
- de tester les flux de login/logout sur une vraie IP publique;
- de preparer la prochaine etape de dev du control panel.

## 12. Ce qui n'est pas encore fait

Ce qui reste hors scope ou non fait a ce stade:

- deployment automatise du prototype sur la VM;
- service `systemd` pour garder `uvicorn` actif;
- reverse proxy `nginx` ou `caddy`;
- HTTPS/TLS pour le control panel;
- branchement Keycloak OIDC;
- base PostgreSQL pour les utilisateurs ou sessions;
- CI/CD de deploiement;
- observabilite dediee au control panel;
- gestion production des secrets de session.

## 13. Risques et points d'attention

### 13.1 Securite applicative

Le prototype Auth actuel reste un prototype:

- comptes demo en dur;
- pas de CSRF dedie;
- pas de MFA;
- pas de SSO;
- pas de persistance des utilisateurs;
- secret de session faible si non surcharge.

Il ne faut pas traiter cette application comme un service Internet final.

### 13.2 Exposition reseau

Le port `8000` n'est plus modele par Terraform dans le SG courant. Le port
expose cote infra reste `443`.

Mais:

- l'application reste en HTTP simple;
- si besoin d'acces plus large, il faudra passer par un proxy et du TLS.

### 13.3 Exploitabilite

Sans service manager:

- si `uvicorn` est lance a la main, il tombera a la fermeture de session;
- ce mode est acceptable pour un test ponctuel;
- pas pour une phase de recette plus longue.

## 14. Etat de preparation pour la suite

Le socle minimum cote VM est maintenant pret.

Ce que l'on a de disponible:

- une VM dediee et isolee;
- une IP publique connue;
- un port applicatif de test pre-ouvert;
- des cles SSH injectees;
- un prototype Auth local pret a etre embarque.

Le prochain jalon logique est:

- deployer `auth_prototype` sur `control-panel-DEV1-S`;
- valider la connexion operateur via navigateur;
- ensuite cadrer un mode de run plus propre (`systemd`, reverse proxy, puis OIDC/Keycloak).

## 15. Livrables et fichiers de reference

### 15.1 Infrastructure

- `infrastructure/environments/dev/main.tf`
- `infrastructure/environments/dev/control-panel-sg.tf`
- `infrastructure/environments/dev/variables.tf`
- `infrastructure/modules/scaleway-instance/main.tf`

### 15.2 Prototype applicatif

- `python script/control_plane/auth_prototype/README.md`
- `python script/control_plane/auth_prototype/app/main.py`
- `python script/control_plane/auth_prototype/app/config.py`
- `python script/control_plane/auth_prototype/app/security.py`
- `python script/control_plane/auth_prototype/PRD_AUTHENTIFICATION.md`

## 16. Recommandation immediate

Recommendation concrete:

- utiliser la nouvelle VM uniquement pour le test serveur de l'Auth dans un premier temps;
- ne pas ouvrir davantage de ports pour l'instant;
- aligner le deploiement applicatif sur le port expose `443` ou utiliser un
  tunnel/reverse proxy pour les tests de prototype;
- verifier les flux `login -> session -> dashboard -> admin/API`;
- une fois valide, preparer un deployment plus propre et la migration progressive vers la cible `Keycloak + FastAPI control plane`.
