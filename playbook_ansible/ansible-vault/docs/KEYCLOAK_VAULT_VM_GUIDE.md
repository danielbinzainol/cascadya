# Guide d'integration Keycloak sur la VM Vault

## 1. Ce que la cartographie impose

La cartographie relevee sur `vault-DEV1-S` le `2026-04-15` impose les garde-fous suivants :

- `Vault` tourne deja en natif sur `8200/8201`
- `nginx` tourne deja sur `80/443`
- `nginx` publie deja `https://secrets.cascadya.com` vers `Vault`
- Docker est deja installe mais ne porte pas encore `Keycloak`
- la VM Vault est joignable en prive sur `10.42.2.4`

Conclusion pratique :

- en phase 1, on ajoute `Keycloak` sans toucher a `Vault`
- on publie `auth.cascadya.internal` via un nouveau vhost `nginx`
- on fait pointer le backchannel du Control Panel vers `http://10.42.2.4:8081`
- on ne deplace pas `secrets.cascadya.com` dans ce lot

## 2. Ce que deploie le role

Le role `vault_vm_keycloak` pose :

- `postgres-keycloak` en conteneur
- `keycloak` en conteneur
- un runtime dedie sous `/opt/keycloak-vault`
- un vhost `nginx` dedie a `auth.cascadya.internal`
- un certificat auto-signe par defaut pour rester coherent avec l'existant `.internal`

Le role ne modifie pas :

- le service `vault`
- le vhost `secrets.cascadya.com`
- le DNS interne
- les variables du Control Panel

## 3. Choisir la strategie de migration

### Option A - Import de realm

A utiliser si l'environnement est encore leger ou si la preservation stricte des `sub` n'est pas critique.

Dans ce cas :

- `vault_vm_keycloak_realm_import_enabled: true`
- le role genere `realm.json`
- Keycloak importe les clients au demarrage

### Option B - Restauration DB

A utiliser si vous devez preserver les `sub` / `keycloak_uuid` existants.

Dans ce cas :

- `vault_vm_keycloak_realm_import_enabled: false`
- restaurer une sauvegarde de `postgres-keycloak` dans le conteneur cible
- laisser Keycloak relire l'etat restaure
- le role peut ensuite synchroniser les clients declares dans `vault_vm_keycloak_clients`
  et les roles declares dans `vault_vm_keycloak_realm_roles`
  via l'API d'administration, sans reimporter tout le realm

Cette option est la bonne si le Control Panel a deja des utilisateurs relies a `keycloak_uuid`.

## 4. Variables a preparer

Copier :

- `inventory/hosts.example.yml` -> `inventory/hosts.yml`
- `inventory/group_vars/vault_vm.example.yml` -> `inventory/group_vars/vault_vm.yml`

Puis renseigner au minimum :

- `vault_vm_keycloak_admin_username`
- `vault_vm_keycloak_admin_password`
- `vault_vm_keycloak_db_password`
- `vault_vm_keycloak_clients[*].client_secret`
- `vault_vm_keycloak_realm_roles`

## 5. Deploiement

Lancer :

```bash
ansible-playbook playbooks/vault_keycloak.yml
```

Effets attendus :

- `postgres-keycloak` et `keycloak` demarrent
- Keycloak ecoute en local sur `127.0.0.1:8081`
- `nginx` publie `auth.cascadya.internal`

## 6. Validations a faire apres run

Sur la VM Vault :

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
curl -sS http://127.0.0.1:8081/realms/cascadya-corp/.well-known/openid-configuration
curl -skH 'Host: auth.cascadya.internal' https://127.0.0.1/realms/cascadya-corp/.well-known/openid-configuration
sudo nginx -t
```

Depuis une VM du VPC :

```bash
curl -sS http://10.42.2.4:8081/realms/cascadya-corp/.well-known/openid-configuration
```

## 7. Recablage du Control Panel

Pour la phase 1, garder l'issuer public et basculer le backchannel sur l'IP privee Vault :

```env
AUTH_PROTO_OIDC_ISSUER_URL=https://auth.cascadya.internal/realms/cascadya-corp
AUTH_PROTO_OIDC_DISCOVERY_URL=http://10.42.2.4:8081/realms/cascadya-corp/.well-known/openid-configuration
AUTH_PROTO_OIDC_INTERNAL_BASE_URL=http://10.42.2.4:8081
AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL=http://10.42.2.4:8081
```

Ce choix suit exactement la recommandation issue de la cartographie : limiter le risque en gardant un backchannel prive simple.

## 8. Bascule DNS

Ne changer `auth.cascadya.internal` que lorsque :

- le vhost `nginx` de Vault est en place
- le realm repond bien sur `127.0.0.1` et `10.42.2.4`
- le certificat choisi est present

Sinon, la VM Vault peut presenter autre chose que Keycloak sous ce hostname.

## 9. Et Traefik ensuite ?

Le role accepte deja la variable `vault_vm_keycloak_proxy_mode`, mais le scaffold bloque volontairement `traefik` en phase 1.

Raison :

- `nginx` sert deja `secrets.cascadya.com`
- retirer `nginx` sans migration prealable casserait l'acces TLS a `Vault`

Le bon ordre si vous voulez uniformiser ensuite :

1. migrer `secrets.cascadya.com` vers `Traefik`
2. verifier que `Vault` reste servi correctement
3. remplacer le vhost `nginx` de `auth.cascadya.internal`
4. seulement ensuite envisager la suppression de `nginx`
