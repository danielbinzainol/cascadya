# PRD - Lot 1 - Socle PostgreSQL et RBAC metier

## 1. Objet

Ce document fige le lot 1 du chantier IAM du Control Panel au 27 mars 2026.

Le lot 1 avait pour but de sortir le prototype `FastAPI` d'un mode purement local pour lui donner :

- une vraie base metier PostgreSQL ;
- un schema RBAC versionne ;
- une base de roles et permissions persistante ;
- un socle exploitable avant l'integration Keycloak.

Ce lot ne remplacait pas encore le login local. Il preparait l'application a recevoir un fournisseur d'identite externe sans casser l'existant.

## 2. Objectifs du lot 1

- Deployer une base `postgres-fastapi` dediee au backend metier.
- Connecter `FastAPI` a PostgreSQL via SQLAlchemy.
- Introduire Alembic pour versionner le schema.
- Creer les entites RBAC : `users`, `roles`, `permissions`, `user_roles`, `role_permissions`.
- Seed un premier catalogue de roles et permissions.
- Ajouter des checks applicatifs simples pour verifier la sante de l'application et de la base.

## 3. Architecture cible du lot 1

```text
Utilisateur VPN
   ->
Traefik
   ->
FastAPI (127.0.0.1:8000)
   ->
PostgreSQL metier (127.0.0.1:5433)
```

Composants concernes :

- `wireguard-DEV1-S`
  - DNS interne `10.8.0.1`
  - forwarding vers `10.42.0.0/16`
- `control-panel-DEV1-S`
  - `Traefik`
  - `FastAPI`
  - `postgres-fastapi`

## 4. Perimetre implemente

### 4.1 Base de donnees metier

Un conteneur Docker `postgres-fastapi` a ete ajoute sur `control-panel-DEV1-S`.

Parametres stabilises :

- exposition locale uniquement sur `127.0.0.1:5433`
- base : `control_panel`
- utilisateur : `control_panel`
- mot de passe injecte par env

### 4.2 Couche persistence cote FastAPI

Le backend a ete branche a PostgreSQL avec :

- `SQLAlchemy 2`
- `psycopg 3`
- `Alembic`

Une couche standard a ete introduite pour :

- creer l'engine ;
- ouvrir les sessions DB ;
- partager le `Base` SQLAlchemy ;
- verifier la sante de la connexion.

### 4.3 Schema RBAC

Le schema metier introduit est :

- `users`
- `roles`
- `permissions`
- `user_roles`
- `role_permissions`
- `alembic_version`

La table `users` ne stocke aucun mot de passe.

Colonnes structurantes du miroir utilisateur :

- `id`
- `keycloak_uuid`
- `email`
- `display_name`
- `is_active`
- `created_at`
- `updated_at`

### 4.4 Catalogue RBAC initial

Permissions seedees :

- `audit:read`
- `inventory:read`
- `inventory:scan`
- `provision:cancel`
- `provision:prepare`
- `provision:run`
- `site:read`
- `site:write`

Roles seedes :

- `admin`
- `operator`
- `provisioning_manager`
- `viewer`

### 4.5 Migration et seed

Le schema est versionne par Alembic.

Livrables du lot :

- migration initiale de creation des tables RBAC ;
- script de seed idempotent ;
- support des migrations sur la VM.

### 4.6 Endpoints de verification

Deux endpoints ont ete ajoutes pour valider le lot :

- `GET /healthz`
- `GET /healthz/db`

Un endpoint d'inspection du catalogue RBAC a aussi ete ajoute :

- `GET /api/admin/rbac/catalog`

## 5. Etat valide en production de dev

Le lot 1 a ete valide sur `control-panel-DEV1-S` avec :

- migration Alembic appliquee ;
- seed RBAC execute ;
- service `control-panel-auth` redemarre avec succes ;
- `GET /healthz` OK ;
- `GET /healthz/db` OK ;
- verification SQL directe des tables, roles et permissions.

Verification SQL confirmee :

- tables presentes : `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `alembic_version`
- roles presents : `admin`, `operator`, `provisioning_manager`, `viewer`
- 8 permissions presentes

## 6. Automatisation

Le lot 1 a ete rejoue et fige via Ansible.

Le playbook couvre :

- configuration reseau et DNS interne cote WireGuard ;
- deploiement de `postgres-fastapi` ;
- injection de l'env applicatif ;
- installation des dependances Python ;
- execution d'Alembic ;
- execution du seed RBAC ;
- verification de sante applicative.

## 7. Valeur obtenue

Le prototype n'est plus seulement une page web avec comptes hardcodes. Il dispose maintenant :

- d'une vraie persistence metier ;
- d'un schema RBAC versionne ;
- d'un catalogue de permissions durable ;
- d'une base propre pour brancher OIDC ensuite ;
- d'un etat reproductible via Ansible.

## 8. Hors perimetre volontaire du lot 1

Le lot 1 ne couvrait pas encore :

- Keycloak ;
- le remplacement du login local ;
- la creation JIT des utilisateurs miroir ;
- l'enforcement complet des permissions sur toutes les routes ;
- la gestion d'utilisateurs via UI.

## 9. Definition of Done atteinte

Le lot 1 est considere atteint car :

- la base PostgreSQL metier tourne de facon stable ;
- `FastAPI` est connecte a cette base ;
- le schema RBAC est migre et versionne ;
- le seed roles / permissions est en place ;
- les checks de sante applicatifs sont valides ;
- l'etat cible est maintenant automatisable via Ansible.

## 10. Suite logique

Le lot 2 devait s'appuyer sur ce socle pour ajouter :

- `Keycloak`
- OIDC
- JIT user mirroring
- enforcement RBAC complet
- gestion d'utilisateurs
