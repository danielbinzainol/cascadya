# PRD - Etat actuel du Control Panel sur VM DEV1-S

Version: 1.0
Date: 2026-03-26
Statut: reference technique courante
Auteur: Codex

## 1. Objet du document

Ce document decrit l'etat atteint au 2026-03-26 pour le prototype Auth du futur Control Panel Cascadya deploye sur une VM dediee Scaleway.

Il sert a :

- documenter l'infrastructure cible utilisee pour les tests serveur ;
- documenter le prototype applicatif actuellement deploye ;
- decrire precisement la facon dont le runtime a ete installe sur la VM ;
- lister ce qui fonctionne deja ;
- cadrer les limites actuelles ;
- fournir la base technique pour la prochaine phase de durcissement et d'integration.

Ce document decrit l'etat reel atteint au 2026-03-26, apres :

- creation de la VM `control-panel-DEV1-S` ;
- deploiement manuel du prototype Auth `FastAPI` ;
- mise en place d'un service `systemd` ;
- validation des endpoints `/healthz` et `/auth/login`.

## 2. Resume executif

Au 2026-03-26, le prototype Auth du futur control panel est operationnel sur une VM dediee.

Ce qui est atteint :

- une VM `control-panel-DEV1-S` existe en environnement `dev` ;
- la VM expose une IPv4 publique de test ;
- le port applicatif `8000` est ouvert de maniere restreinte ;
- le code applicatif `auth_prototype` a ete copie sur la VM ;
- un environnement virtuel Python a ete cree ;
- les dependances de l'application ont ete installees ;
- un fichier d'environnement runtime a ete cree sur la VM ;
- le service `control-panel-auth` a ete installe et active via `systemd` ;
- l'application repond correctement sur `GET /healthz` ;
- la page `GET /auth/login` est accessible ;
- le prototype est pret pour des tests manuels avec utilisateurs de demonstration.

Conclusion :

le prototype n'est plus seulement un test local. Il fonctionne maintenant sur un vrai serveur distant, avec un mode de lancement persistent.

## 3. Perimetre atteint aujourd'hui

### 3.1 Cote infrastructure

Infrastructure disponible :

- VM dediee pour le control panel ;
- IP publique de test ;
- attachement reseau prive ;
- security group dedie ;
- port de test Auth expose de facon controlee ;
- acces SSH restreint.

### 3.2 Cote application

Application disponible :

- prototype Auth web `FastAPI` server-rendered ;
- sessions web basees sur cookie signe ;
- pages HTML protegees ;
- API JSON protegees ;
- RBAC simple `operator` / `admin` ;
- service lance sur la VM via `systemd`.

### 3.3 Cote exploitation

Runbook de base disponible :

- installation prerequis Ubuntu ;
- copie du code sur la VM ;
- creation du venv ;
- installation des requirements ;
- creation du fichier env ;
- lancement manuel pour smoke test ;
- conversion en service `systemd`.

## 4. Infrastructure cible utilisee

### 4.1 VM

VM de reference :

- Nom : `control-panel-DEV1-S`
- Type : `DEV1-S`
- OS : `ubuntu_jammy`
- Environnement : `dev`
- Role : hebergement des premiers tests serveur du futur control panel

### 4.2 Reseau

Etat connu du reseau de test :

- IPv4 publique attribuee a la VM ;
- rattachement a un reseau prive `app` ;
- policy d'exposition limitee au strict necessaire pour les tests.

### 4.3 Security group

Le security group dedie autorise :

- SSH uniquement depuis le VPN WireGuard et le CIDR d'administration ;
- le port `TCP 8000` uniquement depuis le VPN WireGuard et le CIDR d'administration ;
- le trafic prive intra-reseau pour les futures integrations.

Consequence immediate :

le prototype Auth n'est pas expose au monde entier. Il n'est testable que depuis les reseaux autorises.

## 5. Architecture technique actuelle

### 5.1 Vue d'ensemble

```text
Navigateur
  ->
IP publique VM:8000
  ->
Uvicorn
  ->
FastAPI
  ->
SessionMiddleware
  ->
templates Jinja2 + routes JSON
```

### 5.2 Composants utilises

Le prototype repose sur :

- `FastAPI`
- `Starlette SessionMiddleware`
- `Jinja2`
- `itsdangerous`
- `python-multipart`
- `uvicorn`
- verification de mot de passe via `hashlib.scrypt`

Sources applicatives :

- `auth_prototype/app/main.py`
- `auth_prototype/app/config.py`
- `auth_prototype/app/security.py`

### 5.3 Pourquoi cette architecture

Le choix retenu pour cette phase est volontairement simple :

- pas de conteneur ;
- pas de reverse proxy dans un premier temps ;
- pas de base de donnees utilisateur ;
- pas de provider d'identite externe.

But :

- aller vite ;
- valider la couche serveur ;
- verifier le comportement du login et des cookies sur une vraie VM ;
- preparer ensuite un passage propre vers `systemd`, TLS et OIDC.

## 6. Prototype Auth actuellement deploye

### 6.1 Nature du prototype

Le prototype est une application web `FastAPI` server-rendered qui valide :

- le flux de login operateur ;
- la creation d'une session ;
- la protection de pages HTML ;
- la protection d'endpoints API ;
- un premier RBAC simple.

### 6.2 Endpoints disponibles

Endpoints operationnels :

- `GET /healthz`
- `GET /auth/login`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /app`
- `GET /admin`
- `GET /api/me`
- `GET /api/admin/audit`

### 6.3 Comptes de demonstration

Comptes actuellement presents dans le code :

- `operator / operator123!`
- `admin / admin123!`

Usage :

- `operator` permet de tester le dashboard protege et `GET /api/me`
- `admin` permet de tester les routes reservees admin

Note :

ces comptes existent uniquement pour les tests internes du prototype. Ils ne constituent pas une solution de production.

## 7. Mecanisme d'authentification actuel

### 7.1 Principe general

Le systeme actuel n'utilise pas encore Keycloak ni OIDC.

Il fonctionne ainsi :

1. l'utilisateur ouvre `/auth/login`
2. il soumet un `username` et un `password`
3. le backend verifie les credentials contre les comptes demo locaux
4. si le login reussit, une session est creee dans le cookie signe
5. les routes protegees lisent cette session a chaque requete

### 7.2 Session

La session est geree par `SessionMiddleware`.

Configuration actuelle :

- cookie de session nomme `control_plane_session`
- `SameSite=lax`
- `Secure=false` tant que l'app reste en HTTP simple
- TTL de session : `28800` secondes

### 7.3 Mot de passe

Les mots de passe des comptes demo sont verifies via :

- `hashlib.scrypt`
- `hmac.compare_digest`

But :

- eviter les comparaisons naives ;
- simuler une vraie verification de secret ;
- rester sans dependance crypto additionnelle.

### 7.4 RBAC

Le RBAC actuel expose deux niveaux :

- `operator`
- `admin`

Comportement :

- `operator` peut acceder a `/app` et `/api/me`
- `admin` peut acceder a `/admin` et `/api/admin/audit`

## 8. Deploiement effectue aujourd'hui sur la VM

### 8.1 Installation systeme realisee

Sur la VM, les prerequis suivants ont ete installes :

- `python3`
- `python3-venv`
- `python3-pip`
- `git`

Le retour d'installation montre que la pile Python systeme et les dependances de build sont presentes.

### 8.2 Arborescence de deploiement retenue

Arborescence runtime actuelle :

```text
/opt/control-panel/control_plane
/etc/control-panel/auth-prototype.env
/etc/systemd/system/control-panel-auth.service
```

### 8.3 Environnement virtuel

Un venv Python a ete cree dans :

```text
/opt/control-panel/control_plane/.venv
```

Le venv contient maintenant les dependances runtime du prototype.

### 8.4 Dependances installees

Requirements installes :

- `fastapi`
- `uvicorn[standard]`
- `jinja2`
- `python-multipart`
- `itsdangerous`

### 8.5 Configuration d'environnement

Le fichier de configuration runtime est :

```text
/etc/control-panel/auth-prototype.env
```

Etat valide au 2026-03-26 :

- `AUTH_PROTO_APP_NAME` correctement quote ;
- `AUTH_PROTO_SESSION_SECRET` defini ;
- `AUTH_PROTO_SESSION_COOKIE=control_plane_session`
- `AUTH_PROTO_SECURE_COOKIES=false`
- `AUTH_PROTO_SAMESITE=lax`
- `AUTH_PROTO_SESSION_TTL_SECONDS=28800`

Important :

le secret de session est configure sur la VM mais ne doit pas etre committe dans le repo.

### 8.6 Detail important rencontre pendant le deploiement

Une anomalie a ete rencontree lors du chargement de l'env :

- `AUTH_PROTO_APP_NAME=Control Plane Auth Prototype`

Sans guillemets, cette variable cassait le chargement shell et provoquait l'erreur :

```text
Plane: command not found
```

Resolution appliquee :

```env
AUTH_PROTO_APP_NAME="Control Plane Auth Prototype"
```

Le modele d'env du repo a ete corrige pour refleter cette exigence.

## 9. Mode de lancement actuel

### 9.1 Lancement manuel valide

Le lancement manuel suivant a ete teste avec succes :

```bash
cd /opt/control-panel/control_plane
. .venv/bin/activate
set -a
source /etc/control-panel/auth-prototype.env
set +a
python -m uvicorn auth_prototype.app.main:app --host 0.0.0.0 --port 8000
```

Resultat :

- serveur demarre ;
- startup FastAPI OK ;
- endpoint `/healthz` repond.

### 9.2 Service systemd mis en place

Le prototype est maintenant egalement lance via `systemd`.

Service :

```text
control-panel-auth.service
```

Etat atteint :

- service installe ;
- `daemon-reload` effectue ;
- service `enabled` ;
- service `started` ;
- service `active (running)`.

### 9.3 Configuration du service

Le service `systemd` utilise :

- `User=ubuntu`
- `WorkingDirectory=/opt/control-panel/control_plane`
- `EnvironmentFile=/etc/control-panel/auth-prototype.env`
- `ExecStart=/opt/control-panel/control_plane/.venv/bin/python -m uvicorn auth_prototype.app.main:app --host 0.0.0.0 --port 8000`
- `Restart=always`

But :

- garder l'application vivante apres deconnexion SSH ;
- permettre un restart simple ;
- poser une premiere base d'exploitation.

## 10. Verifications fonctionnelles deja passees

### 10.1 Healthcheck

Le endpoint suivant a ete valide :

```text
http://51.15.115.203:8000/healthz
```

Reponse observee :

```json
{"status":"ok"}
```

### 10.2 Page de login

Le endpoint suivant a ete valide :

```text
http://51.15.115.203:8000/auth/login
```

Resultat :

- la page de login repond ;
- le serveur journalise correctement la requete ;
- la couche HTML serveur fonctionne sur la VM.

### 10.3 Observabilite basique

Verification d'exploitation deja validee :

- `systemctl status control-panel-auth`
- `journalctl -u control-panel-auth -f`
- `curl http://127.0.0.1:8000/healthz`

## 11. Acces reel depuis l'exterieur

### 11.1 URL actuelle de test

URL de test actuelle :

```text
http://51.15.115.203:8000/auth/login
```

### 11.2 Restriction d'acces

Cette URL n'est pas accessible publiquement a tout Internet.

Elle est accessible uniquement depuis :

- le VPN WireGuard ;
- le CIDR d'administration ;
- ou toute autre IP explicitement ajoutee au security group.

### 11.3 Consequence pour les tests avec le chef

Pour que le chef teste l'application, une des conditions suivantes doit etre remplie :

1. il est connecte au VPN WireGuard ;
2. son IP publique est explicitement ouverte dans le security group ;
3. une couche d'acces plus propre est ajoutee plus tard via HTTPS et reverse proxy.

Recommendation immediate :

pour un test interne controle, le meilleur choix est le passage par WireGuard.

## 12. Partie infra deployee versus partie applicative

### 12.1 Ce que gere l'infrastructure

Terraform et l'infra actuelle gerent :

- la VM ;
- l'IP ;
- le volume ;
- le security group ;
- le private network ;
- l'acces SSH controle ;
- l'ouverture controlee du port `8000`.

### 12.2 Ce que gere la VM runtime

La VM runtime gere :

- l'installation de Python ;
- le venv ;
- le fichier `.env` ;
- le service `systemd` ;
- le lancement de `uvicorn`.

### 12.3 Ce que gere l'application

L'application gere :

- le formulaire de login ;
- la verification de credentials ;
- la creation de session ;
- la lecture de session ;
- le RBAC ;
- les pages et APIs protegees.

## 13. Ce qu'on a choisi de ne pas faire aujourd'hui

Pour cette phase, les decisions suivantes ont ete prises :

- ne pas utiliser Docker ;
- ne pas introduire de reverse proxy tout de suite ;
- ne pas brancher Keycloak ;
- ne pas introduire PostgreSQL pour les utilisateurs ;
- ne pas faire de CI/CD de deploiement ;
- ne pas exposer l'application au monde entier.

Justification :

- minimiser la complexite ;
- valider d'abord le comportement du prototype sur serveur ;
- decouper proprement les taches entre infra, runtime et application.

## 14. Limites actuelles

### 14.1 Limites securite

Le prototype reste un prototype.

Limites connues :

- comptes demo en dur ;
- pas de CSRF dedie ;
- pas de MFA ;
- pas de SSO ;
- pas de base utilisateurs ;
- pas de rotation de secrets automatisee ;
- application servie en HTTP simple ;
- cookies non `Secure` tant qu'on reste sans TLS.

### 14.2 Limites d'exploitabilite

Malgre `systemd`, il manque encore :

- reverse proxy `Caddy` ou `Nginx` ;
- HTTPS ;
- journaux applicatifs plus structures ;
- supervision dediee ;
- pipeline de deploiement ;
- procedure d'upgrade du code plus industrialisee.

### 14.3 Limites produit

Le systeme actuel ne represente pas encore le futur control panel final.

Il ne valide que :

- le socle serveur ;
- le flux d'authentification de base ;
- la persistance d'un service web sur VM.

## 15. Livrables techniques produits aujourd'hui

### 15.1 Documentation

Documents disponibles :

- `auth_prototype/PRD_AUTHENTIFICATION.md`
- `auth_prototype/deploy/README_VM_DEPLOYMENT.md`
- `auth_prototype/PRD_ETAT_ACTUEL_VM_DEV1_S_2026-03-26.md`

### 15.2 Fichiers de deploiement

Fichiers de support disponibles :

- `auth_prototype/deploy/auth-prototype.env.example`
- `auth_prototype/deploy/control-panel-auth.service`
- `auth_prototype/deploy/Caddyfile.example`

### 15.3 Artefacts runtime presents sur la VM

Artefacts runtime attendus sur la VM :

- `/opt/control-panel/control_plane`
- `/opt/control-panel/control_plane/.venv`
- `/etc/control-panel/auth-prototype.env`
- `/etc/systemd/system/control-panel-auth.service`

## 16. Ce qui reste a faire

### 16.1 Court terme

Prochaines etapes recommandees :

1. valider un test complet de login avec un utilisateur de demonstration ;
2. verifier l'acces du chef via WireGuard ou ouverture IP temp ;
3. confirmer le comportement de `/app`, `/admin`, `/api/me`, `/api/admin/audit`.

### 16.2 Moyen terme

Prochaines etapes techniques :

1. ajouter `Caddy` ou `Nginx` ;
2. passer FastAPI en ecoute locale `127.0.0.1:8000` ;
3. activer TLS ;
4. passer `AUTH_PROTO_SECURE_COOKIES=true`.

### 16.3 Cible produit

Evolution cible :

1. remplacer les comptes demo par `Keycloak OIDC` ;
2. garder `FastAPI` pour l'application ;
3. utiliser `Vault` pour les secrets techniques ;
4. brancher les futures briques du control plane.

## 17. Decision immediate recommandee

La bonne decision a tres court terme est :

- garder ce prototype sans conteneur ;
- l'utiliser comme base de test serveur ;
- donner l'acces au chef via WireGuard si possible ;
- ne pas ouvrir davantage le port `8000` a Internet ;
- ajouter ensuite une couche `Caddy + HTTPS` si les tests doivent durer.

## 18. Conclusion

Au 2026-03-26, un jalon important a ete atteint :

- la VM de test existe ;
- l'application Auth est deployee ;
- le runtime Python est installe ;
- le service web est persistent via `systemd` ;
- les endpoints de base repondent ;
- l'environnement est pret pour un test humain reel.

Le systeme n'est pas encore un service production, mais il est maintenant suffisamment mature pour :

- une demonstration interne controlee ;
- une validation fonctionnelle du flux Auth ;
- la preparation du prochain palier technique : VPN utilisateur, reverse proxy, TLS, puis OIDC.
