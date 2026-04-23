# Guide VM - Traefik Docker sur la meme VM

## Hypothese retenue

Ce guide part de l'hypothese suivante :

- le prototype Auth `FastAPI` tourne sur la meme VM que Traefik ;
- `FastAPI` reste hors Docker et continue a tourner via `systemd` ;
- Traefik tourne dans Docker sur la meme VM ;
- l'acces web doit etre reserve au reseau WireGuard et a l'IP d'administration ;
- le nom de service est interne, ici `control-panel.cascadya.internal` ;
- le certificat TLS est fourni via un certificat interne ou PKI interne, pas via Let's Encrypt.

Cette approche est la plus simple si tu veux :

- rester WireGuard-only ;
- ne pas exposer 80/443 au monde entier ;
- garder un nom interne ;
- separer proprement le proxy et l'application.

## Architecture cible

```text
Client WireGuard
  -> https://control-panel.cascadya.internal
  -> Traefik (Docker, host network)
  -> ipAllowList
  -> FastAPI sur 127.0.0.1:8000
```

## Prerequis

- le prototype Auth fonctionne deja sur la VM ;
- le service `control-panel-auth` existe deja ;
- Docker peut etre installe sur la VM ;
- le nom interne choisi doit resoudre vers la VM pour les clients WireGuard ;
- un certificat et une cle privee TLS existent pour ce nom interne.

## Etape 1 - Installer Docker

Sur la VM :

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu
```

Reconnecte ensuite la session SSH ou lance :

```bash
newgrp docker
```

## Etape 2 - Passer FastAPI en mode "behind Traefik"

Copie le fichier systemd adapte :

```bash
sudo cp /opt/control-panel/control_plane/auth_prototype/deploy/control-panel-auth-behind-traefik.service /etc/systemd/system/control-panel-auth.service
```

Prepare le fichier env adapte :

```bash
sudo cp /opt/control-panel/control_plane/auth_prototype/deploy/auth-prototype.traefik.env.example /etc/control-panel/auth-prototype.env
sudo nano /etc/control-panel/auth-prototype.env
```

Adapte au minimum :

- `AUTH_PROTO_SESSION_SECRET`
- `AUTH_PROTO_TRUSTED_HOSTS`

Exemple :

```env
AUTH_PROTO_APP_NAME="Control Plane Auth Prototype"
AUTH_PROTO_SESSION_SECRET="replace-with-a-long-random-secret"
AUTH_PROTO_SESSION_COOKIE=control_plane_session
AUTH_PROTO_SECURE_COOKIES=true
AUTH_PROTO_SAMESITE=lax
AUTH_PROTO_SESSION_TTL_SECONDS=28800
AUTH_PROTO_TRUSTED_HOSTS=control-panel.cascadya.internal,127.0.0.1,localhost
```

Recharge puis redemarre :

```bash
sudo systemctl daemon-reload
sudo systemctl restart control-panel-auth
sudo systemctl status control-panel-auth
curl http://127.0.0.1:8000/healthz
```

Resultat attendu :

- FastAPI ne repond que localement ;
- `curl http://127.0.0.1:8000/healthz` renvoie `{"status":"ok"}` ;
- l'IP publique de la VM ne doit plus servir pour joindre directement l'app.

## Etape 3 - Preparer l'arborescence Traefik

Sur la VM :

```bash
sudo mkdir -p /opt/traefik-control-panel/dynamic
sudo mkdir -p /opt/traefik-control-panel/certs
sudo mkdir -p /opt/traefik-control-panel/logs
sudo chown -R ubuntu:ubuntu /opt/traefik-control-panel
```

Copie les fichiers :

```bash
cp /opt/control-panel/control_plane/auth_prototype/deploy/traefik-docker/docker-compose.yml /opt/traefik-control-panel/
cp /opt/control-panel/control_plane/auth_prototype/deploy/traefik-docker/traefik.yml /opt/traefik-control-panel/
cp /opt/control-panel/control_plane/auth_prototype/deploy/traefik-docker/dynamic/control-panel.yml /opt/traefik-control-panel/dynamic/
```

## Etape 4 - Installer le certificat TLS interne

Le guide suppose un certificat interne.

Depose sur la VM :

```text
/opt/traefik-control-panel/certs/control-panel.cascadya.internal.crt
/opt/traefik-control-panel/certs/control-panel.cascadya.internal.key
```

Verifie les permissions :

```bash
chmod 600 /opt/traefik-control-panel/certs/control-panel.cascadya.internal.key
chmod 644 /opt/traefik-control-panel/certs/control-panel.cascadya.internal.crt
```

Si tu utilises Vault PKI ou une PKI interne, c'est ici que tu injectes le certificat emis.

## Etape 5 - Adapter le nom interne si necessaire

Par defaut, les fichiers utilisent :

```text
control-panel.cascadya.internal
```

Si tu choisis un autre FQDN interne, il faut modifier :

- `/etc/control-panel/auth-prototype.env`
- `/opt/traefik-control-panel/dynamic/control-panel.yml`

## Etape 6 - Demarrer Traefik

Sur la VM :

```bash
cd /opt/traefik-control-panel
docker compose up -d
docker compose ps
docker compose logs -f
```

## Etape 7 - Verifier la resolution DNS interne

Les clients WireGuard doivent resoudre le nom interne vers la VM.

Deux options :

### Option A - DNS interne / split DNS

Le DNS interne renvoie l'IP de la VM pour :

```text
control-panel.cascadya.internal
```

### Option B - test rapide via fichier hosts

Sur le poste client :

```text
51.15.115.203  control-panel.cascadya.internal
```

Cette option est pratique pour une validation rapide.

## Etape 8 - Verifier le filtrage WireGuard

Le middleware Traefik applique :

- `10.8.0.0/24`
- `195.68.106.70/32`

Resultat attendu :

- VPN ON -> page de login accessible
- VPN OFF -> `403 Forbidden`

## Etape 9 - Ajustements infra indispensables

Ces points sont hors VM mais indispensables :

- fermer l'exposition publique directe de `8000`
- ouvrir `443` uniquement aux CIDR autorises
- si tu gardes aussi l'IP d'administration, la conserver dans le SG

Important :

comme Traefik tourne en `network_mode: host`, il utilise directement la pile reseau de la VM.
Le filtrage principal doit donc rester au niveau du Security Group Scaleway.

## Etape 10 - Tests de validation

### Test local VM

```bash
curl http://127.0.0.1:8000/healthz
curl -k https://127.0.0.1
```

### Test client VPN

Depuis un client WireGuard :

- ouvrir `https://control-panel.cascadya.internal/auth/login`
- verifier la page de login
- tester `operator / operator123!`
- tester `admin / admin123!`

### Test hors VPN

Depuis une connexion non VPN :

- verifier qu'un `403` est renvoye

## Resultat final attendu

- Traefik tourne dans Docker sur la meme VM
- FastAPI tourne via `systemd`
- FastAPI ecoute seulement sur `127.0.0.1:8000`
- Traefik termine TLS
- l'acces est limite au reseau WireGuard
- le nom interne fonctionne pour les clients autorises

## Evolution ensuite

Une fois cette etape validee, tu pourras :

- remplacer le certificat interne par un mecanisme de certif public si besoin ;
- ajouter un vrai DNS interne ;
- brancher Keycloak ;
- renforcer le monitoring et l'exploitation.
