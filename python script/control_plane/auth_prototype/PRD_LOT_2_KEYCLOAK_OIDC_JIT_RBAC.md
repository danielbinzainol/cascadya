# PRD - Lot 2 - Keycloak, OIDC, JIT user mirroring et administration des comptes

## 1. Objet

Ce document fige le lot 2 du chantier IAM du Control Panel au 27 mars 2026.

Le lot 2 etend le socle RBAC du lot 1 en ajoutant :

- `Keycloak` comme fournisseur d'identite ;
- un flux OIDC complet pour le login web ;
- la creation JIT des utilisateurs miroir ;
- l'enforcement des permissions metier sur les routes HTML et API ;
- une vraie premiere brique d'administration des comptes.

L'etat cible retenu en fin de lot est maintenant :

- login principal via `Keycloak OIDC` ;
- login legacy desactive sur l'environnement courant ;
- onboarding des utilisateurs via creation admin + mot de passe temporaire Keycloak ;
- plus aucun flux actif d'email d'activation depuis l'interface du Control Panel.

## 2. Objectifs du lot 2

- Deployer `Keycloak` avec sa base dediee `postgres-keycloak`.
- Exposer `auth.cascadya.internal` derriere `Traefik`.
- Remplacer le login local comme mecanisme principal par un flux `Authorization Code`.
- Creer automatiquement l'utilisateur miroir dans la base metier au premier login OIDC.
- Evaluer les permissions metier depuis PostgreSQL, pas depuis Keycloak.
- Ajouter une interface admin pour consulter, creer, modifier, activer, desactiver et supprimer des utilisateurs.
- Conserver une separation nette entre authentification et autorisation :
  - `Keycloak` authentifie ;
  - PostgreSQL metier autorise.

## 3. Architecture cible du lot 2

```text
Navigateur VPN
   ->
Traefik
   ->
FastAPI Control Panel
   ->
redirection OIDC
   ->
Keycloak
   ->
callback OIDC vers FastAPI
   ->
JIT user mirroring dans PostgreSQL metier
   ->
evaluation RBAC et ouverture de session applicative
```

Composants stabilises :

- `postgres-fastapi`
- `postgres-keycloak`
- `keycloak`
- `traefik`
- `fastapi-control-panel`

Domaines internes :

- `control-panel.cascadya.internal`
- `auth.cascadya.internal`

## 4. Infrastructure mise en place

### 4.1 Keycloak

Un stack Docker dedie a ete ajoute sur `control-panel-DEV1-S` :

- `control-panel-postgres-keycloak`
- `control-panel-keycloak`

Exposition locale :

- PostgreSQL Keycloak sur `127.0.0.1:5434`
- Keycloak HTTP sur `127.0.0.1:8081`

Exposition utilisateur :

- `https://auth.cascadya.internal` via `Traefik`

### 4.2 Traefik

`Traefik` route maintenant deux frontaux HTTPS :

- `control-panel.cascadya.internal`
- `auth.cascadya.internal`

Certificats autosignes generes pour les deux hostnames.

L'acces reste filtre par `ipAllowList` sur les plages attendues.

### 4.3 DNS VPN

Le DNS interne via `dnsmasq` retourne maintenant aussi :

- `auth.cascadya.internal -> 10.42.1.2`

Le flux utilisateur est donc resolu entierement dans le tunnel WireGuard.

## 5. Configuration OIDC et admin cote application

Le backend `FastAPI` a ete enrichi avec les variables suivantes :

- `AUTH_PROTO_OIDC_ENABLED`
- `AUTH_PROTO_ENABLE_LEGACY_LOGIN`
- `AUTH_PROTO_OIDC_ISSUER_URL`
- `AUTH_PROTO_OIDC_DISCOVERY_URL`
- `AUTH_PROTO_OIDC_INTERNAL_BASE_URL`
- `AUTH_PROTO_OIDC_VERIFY_TLS`
- `AUTH_PROTO_OIDC_CLIENT_ID`
- `AUTH_PROTO_OIDC_CLIENT_SECRET`
- `AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL`
- `AUTH_PROTO_KEYCLOAK_ADMIN_REALM`
- `AUTH_PROTO_KEYCLOAK_ADMIN_USERNAME`
- `AUTH_PROTO_KEYCLOAK_ADMIN_PASSWORD`
- `AUTH_PROTO_KEYCLOAK_MANAGED_REALM`
- `AUTH_PROTO_BOOTSTRAP_ADMIN_EMAILS`
- `AUTH_PROTO_JIT_DEFAULT_ROLES`

Points importants stabilises pendant la validation :

- la discovery OIDC backend se fait en interne via `http://127.0.0.1:8081/...`
- les endpoints visibles dans les tokens et redirections restent publics en `https://auth.cascadya.internal/...`
- le flag `AUTH_PROTO_ENABLE_LEGACY_LOGIN` existe encore dans le code, mais il est desactive dans l'etat de deploiement courant et dans l'inventaire Ansible actif

Cela evite de faire dependre le backchannel de Traefik et du certificat autosigne, tout en gardant un point de coupure clair pour le login local.

## 6. Comportement backend implemente

### 6.1 Login OIDC web

Le backend gere maintenant :

- `GET /auth/login`
- `GET /auth/oidc/start`
- `GET /auth/callback`
- `POST /auth/logout`

Le flux utilise :

- `Authorization Code`
- session serveur cote `FastAPI`
- cookie de session signe

### 6.2 Login legacy

Le login legacy local n'est plus le mode operatoire cible.

Etat retenu en fin de lot :

- desactive sur l'environnement de dev valide ;
- desactive dans l'inventaire Ansible actif ;
- non visible sur la page de login tant que `AUTH_PROTO_ENABLE_LEGACY_LOGIN=false`.

Le code de fallback existe encore uniquement comme option de secours technique, pas comme flux normal du produit.

### 6.3 Support bearer token

Le backend est aussi capable d'authentifier des appels API via :

- `Authorization: Bearer <token>`

Ce point prepare de futurs usages API ou frontend separe.

## 7. JIT user mirroring

Au premier login d'un utilisateur Keycloak, `FastAPI` :

- lit les claims OIDC ;
- cree l'utilisateur miroir s'il n'existe pas ;
- met a jour l'email, le username et le display name si necessaire ;
- renseigne `last_login_at`.

Champs miroir exploites :

- `keycloak_uuid`
- `email`
- `preferred_username`
- `display_name`
- `is_active`
- `last_login_at`

Politique d'amorcage :

- attribution eventuelle de roles par defaut via `AUTH_PROTO_JIT_DEFAULT_ROLES`
- attribution automatique du role `admin` pour les emails listes dans `AUTH_PROTO_BOOTSTRAP_ADMIN_EMAILS`

## 8. RBAC metier et enforcement

Le lot 2 etend le catalogue RBAC avec :

- `dashboard:read`
- `user:read`
- `user:write`
- `role:assign`

Les routes HTML et API importantes sont protegees par permission, par exemple :

- `/app` -> `dashboard:read`
- `/admin` -> `user:read`
- `/api/admin/users` -> `user:read`
- modification des roles -> `role:assign`
- activation / desactivation utilisateur -> `user:write`

Le principe stabilise est :

- `Keycloak` authentifie
- PostgreSQL metier autorise

## 9. Administration des utilisateurs

La brique de user management lot 2 couvre maintenant :

- lister les utilisateurs miroir ;
- consulter les roles disponibles ;
- creer un utilisateur dans Keycloak ;
- creer immediatement le miroir utilisateur dans PostgreSQL ;
- modifier l'email, le prenom et le nom d'un utilisateur ;
- remplacer les roles d'un utilisateur ;
- activer / desactiver un utilisateur miroir ;
- supprimer un utilisateur de Keycloak et du RBAC local ;
- afficher les permissions derivees ;
- proteger l'interface contre l'auto-suppression du compte admin courant.

Canaux exposes :

- UI admin HTML
- endpoints JSON d'administration

Endpoints admin stabilises :

- `GET /api/admin/users`
- `GET /api/admin/users/{id}`
- `POST /api/admin/users/invite`
- `PUT /api/admin/users/{id}`
- `PUT /api/admin/users/{id}/roles`
- `PUT /api/admin/users/{id}/status`
- `DELETE /api/admin/users/{id}`

## 10. Onboarding des comptes

Le mode d'onboarding retenu en fin de lot est volontairement simple :

- creation du compte par un admin depuis le Control Panel ;
- attribution immediate du role metier ;
- definition d'un mot de passe temporaire dans Keycloak ;
- changement de mot de passe par l'utilisateur au premier login.

Le flux par email d'activation ou de reset n'est plus expose depuis l'interface du Control Panel.

Raison de ce choix :

- l'acces SMTP sortant n'est pas stabilise sur la VM ;
- le flux `create user + temporary password` a ete valide de bout en bout ;
- ce mode reste suffisant pour la phase actuelle de developpement prive sous WireGuard.

## 11. Realm et client Keycloak

Le realm de reference est :

- `cascadya-corp`

Le client OIDC de reference est :

- `control-panel-web`

Le client est configure pour :

- `standardFlowEnabled=true`
- `publicClient=false`
- `redirectUris` vers `https://control-panel.cascadya.internal/auth/callback`
- `post logout redirect` vers `https://control-panel.cascadya.internal/auth/login`

## 12. Validations techniques atteintes

Le lot 2 est considere valide car les points suivants ont ete verifies :

- stack `Keycloak + postgres-keycloak` demarree et `healthy`
- discovery OIDC disponible sur `127.0.0.1:8081`
- discovery OIDC disponible aussi via `https://auth.cascadya.internal`
- backend `FastAPI` capable de produire une redirection OIDC valide
- login OIDC utilisateur valide
- creation JIT de l'utilisateur miroir en base metier
- attribution bootstrap admin fonctionnelle
- acces a `/app` et `/admin` valide apres login
- creation admin de plusieurs comptes fonctionnelle
- edition des donnees d'identite fonctionnelle
- attribution des roles `viewer`, `operator` et `admin` fonctionnelle
- activation / desactivation fonctionnelle
- suppression admin fonctionnelle
- onboarding sans email valide avec mot de passe temporaire Keycloak
- login legacy desactive dans l'etat de deploiement courant
- playbook Ansible rejoue avec succes sur l'etat final du lot 2

## 13. Valeur obtenue

Le Control Panel n'est plus seulement un prototype avec comptes locaux.

Il dispose maintenant :

- d'une authentification centralisee ;
- d'une identite utilisateur tracable ;
- d'un pont fonctionnel entre OIDC et RBAC metier ;
- d'une administration de comptes exploitable ;
- d'un deploiement reproductible via Ansible ;
- d'un socle pret pour brancher les premiers modules metier.

## 14. Limites volontaires restantes

Le lot 2 ne couvre pas encore :

- federation externe ;
- MFA obligatoire ;
- audit events complets ;
- workflows d'approbation ;
- policies contextuelles avancees ;
- gestion fine des groupes Keycloak ;
- self-service de reset mot de passe depuis le Control Panel ;
- envoi d'emails applicatifs, faute de SMTP sortant stabilise.

## 15. Definition of Done atteinte

Le lot 2 est considere atteint car :

- Keycloak est deployee et accessible ;
- le login principal du Control Panel passe par OIDC ;
- le backend cree les utilisateurs miroir a la volee ;
- les permissions metier sont enforcees depuis PostgreSQL ;
- un administrateur peut creer, modifier, desactiver, reactiver, supprimer et role-mapper des comptes ;
- l'etat de deploiement courant est OIDC-only ;
- le tout reste compatible avec l'architecture privee `WireGuard + Traefik + DNS interne`.

## 16. Suite logique

La suite naturelle apres ce lot est :

- attaquer le premier module metier visible du Control Panel ;
- introduire un registre de `sites` ;
- introduire un module `inventory` lisible et filtrable ;
- brancher les permissions `site:read`, `site:write`, `inventory:read`, `inventory:scan` sur des pages et APIs concretes ;
- preparer ensuite les workflows de scan et de provisionnement.
