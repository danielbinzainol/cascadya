# Auth Prototype

Prototype web autonome pour tester la partie authentification du futur control panel.

## Ce que le prototype couvre

- Login operateur via formulaire web
- Session cookie signee
- Logout
- Protection de routes HTML et JSON
- Controle d'acces par role (`operator`, `admin`)
- Structure simple pour etre remplacee ensuite par Keycloak OIDC
- Socle RBAC PostgreSQL du lot 1

## Installation

Depuis la racine du repo :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r auth_prototype\requirements.txt
alembic -c auth_prototype\alembic.ini upgrade head
python -m auth_prototype.scripts.seed_rbac
python -m uvicorn auth_prototype.app.main:app --reload
```

Ensuite ouvre :

- `http://127.0.0.1:8000/auth/login`

## Comptes de demo

- `operator` / `operator123!`
- `admin` / `admin123!`

## Variables utiles

```powershell
$env:AUTH_PROTO_SESSION_SECRET="change-me"
$env:AUTH_PROTO_SECURE_COOKIES="false"
$env:AUTH_PROTO_SAMESITE="lax"
$env:AUTH_PROTO_DATABASE_URL="sqlite+pysqlite:///./auth_prototype/control_panel_auth.db"
$env:AUTH_PROTO_DATABASE_ECHO="false"
```

Pour un acces via HTTPS plus tard, passe `AUTH_PROTO_SECURE_COOKIES=true`.

Pour tester PostgreSQL au lieu de SQLite, leve le conteneur dans [docker-compose.yml](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/deploy/postgres-fastapi/docker-compose.yml#L1) puis pointe `AUTH_PROTO_DATABASE_URL` vers `127.0.0.1:5433`.

## Endpoints utiles

- `GET /healthz`
- `GET /healthz/db`
- `GET /app`
- `GET /admin`
- `GET /api/me`
- `GET /api/admin/audit`
- `GET /api/admin/rbac/catalog`

## Limites volontaires

- Pas encore de Keycloak
- Pas encore de CSRF dedie
- Comptes de demo locaux toujours utilises pour la phase pre-Keycloak

Le but est de valider le flux UX, le mecanisme de protection des routes et le socle RBAC avant le branchement OIDC.
