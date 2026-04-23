# Deploiement Keycloak pour le lot 2

Ce dossier prepare le socle Keycloak de la VM `control-panel-DEV1-S`.

## Contenu

- `docker-compose.yml`
  Lance PostgreSQL dedie a Keycloak et Keycloak lui-meme.
- `keycloak.env.example`
  Variables a recopier en `keycloak.env`.
- `realm-import/cascadya-corp-realm.json`
  Realm minimal avec le client OIDC `control-panel-web`.

## Etapes rapides sur la VM

```bash
sudo mkdir -p /opt/control-panel/keycloak
sudo chown -R ubuntu:ubuntu /opt/control-panel/keycloak
cp docker-compose.yml /opt/control-panel/keycloak/
cp keycloak.env.example /opt/control-panel/keycloak/keycloak.env
cp -r realm-import /opt/control-panel/keycloak/
```

Puis adapter :

- `KEYCLOAK_DB_PASSWORD`
- `KEYCLOAK_ADMIN_PASSWORD`
- le `secret` du client dans `realm-import/cascadya-corp-realm.json`

Ensuite :

```bash
cd /opt/control-panel/keycloak
docker compose up -d
docker compose ps
docker compose logs --tail=100
```

Le backchannel du control panel peut ensuite viser :

- `AUTH_PROTO_OIDC_ISSUER_URL=https://auth.cascadya.internal/realms/cascadya-corp`
- `AUTH_PROTO_OIDC_INTERNAL_BASE_URL=http://127.0.0.1:8081`
