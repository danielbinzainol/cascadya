# ansible-vault

Playbook Ansible dedie a la VM `vault-DEV1-S` pour heberger un Keycloak partage sans casser le Vault deja en place.

## Hypothese de depart

La cartographie relevee sur la VM Vault le `2026-04-15` montre :

- `Vault` natif actif sur `0.0.0.0:8200` et `*:8201`
- `nginx` actif sur `80/443`
- `nginx` publie deja `https://secrets.cascadya.com` vers `http://127.0.0.1:8200`
- Docker est present mais n'heberge aujourd'hui que `cadvisor`
- la VM a pour IP privee `10.42.2.4`

Ce repo part donc d'une cible prudente :

- `Vault` reste en place et n'est pas modifie
- `Keycloak` et `postgres-keycloak` sont ajoutes dans un scope isole
- `auth.cascadya.internal` est d'abord publie par un vhost dedie sur `nginx`
- le backchannel applicatif peut pointer en phase 1 vers `http://10.42.2.4:8081`

Le role est structure pour pouvoir basculer plus tard vers `Traefik`, mais le mode par defaut reste `nginx` parce que c'est ce qui colle a la cartographie reelle.

## Structure

- `playbooks/vault_keycloak.yml` : point d'entree principal
- `roles/vault_vm_keycloak` : role de deploiement Keycloak
- `inventory/hosts.example.yml` : inventaire d'exemple
- `inventory/group_vars/vault_vm.example.yml` : variables d'exemple a copier puis completer hors Git
- `docs/KEYCLOAK_VAULT_VM_GUIDE.md` : guide d'integration et hypotheses initiales
- `docs/CURRENT_STATE_PRD.md` : etat reel de `vault-DEV1-S` apres migration
- `docs/PORTAL_HUB_MVP_PRD.md` : PRD MVP pour un portail d'entree applicatif apres login Keycloak
- `docs/PORTAL_KEYCLOAK_CHECKLIST_PRD.md` : checklist Keycloak pour finaliser les roles et l'autorisation du portail
- `docs/PORTAL_POINT_ENTREE_ADMIN_PRD.md` : trajectoire cible `portal first` avec surface admin migree depuis le Control Panel
- `docs/PORTAL_PHASE1_RUNBOOK.md` : runbook d'execution pour completer et valider la phase 1 du portail

## Mise en route

1. Copier `inventory/hosts.example.yml` en `inventory/hosts.yml`
2. Copier `inventory/group_vars/vault_vm.example.yml` en `inventory/group_vars/vault_vm.yml`
3. Remplir les secrets hors Git
4. Choisir la strategie de migration :
   - `realm import` si environnement jetable ou peu critique
   - `restore DB` si les `sub` / `keycloak_uuid` doivent rester strictement stables
5. Lancer le playbook :

```bash
ansible-playbook playbooks/vault_keycloak.yml
```

## Points d'attention

- Ne pas faire pointer `auth.cascadya.internal` vers la VM Vault tant que le vhost `auth.cascadya.internal` n'existe pas. Sinon on peut presenter l'UI Vault a la place de Keycloak.
- Ne pas supprimer `nginx` sur Vault sans avoir remplace `secrets.cascadya.com`, car il sert aujourd'hui reellement de frontal TLS a Vault.
- Ne pas committer les secrets Keycloak, PostgreSQL ou certificats dans Git.
