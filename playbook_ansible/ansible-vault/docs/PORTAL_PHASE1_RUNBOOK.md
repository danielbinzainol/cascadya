# Runbook - Phase 1 portail Cascadya

Date de reference : `2026-04-16`

## 1. Objet

Ce runbook decrit comment completer et valider la phase 1 de migration et d'integration du portail :

- rendre `portal.cascadya.internal` vraiment utilisable
- ne toucher qu'a Keycloak sur `vault-DEV1-S`
- debloquer les cartes du portail via des `realm roles`
- valider le resultat sur un compte utilisateur reel

## 2. Ou executer quoi

### Sur `vault-DEV1-S`

A executer sur la VM Vault :

- verification du client `cascadya-portal-web`
- creation des `realm roles`
- affectation des roles a l'utilisateur de test

### Sur votre poste WSL dans ce repo

A executer depuis le repo `playbook_ansible/ansible-vault` :

- relance du playbook pour rendre persistants :
  - les `realm roles`
  - la configuration OIDC du client portail

### Dans le navigateur

A executer cote utilisateur :

- logout portail
- logout Keycloak si necessaire
- reconnexion a `https://portal.cascadya.internal`
- verification des cartes ouvertes

## 3. Commandes a lancer sur `vault-DEV1-S`

### 3.1 Ouvrir une session `kcadm`

```bash
export KC_ADMIN_USER='admin'
export KC_ADMIN_PASSWORD='<vault_vm_keycloak_admin_password>'
export KC_REALM='cascadya-corp'
export PORTAL_CLIENT_ID='cascadya-portal-web'
export TEST_USER_EMAIL='daniel.binzainol@cascadya.com'

docker exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://127.0.0.1:8080 \
  --realm master \
  --user "$KC_ADMIN_USER" \
  --password "$KC_ADMIN_PASSWORD"
```

### 3.2 Verifier le client portail

```bash
docker exec keycloak /opt/keycloak/bin/kcadm.sh get clients \
  -r "$KC_REALM" \
  -q clientId="$PORTAL_CLIENT_ID"
```

Verifier visuellement que :

- `redirectUris` contient `https://portal.cascadya.internal/auth/callback`
- `attributes.post.logout.redirect.uris` contient `https://portal.cascadya.internal/`
- `standardFlowEnabled` est a `true`

### 3.3 Creer les roles realm si absents

```bash
for role in \
  portal-access \
  portal-admin \
  control-panel-user \
  monitoring-user \
  grafana-user \
  wazuh-user \
  security-user
do
  docker exec keycloak /opt/keycloak/bin/kcadm.sh get "roles/$role" -r "$KC_REALM" >/dev/null 2>&1 || \
  docker exec keycloak /opt/keycloak/bin/kcadm.sh create roles -r "$KC_REALM" -s "name=$role"
done
```

### 3.4 Recuperer l'identifiant du compte de test

```bash
export TEST_USER_ID="$(
  docker exec keycloak /opt/keycloak/bin/kcadm.sh get users \
    -r "$KC_REALM" \
    -q email="$TEST_USER_EMAIL" \
    --fields id,email,username | \
  python3 -c "import sys, json; a=json.load(sys.stdin); print(a[0]['id'] if a else '')"
)"

printf '%s\n' "$TEST_USER_ID"
```

Si la commande ne renvoie rien, verifier l'email exact du compte dans Keycloak.

### 3.5 Test minimal

```bash
docker exec keycloak /opt/keycloak/bin/kcadm.sh add-roles \
  -r "$KC_REALM" \
  --uid "$TEST_USER_ID" \
  --rolename portal-access \
  --rolename control-panel-user \
  --rolename monitoring-user \
  --rolename grafana-user
```

Resultat attendu apres reconnexion :

- `Control Panel`
- `Features`
- `Grafana`
- `Mimir`

doivent etre ouverts.

### 3.6 Test "tout ouvert"

Si vous voulez un test rapide sans filtrage fin :

```bash
docker exec keycloak /opt/keycloak/bin/kcadm.sh add-roles \
  -r "$KC_REALM" \
  --uid "$TEST_USER_ID" \
  --rolename portal-admin
```

### 3.7 Verifier les roles reellement portes par l'utilisateur

```bash
docker exec keycloak /opt/keycloak/bin/kcadm.sh get \
  "users/$TEST_USER_ID/role-mappings/realm" \
  -r "$KC_REALM"
```

## 4. Rendre la phase 1 persistante via Ansible

Ce depot a ete aligne pour :

- synchroniser les `realm roles` declares dans `vault_vm_keycloak_realm_roles`
- garder le client `cascadya-portal-web`
- aligner le `post logout redirect URI` du portail sur `https://portal.cascadya.internal/`

Depuis WSL :

```bash
export WIN_ROOT='/mnt/c/Users/Daniel BIN ZAINOL/Desktop/GIT - Daniel'
export WSL_ROOT="$HOME/git/cascadya-project"

rsync -av --delete \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$WIN_ROOT/playbook_ansible/ansible-vault/" \
  "$WSL_ROOT/playbook_ansible/ansible-vault/"

cd "$WSL_ROOT/playbook_ansible/ansible-vault"

export ANSIBLE_CONFIG="$PWD/ansible.cfg"
export ANSIBLE_ROLES_PATH="$PWD/roles"

ansible-playbook \
  -i inventory/hosts.yml \
  playbooks/vault_keycloak.yml \
  --private-key ~/.ssh/id_ed25519 \
  -K -vv
```

## 5. Validation finale dans le navigateur

1. Se deconnecter du portail
2. Se deconnecter aussi de Keycloak si necessaire
3. Recharger `https://portal.cascadya.internal`
4. Se reconnecter

### Validation attendue en test minimal

- `Control Panel` est ouvert
- `Features` est ouvert
- `Grafana` est ouvert
- `Mimir` est ouvert
- `Wazuh` reste ferme
- `Keycloak Admin` reste ferme

### Validation attendue en test "tout ouvert"

- toutes les cartes du MVP sont ouvertes

## 6. Etape suivante

Une fois la phase 1 validee :

- garder `portal-admin` reserve aux admins
- decider si les utilisateurs standards recoivent leurs roles par affectation directe ou via groupes
- implementer ensuite l'onglet admin portail en l'ouvrant seulement a `portal-admin`
