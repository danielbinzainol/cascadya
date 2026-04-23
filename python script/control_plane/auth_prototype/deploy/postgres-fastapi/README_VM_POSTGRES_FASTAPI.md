# PostgreSQL FastAPI - Lot 1

## Objectif

Lever la base metier `postgres-fastapi` du lot 1 pour le prototype auth et le futur RBAC.

## Fichiers

- `docker-compose.yml`
- `postgres-fastapi.env.example`

## Installation sur la VM

Copier ce dossier sur la VM, puis :

```bash
sudo mkdir -p /opt/control-panel/postgres-fastapi
sudo chown -R ubuntu:ubuntu /opt/control-panel/postgres-fastapi
cp auth_prototype/deploy/postgres-fastapi/docker-compose.yml /opt/control-panel/postgres-fastapi/
cp auth_prototype/deploy/postgres-fastapi/postgres-fastapi.env.example /opt/control-panel/postgres-fastapi/postgres-fastapi.env
nano /opt/control-panel/postgres-fastapi/postgres-fastapi.env
cd /opt/control-panel/postgres-fastapi
docker compose up -d
docker compose ps
```

## Variables a recopier dans `/etc/control-panel/auth-prototype.env`

```env
AUTH_PROTO_DATABASE_URL=postgresql+psycopg://control_panel:change-me-before-vm-deploy@127.0.0.1:5433/control_panel
AUTH_PROTO_DATABASE_ECHO=false
```

## Migration et seed

Depuis `/opt/control-panel/control_plane` :

```bash
source .venv/bin/activate
set -a
source /etc/control-panel/auth-prototype.env
set +a
echo "$AUTH_PROTO_DATABASE_URL"
pip install -r auth_prototype/requirements.txt
alembic -c auth_prototype/alembic.ini upgrade head
python -m auth_prototype.scripts.seed_rbac
```

Important :

- `alembic` et le script de seed lisent `AUTH_PROTO_DATABASE_URL` depuis l'environnement shell
- sans `source /etc/control-panel/auth-prototype.env`, la commande retombe sur la base SQLite par defaut

## Verification

```bash
curl http://127.0.0.1:8000/healthz/db
```

Puis, une fois connecte en `admin` sur le prototype :

- `GET /api/admin/rbac/catalog`
