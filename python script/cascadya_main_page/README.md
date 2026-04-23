# Cascadya Portal Hub MVP

Portail d'entree applicatif apres authentification Keycloak.

Le projet implemente un hub SSO leger conforme au PRD:

- `auth.cascadya.internal` reste reserve a l'identite
- le portail vit sur son propre DNS, typiquement `portal.cascadya.internal`
- chaque application garde son domaine natif
- le portail ne reverse-proxy pas les autres UIs

## Ce que livre ce MVP

- auth OIDC Keycloak avec redirection vers `/auth/callback`
- logout portail + tentative de logout RP-initiated cote IdP
- pages serveur:
  - `/`
  - `/operations`
  - `/monitoring`
  - `/security`
  - `/platform`
- cartes filtrees par roles / groupes exposes dans les claims Keycloak
- mode dev optionnel avec profils locaux pour valider l'UX sans IdP
- endpoints utilitaires:
  - `GET /api/healthz`
  - `GET /api/status`
  - `GET /api/me`

## Stack

- Python 3
- Flask
- templates Jinja
- CSS/JS statiques
- waitress pour servir l'app

Le choix reste volontairement simple pour un deploiement isole sur la VM `control-panel-DEV1-S`.

## Arborescence

- `app.py`: point d'entree local
- `portal_hub/config.py`: config `.env`
- `portal_hub/oidc.py`: discovery, token exchange, userinfo, logout
- `portal_hub/auth.py`: extraction des claims, roles, groupes et protections de session
- `portal_hub/catalog.py`: sections et cartes du portail
- `portal_hub/server.py`: routes Flask
- `portal_hub/templates/`: rendu HTML
- `portal_hub/static/`: styles et JS
- `tests/`: tests unitaires

## Documentation

- `docs/PRD_KEYCLOAK_PORTAL_ACCESS_CHECKLIST_2026-04-16.md`: checklist PRD pour finaliser la partie Keycloak sur Vault
- `docs/PORTAL_HUB_IMPLEMENTATION_NOTE_2026-04-16.md`: dossier technique sur ce qui a ete construit, pourquoi et comment
- `docs/PRD_PORTAL_POINT_ENTREE_UNIQUE_ET_SURFACE_ADMIN_2026-04-16.md`: PRD cible "portal first" pour la migration du Control Panel vers un role de microservice

## Lancement local

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Puis ouvrir:

```text
http://127.0.0.1:8788
```

## Variables importantes

- `PORTAL_OIDC_ENABLED=true`
- `PORTAL_OIDC_ISSUER_URL=https://auth.cascadya.internal/realms/cascadya-corp`
- `PORTAL_OIDC_CLIENT_ID=cascadya-portal-web`
- `PORTAL_OIDC_CLIENT_SECRET=...`
- `PORTAL_PUBLIC_BASE_URL=https://portal.cascadya.internal`
- `PORTAL_OIDC_VERIFY_TLS=false`
- `PORTAL_OIDC_CA_CERT_PATH=/path/to/ca.pem`
- `PORTAL_REQUIRED_TAGS=portal-access,portal-admin`

Note TLS:

- le PRD mentionne un certificat auto-signe sur `auth.cascadya.internal`
- le portail peut soit faire confiance a une CA via `PORTAL_OIDC_CA_CERT_PATH`
- soit desactiver temporairement la verification via `PORTAL_OIDC_VERIFY_TLS=false`

## Roles / groupes pris en charge

Le portail calcule les tags d'acces a partir de plusieurs emplacements de claims:

- `realm_access.roles`
- `resource_access.*.roles`
- `roles`
- `groups`
- `group_membership`

Les cartes sont ensuite filtrees avec un mapping simple.

Exemples utilises dans ce MVP:

- `portal-access`
- `portal-admin`
- `control-panel-user`
- `monitoring-user`
- `grafana-user`
- `wazuh-user`

## Tests

```powershell
python -m unittest discover -s tests
```

## Deploiement rapide vers la VM Control Panel

Depuis ton poste Windows, dans ce repo:

```powershell
cd "C:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\python script\cascadya_main_page"
.\scripts\deploy-live.ps1
```

Si tu as deja prepare un vrai `.env` local avec `PORTAL_SESSION_SECRET` et `PORTAL_OIDC_CLIENT_SECRET`, tu peux aussi le pousser sur la VM:

```powershell
.\scripts\deploy-live.ps1 -PushLocalEnv
```

Verification apres deploiement:

```powershell
.\scripts\check-live.ps1
```

Ce que fait le script:

- copie le repo vers `/opt/cascadya_portal_hub`
- cree ou reutilise `.venv`
- installe les dependances Python
- pose le service `systemd` `cascadya-portal-hub`
- pose la config Traefik dynamique pour `portal.cascadya.internal`
- genere un certificat auto-signe si necessaire
- redemarre le service et teste `http://127.0.0.1:8788/api/healthz`

Si tu preferes faire la pose a la main directement sur la VM, les templates sont dans:

- `deploy/cascadya-portal-hub.service.template`
- `deploy/cascadya-portal-hub.traefik.yml.template`
- `deploy/cascadya-portal-hub.env.template`

## Hypotheses du MVP

- les roles utiles sont exposes dans l'access token, l'id token ou `userinfo`
- `Mimir` doit pointer vers une vue Grafana pertinente par defaut, surchargeable via `PORTAL_URL_MIMIR`
- les cartes sensibles comme Wazuh Admin / Keycloak Admin peuvent rester masquees si le role manque
