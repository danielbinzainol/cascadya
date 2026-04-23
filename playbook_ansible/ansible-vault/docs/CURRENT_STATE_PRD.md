# CURRENT_STATE_PRD

## 1. Objet

Ce document decrit l'etat reel de la VM `vault-DEV1-S` apres la migration Keycloak finalisee le `2026-04-15`, puis consolidee le `2026-04-16` pour les clients OIDC du portail.

Il sert de reference d'exploitation et complete le guide d'integration historique.

## 2. Perimetre actuel de la VM Vault

La VM `vault-DEV1-S` porte desormais les briques suivantes :

- `Vault` natif, conserve en place, expose sur `8200/8201`
- `nginx` systeme, conserve en frontal TLS sur `80/443`
- `cadvisor` en conteneur Docker
- `postgres-keycloak` en conteneur Docker
- `keycloak` en conteneur Docker

Adresses utiles :

- IP privee Vault VM : `10.42.2.4`
- IP publique Vault VM : `51.15.36.65`
- runtime Keycloak : `/opt/keycloak-vault`

## 3. Exposition reseau en production actuelle

### Vault

- `Vault` reste publie via `nginx`
- hostname public conserve : `https://secrets.cascadya.com`
- ce flux n'a pas ete remanie par la migration Keycloak

### Keycloak partage

- hostname publie : `https://auth.cascadya.internal`
- terminaison TLS : `nginx`
- certificat actuel : auto-signe
- backend Keycloak : `127.0.0.1:8081 -> keycloak:8080`

Important :

- le endpoint de reference pour les applications est `https://auth.cascadya.internal`
- le HTTP local `127.0.0.1:8081` reste un endpoint technique de backend, pas l'URL d'integration recommandee pour les clients

## 4. Etat de la migration Keycloak

La migration a ete faite en mode `restore DB`, et non en mode `realm import`.

Consequences voulues :

- conservation des utilisateurs existants
- conservation des hash de mots de passe
- conservation des `sub` et des identifiants Keycloak historiques
- reprise du client `control-panel-web` depuis la base existante

Validation observee apres restauration :

- `user_entity`: `6`
- `credential`: `6`

Le realm actif attendu est :

- realm : `cascadya-corp`
- issuer : `https://auth.cascadya.internal/realms/cascadya-corp`

## 5. Etat des clients OIDC

### Client restaure par la DB

- `control-panel-web`

### Clients ajoutes apres restauration

- `cascadya-features-web`
- `grafana-monitoring`
- `cascadya-portal-web`

Les `client_secret` ont ete generes pendant la migration mais ne doivent pas etre stockes dans ce document.

Le role Ansible de la VM Vault sait desormais resynchroniser les clients OIDC declares apres un `restore DB`, sans reimporter tout le realm.

## 6. Etat du Control Panel

Le `control-panel` est deja recable vers le Keycloak heberge sur la VM Vault.

Configuration active attendue dans `/etc/control-panel/auth-prototype.env` :

- `AUTH_PROTO_OIDC_ISSUER_URL=https://auth.cascadya.internal/realms/cascadya-corp`
- `AUTH_PROTO_OIDC_DISCOVERY_URL=https://auth.cascadya.internal/realms/cascadya-corp/.well-known/openid-configuration`
- `AUTH_PROTO_OIDC_INTERNAL_BASE_URL=https://auth.cascadya.internal`
- `AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL=https://auth.cascadya.internal`
- `AUTH_PROTO_OIDC_VERIFY_TLS=false`

Remarque :

- `AUTH_PROTO_OIDC_VERIFY_TLS=false` est un compromis temporaire impose par le certificat auto-signe actuel

Validation de service observee le `2026-04-15` :

- `GET /auth/login` : `200`
- `GET /auth/oidc/start?next=/ui/alerts` : `303`
- login OIDC complet deja observe dans les logs du service `control-panel-auth`

## 7. Etat du portail Cascadya

Le portail `portal.cascadya.internal` est desormais connecte au Keycloak heberge sur la VM Vault.

Etat observe le `2026-04-16` :

- client OIDC actif : `cascadya-portal-web`
- login OIDC fonctionnel
- retour callback fonctionnel
- creation de session portail fonctionnelle
- filtrage des cartes par roles deja actif
- blocage restant : roles metier encore absents des comptes utilisateurs testes

## 8. Etat de l'ancien Keycloak du Control Panel

L'ancien stack local du `control-panel` n'est plus le service actif.

Etat attendu cote `control-panel-DEV1-S` :

- anciens conteneurs Keycloak arretes
- ancien repertoire retire du runtime actif
- repertoire d'archive present :
  - `/opt/control-panel/keycloak.retired.2026-04-15-152216`

Des backups de configuration existent encore sous :

- `/root/control-panel-auth-backups/`

## 9. Contraintes et points d'attention restants

- le certificat de `auth.cascadya.internal` est encore auto-signe
- tant que ce certificat n'est pas remplace ou distribue, les clients OIDC doivent soit :
  - faire confiance au certificat
  - soit desactiver la verification TLS
- si le DNS interne n'est pas encore officiellement bascule, une resolution locale de `auth.cascadya.internal` peut rester necessaire sur certaines VMs

## 10. Commandes de verification de reference

Sur `vault-DEV1-S` :

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
curl -sk -H 'Host: auth.cascadya.internal' \
  https://127.0.0.1/realms/cascadya-corp/.well-known/openid-configuration
```

Sur `control-panel-DEV1-S` :

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/auth/login
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8000/auth/oidc/start?next=/ui/alerts'
sudo journalctl -u control-panel-auth -n 50 --no-pager
```

## 10. Fichiers de verite dans ce repo

- `inventory/hosts.yml`
- `inventory/group_vars/vault_vm.yml`
- `playbooks/vault_keycloak.yml`
- `roles/vault_vm_keycloak`

Ce PRD decrit l'etat courant. Pour le mecanisme de deploiement et les hypotheses initiales, voir aussi `docs/KEYCLOAK_VAULT_VM_GUIDE.md`.
