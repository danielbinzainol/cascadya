# PRD - Fondations IAM et RBAC du Control Panel

## 1. Contexte

Le Control Panel dispose aujourd'hui d'un prototype web `FastAPI` protege par une authentification locale simple.
Ce prototype tourne derriere `Traefik` sur la VM `control-panel-DEV1-S`, avec un acces reseau restreint via `WireGuard`.

Cet etat est suffisant pour valider un flux web de connexion, mais il ne repond pas aux besoins reels de :

- tracabilite individuelle des actions ;
- gestion centralisee des identites ;
- administration des acces par role et permission ;
- auditabilite des futures operations de provisionnement d'ordinateurs industriels.

Avant de developper les modules metier de decouverte, configuration et provisionnement distant, il faut poser un socle IAM solide.

## 2. Objectifs

### 2.1 Objectifs produit

- Remplacer l'authentification locale FastAPI par un fournisseur d'identite centralise : `Keycloak`.
- Imposer la regle `1 compte = 1 utilisateur physique`.
- Introduire un modele de permissions metier persistant dans une base PostgreSQL dediee au backend.
- Permettre a `FastAPI` de prendre les decisions d'autorisation metier via un RBAC interne, independant de la simple authentification OIDC.
- Preparer une base exploitable pour l'audit des actions sensibles, notamment le provisionnement industriel.

### 2.2 Hors perimetre de ce lot

- Federation externe avec Azure AD, Google Workspace ou autre IdP tiers.
- MFA obligatoire.
- Self-service complet de gestion utilisateurs.
- Workflow d'approbation metier avance.
- ABAC fin, policies contextuelles ou moteur type OPA.
- Provisionnement industriel lui-meme.

## 3. Principes directeurs

### 3.1 Separation des responsabilites

- `Keycloak` gere l'identite, la page de login, les mots de passe, la session SSO, les tokens OIDC.
- `FastAPI` gere la logique metier, les permissions metier et les decisions d'acces applicatif.
- La base metier du Control Panel ne stocke aucun mot de passe utilisateur.

### 3.2 Auditabilite

Chaque action sensible doit pouvoir etre rattachee a un utilisateur humain unique, identifie par :

- son `keycloak_uuid` ;
- son email ;
- son identite visible dans les logs et traces applicatives.

### 3.3 Compatibilite avec l'etat actuel

Le prototype actuel est un backend `FastAPI` qui sert aussi des pages HTML.
Le choix recommande pour la premiere integration OIDC est donc :

- un flux `Authorization Code` ;
- une session serveur cote `FastAPI` ;
- et non pas un simple stockage brut du JWT dans le navigateur comme dans une SPA pure.

Cela permet de rester coherent avec l'architecture actuelle tout en gardant la possibilite d'exposer plus tard des API `Bearer` pour un frontend separe.

## 4. Architecture cible

## 4.1 Composants

- `postgres-keycloak` : base dediee a Keycloak
- `keycloak` : fournisseur d'identite OIDC
- `postgres-fastapi` : base dediee au backend metier
- `fastapi-control-panel` : backend applicatif et serveur web
- `traefik` : reverse proxy TLS deja en place

## 4.2 Architecture logique

```text
Navigateur
   ->
Traefik
   ->
FastAPI Control Panel
   -> redirection OIDC
Keycloak
   -> authentification utilisateur
   -> retour OIDC vers FastAPI
FastAPI
   -> validation du token / userinfo / claims
   -> lookup du user miroir dans postgres-fastapi
   -> evaluation des roles et permissions metier
   -> session applicative et acces aux routes
```

## 4.3 Separation des bases

Deux bases PostgreSQL distinctes sont prevues :

- une pour `Keycloak`
- une pour le backend metier `FastAPI`

Cette separation limite le couplage entre l'IdP et l'application metier et facilite l'evolution future.

## 5. Nommage et exposition

### 5.1 Domaines internes

- `control-panel.cascadya.internal` : application FastAPI / Traefik
- `auth.cascadya.internal` : interface Keycloak via Traefik

### 5.2 Reseau

- acces uniquement via `WireGuard`
- filtrage Traefik / firewall conserve
- Keycloak suit le meme modele d'exposition privee que le Control Panel

## 6. Modele de donnees metier pour le RBAC

## 6.1 Table `users`

- `id`
- `keycloak_uuid` unique
- `email` unique
- `display_name`
- `is_active`
- `created_at`
- `updated_at`

## 6.2 Table `roles`

- `id`
- `name`
- `description`

Exemples :

- `admin`
- `operator`
- `provisioning_manager`
- `viewer`

## 6.3 Table `permissions`

- `id`
- `name`
- `description`

Exemples :

- `site:read`
- `site:write`
- `provision:prepare`
- `provision:run`
- `provision:cancel`
- `audit:read`
- `inventory:read`
- `inventory:scan`

## 6.4 Table `user_roles`

Table de liaison many-to-many entre utilisateurs et roles.

## 6.5 Table `role_permissions`

Table de liaison many-to-many entre roles et permissions.

## 6.6 Evolutions utiles a prevoir rapidement

- `last_login_at`
- `created_by`
- `deactivated_at`
- table `audit_events`

## 7. Strategie d'integration OIDC

## 7.1 Decision recommandee

Pour le FastAPI actuel, la strategie recommande est :

- authentification via `Keycloak`
- validation OIDC cote backend
- creation d'une session applicative serveur dans `FastAPI`

Cette approche est plus adaptee qu'un modele SPA pur avec `Bearer` token gere par le navigateur, car l'application actuelle sert deja ses pages HTML.

## 7.2 Cas API futurs

Pour les endpoints API appeles par un futur frontend separe ou par des outils internes, `FastAPI` devra aussi pouvoir accepter un header :

`Authorization: Bearer <token>`

Le PRD couvre donc les deux usages suivants :

- session web serveur pour le Control Panel actuel
- bearer token pour les API futures

## 7.3 Verification des tokens

`FastAPI` devra :

- recuperer les cles publiques du realm Keycloak via JWKS
- verifier la signature du JWT
- verifier `iss`, `aud`, `exp`, `nbf`
- extraire `sub`, `email`, `preferred_username`, `name`

## 8. JIT User Mirroring

## 8.1 Principe

Si un utilisateur authentifie par Keycloak se presente pour la premiere fois, mais n'existe pas encore dans la base metier, `FastAPI` cree automatiquement un utilisateur miroir.

## 8.2 Donnees initialisees

- `keycloak_uuid`
- `email`
- `display_name`
- `is_active = true`

## 8.3 Important

La creation JIT ne doit pas attribuer automatiquement de role privilegie.
L'utilisateur miroir peut etre cree sans permissions tant qu'un administrateur ne lui affecte pas de role.

## 9. Comportement backend FastAPI

## 9.1 A supprimer du prototype actuel

- logique de mots de passe locaux
- hashing scrypt / verification locale
- comptes de demo hardcodes comme mecanisme principal d'acces

## 9.2 A ajouter

- configuration OIDC
- client Keycloak
- gestion de session post-login
- dependance `get_current_identity`
- dependance `require_permission("permission:name")`
- stockage et lecture du RBAC depuis PostgreSQL

## 9.3 Gestion des erreurs

- `401 Unauthorized` si l'utilisateur n'est pas authentifie ou si le token est invalide
- `403 Forbidden` si l'utilisateur est authentifie mais n'a pas la permission requise

## 10. Variables et configuration attendues

Exemples de variables d'environnement a introduire :

- `AUTH_OIDC_ENABLED=true`
- `AUTH_OIDC_ISSUER_URL=https://auth.cascadya.internal/realms/cascadya-corp`
- `AUTH_OIDC_CLIENT_ID=control-panel-web`
- `AUTH_OIDC_CLIENT_SECRET=...`
- `AUTH_OIDC_REDIRECT_URI=https://control-panel.cascadya.internal/auth/callback`
- `DATABASE_URL=postgresql+psycopg://...`
- `KEYCLOAK_JWKS_CACHE_TTL_SECONDS=300`

## 11. Plan d'implementation

## Lot 1 - Donnees metier et persistence

Objectif :

- introduire `postgres-fastapi`
- brancher `FastAPI` a PostgreSQL
- poser le schema RBAC

Travaux :

- ajouter le conteneur `postgres-fastapi`
- integrer SQLAlchemy ou SQLModel
- ajouter Alembic
- creer les modeles `User`, `Role`, `Permission`, `user_roles`, `role_permissions`
- creer une migration initiale
- ajouter un jeu de seed minimal pour roles et permissions

Livrables :

- docker compose mis a jour
- schema RBAC versionne
- migration initiale

## Lot 2 - Keycloak et socle OIDC

Objectif :

- deployer Keycloak avec sa base dediee
- rendre l'application capable de deleguer le login a Keycloak

Travaux :

- ajouter `postgres-keycloak`
- ajouter `keycloak`
- exposer `auth.cascadya.internal` via Traefik
- creer le realm `cascadya-corp`
- creer le client OIDC `control-panel-web`
- creer au moins deux utilisateurs de test

Livrables :

- Keycloak accessible derriere Traefik
- login OIDC fonctionnel

## Lot 3 - Pont FastAPI vers Keycloak

Objectif :

- relier authentification OIDC et RBAC metier

Travaux :

- valider les tokens Keycloak
- implementer la creation JIT des utilisateurs miroir
- remplacer les protections legacy par `get_current_identity` et `require_permission`
- journaliser l'identite de l'utilisateur sur les actions sensibles

Livrables :

- routes protegees par permissions
- utilisateur miroir cree a la premiere connexion
- controle d'acces fonctionnel

## Lot 4 - Nettoyage du prototype legacy

Objectif :

- retirer la dette technique une fois le nouveau flux stable

Travaux :

- supprimer la page de login locale legacy
- supprimer les comptes de demo comme point d'entree principal
- conserver eventuellement un mode de secours uniquement hors production

## 12. Criteres d'acceptation

- les deux bases PostgreSQL et Keycloak tournent de facon stable sur la VM
- `auth.cascadya.internal` est accessible via Traefik sur le reseau prive
- le login local legacy n'est plus le mecanisme principal d'authentification
- un utilisateur se connecte via Keycloak puis accede au Control Panel
- `FastAPI` cree ou retrouve l'utilisateur miroir a partir du `keycloak_uuid`
- `FastAPI` retourne `401` pour un token invalide ou expire
- `FastAPI` retourne `403` pour un utilisateur sans permission suffisante
- les roles et permissions sont stockes dans PostgreSQL metier
- les futures actions sensibles peuvent etre tracees a un utilisateur unique

## 13. Risques et points d'attention

- confusion entre roles Keycloak et roles metier FastAPI
- trop de logique d'autorisation placee dans Keycloak au lieu du backend metier
- stockage non maitrise des tokens si le flux web n'est pas bien cadre
- absence de seed initial pour un premier administrateur applicatif
- dette de migration si le prototype local et la nouvelle couche OIDC coexistent trop longtemps

## 14. Decision recommandee

La direction recommandee est :

- `Keycloak` pour l'authentification et l'identite
- `PostgreSQL FastAPI` pour les roles et permissions metier
- `FastAPI` comme point central de decision RBAC
- flux OIDC compatible avec l'application web actuelle
- JIT user mirroring sans attribution automatique de privileges

Ce lot doit etre considere comme la fondation obligatoire avant les modules metier de provisionnement industriel.
