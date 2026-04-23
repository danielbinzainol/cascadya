# Guide de deploiement VM - Auth Prototype

## Objectif

Ce guide explique comment deployer le prototype `FastAPI` d'authentification sur la VM `control-panel-DEV1-S` sans conteneur, avec un mode de run simple et un mode de run propre via `systemd`.

Le choix recommande pour cette phase est :

- pas de Docker pour l'instant ;
- `uvicorn` sur la VM ;
- `systemd` pour garder le service vivant ;
- `Caddy` optionnel ensuite pour HTTPS.

## Architecture cible de cette etape

### Phase 1 - test simple

```text
Navigateur
  -> http://51.15.115.203:8000
  -> Uvicorn / FastAPI
```

### Phase 2 - test propre

```text
Navigateur
  -> Caddy :443
  -> FastAPI sur 127.0.0.1:8000
```

## Hypotheses

- VM Ubuntu accessible en SSH
- port `8000` deja autorise dans le security group depuis VPN + CIDR d'administration
- code local disponible dans :
  `C:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\python script\control_plane`
- user SSH suppose : `ubuntu`

## Structure conseillee sur la VM

```text
/opt/control-panel/
  control_plane/                 # copie du repo
  logs/                          # optionnel

/etc/control-panel/
  auth-prototype.env             # variables d'environnement

/etc/systemd/system/
  control-panel-auth.service
```

## Etape 1 - Se connecter a la VM

Depuis ton poste :

```bash
ssh ubuntu@51.15.115.203
```

## Etape 2 - Installer les prerequis

Sur la VM :

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

## Etape 3 - Creer les repertoires

```bash
sudo mkdir -p /opt/control-panel
sudo mkdir -p /etc/control-panel
```

## Etape 4 - Copier le code sur la VM

### Option A - avec `scp`

Depuis ton poste Windows, dans un terminal qui voit `scp` :

```bash
scp -r "C:/Users/Daniel BIN ZAINOL/Desktop/GIT - Daniel/python script/control_plane" ubuntu@51.15.115.203:/tmp/control_plane
```

Puis sur la VM :

```bash
sudo rm -rf /opt/control-panel/control_plane
sudo mv /tmp/control_plane /opt/control-panel/control_plane
```

### Option B - avec Git

Si le repo est accessible depuis la VM :

```bash
cd /opt/control-panel
sudo git clone <URL_DU_REPO> control_plane
```

## Etape 5 - Creer le venv et installer les dependances

Sur la VM :

```bash
cd /opt/control-panel/control_plane
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r auth_prototype/requirements.txt
```

## Etape 6 - Definir les variables d'environnement

Copie le modele fourni dans :

- `auth_prototype/deploy/auth-prototype.env.example`

Sur la VM :

```bash
sudo cp /opt/control-panel/control_plane/auth_prototype/deploy/auth-prototype.env.example /etc/control-panel/auth-prototype.env
sudo nano /etc/control-panel/auth-prototype.env
```

Valeurs minimales a fixer :

- `AUTH_PROTO_SESSION_SECRET`
- `AUTH_PROTO_SECURE_COOKIES=false` tant que tu restes en HTTP simple
- si une variable contient des espaces, garde des guillemets
- exemple valide :
  `AUTH_PROTO_APP_NAME="Control Plane Auth Prototype"`

Pour generer un secret correct :

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

## Etape 7 - Premier test manuel sans systemd

Sur la VM :

```bash
cd /opt/control-panel/control_plane
. .venv/bin/activate
set -a
source /etc/control-panel/auth-prototype.env
set +a
python -m uvicorn auth_prototype.app.main:app --host 0.0.0.0 --port 8000
```

Teste ensuite depuis ton poste :

- `http://51.15.115.203:8000/healthz`
- `http://51.15.115.203:8000/auth/login`

Comptes de demo actuels :

- `operator / operator123!`
- `admin / admin123!`

## Etape 8 - Installer le service systemd

Copie le template fourni :

- `auth_prototype/deploy/control-panel-auth.service`

Sur la VM :

```bash
sudo cp /opt/control-panel/control_plane/auth_prototype/deploy/control-panel-auth.service /etc/systemd/system/control-panel-auth.service
sudo systemctl daemon-reload
sudo systemctl enable control-panel-auth
sudo systemctl start control-panel-auth
```

Verifier :

```bash
sudo systemctl status control-panel-auth
sudo journalctl -u control-panel-auth -f
```

## Etape 9 - Verification fonctionnelle

Verifier les points suivants :

- `GET /healthz` retourne `{"status":"ok"}`
- login `operator`
- acces a `/app`
- acces a `/api/me`
- refus `403` sur `/admin` pour `operator`
- login `admin`
- acces a `/admin`
- acces a `/api/admin/audit`
- logout

## Etape 10 - Option recommandee ensuite : reverse proxy

Quand le test HTTP simple est valide, ajoute `Caddy`.

Avantages :

- HTTPS/TLS
- headers propres
- cookies `Secure`
- FastAPI n'est plus expose directement

Le fichier modele est :

- `auth_prototype/deploy/Caddyfile.example`

Dans ce mode :

- FastAPI ecoute sur `127.0.0.1:8000`
- Caddy expose `443`
- `AUTH_PROTO_SECURE_COOKIES=true`

## Separation des responsabilites

### Terraform

Gere uniquement :

- VM
- IP
- Security Group
- Private network
- volume

Ne doit pas gerer :

- `pip install`
- `uvicorn`
- le code applicatif
- les secrets applicatifs

### VM runtime

Gere :

- Python
- venv
- fichier env
- systemd
- reverse proxy

### Application

Gere :

- login
- session
- RBAC
- templates
- endpoints

## Quand utiliser des conteneurs ?

Pas maintenant.

Utilise des conteneurs plus tard si tu veux :

- plusieurs services sur la meme VM
- un deploiement plus standardise
- CI/CD basee sur image
- separer proprement `auth app` / `proxy`

Pour cette phase, le plus simple et le plus utile est :

- FastAPI natif
- systemd
- Caddy ensuite

## Check-list finale

- VM accessible en SSH
- repo copie sur la VM
- venv cree
- requirements installes
- `AUTH_PROTO_SESSION_SECRET` renseigne
- service `control-panel-auth` actif
- `8000` joignable depuis VPN/CIDR admin
- login operateur valide
- RBAC admin valide

## Prochaine etape apres validation

Une fois ce prototype valide sur VM :

1. ajouter `systemd` si ce n'est pas deja fait ;
2. ajouter `Caddy` ;
3. passer en HTTPS ;
4. activer `AUTH_PROTO_SECURE_COOKIES=true` ;
5. preparer l'integration `Keycloak OIDC`.
