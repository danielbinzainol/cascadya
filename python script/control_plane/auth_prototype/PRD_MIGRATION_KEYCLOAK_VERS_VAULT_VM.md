# PRD - Migration de Keycloak vers la VM Vault pour une identite partagee

## Statut documentaire

Ce document reste la base de conception initiale.

L'etat live valide au 2026-04-16 est desormais le suivant :

- `Keycloak` et `postgres-keycloak` tournent bien sur `vault-DEV1-S`
  (`10.42.2.4`) ;
- `auth.cascadya.internal` pointe maintenant vers `10.42.2.4` et sert bien la
  discovery OIDC ;
- `portal.cascadya.internal` est publie sur `control-panel-DEV1-S`
  (`10.42.1.2`) ;
- les corrections reseau necessaires ont inclus :
  - le NAT `wg0 -> ens5` sur `wireguard-DEV1-S`
  - l'ajout de `10.42.1.5/32` dans les allowlists des frontaux concernes ;
- les clients `Keycloak` confirmes en base sur Vault sont :
  - `control-panel-web`
  - `cascadya-features-web`
  - `grafana-monitoring`
- le client `cascadya-portal-web` manque encore dans le realm migre et reste un
  drift applicatif a corriger ;
- la route legacy `auth.cascadya.internal` du Traefik local du Control Panel
  doit encore etre retiree.

Pour la verite operationnelle actuelle, se reporter en priorite a :

- [PRD_MIGRATION_KEYCLOAK_VERS_VAULT_VM_AJUSTE_2026-04-15.md](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/PRD_MIGRATION_KEYCLOAK_VERS_VAULT_VM_AJUSTE_2026-04-15.md)
- [PRD_DNS_INTERNE_SERVICE_VM.md](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/PRD_DNS_INTERNE_SERVICE_VM.md)

## 1. Objet

Ce document decrit :

- l'architecture d'identification actuelle effectivement implemente dans le workspace ;
- la maniere dont elle est cablee entre `FastAPI`, `Keycloak`, `Traefik`, `PostgreSQL` et `WireGuard` ;
- la cible souhaitee : deplacer `Keycloak` hors de la VM `control-panel-DEV1-S` vers la VM Vault ;
- la facon de rendre ce fournisseur d'identite partageable entre plusieurs services :
  - le `Control Panel` sur `51.15.115.203` ;
  - la mini app `cascadya_features` sur la meme VM ;
  - `Grafana` sur `51.15.83.22` ;
- les changements d'Ansible necessaires pour que la VM Vault puisse etre reprovisionnee proprement a chaque run.

Ce PRD traite d'une **migration d'hebergement de l'Identity Provider**. Il ne suppose pas que toute l'autorisation applicative devienne commune entre services.

Point de vigilance important :

- `Keycloak` est le composant mutualisable ;
- le **RBAC metier du Control Panel reste local a l'application** tant qu'une refonte RBAC inter-services n'est pas explicitement decidee.

## 2. Resume executif

L'etat actuel est le suivant :

- `Keycloak` tourne sur la VM `control-panel-DEV1-S`, dans Docker ;
- sa base `postgres-keycloak` tourne sur la meme VM ;
- `Traefik` sur cette meme VM expose :
  - `https://control-panel.cascadya.internal`
  - `https://auth.cascadya.internal`
- le backend `FastAPI` du Control Panel parle a `Keycloak` en **loopback** via `127.0.0.1:8081` ;
- le realm importe ne contient aujourd'hui qu'un seul client OIDC : `control-panel-web`.

La cible souhaitee est :

- heberger `Keycloak` et `postgres-keycloak` sur la VM Vault `51.15.36.65` ;
- conserver le hostname public/interne `auth.cascadya.internal` ;
- faire pointer ce hostname vers la VM Vault au lieu de la VM Control Panel ;
- permettre a plusieurs services de partager le meme fournisseur d'identite :
  - `control-panel-web`
  - `cascadya-features`
  - `grafana`
- conserver le RBAC metier local du Control Panel ;
- ajouter un provisioning Ansible reproductible cote VM Vault.

## 3. Perimetre

### 3.1 Dans le perimetre

- migration de `Keycloak` hors de la VM Control Panel ;
- migration de sa base dediee `postgres-keycloak` ;
- conservation du realm `cascadya-corp` ;
- evolution du template de realm pour supporter plusieurs clients ;
- recablage du Control Panel vers un backchannel distant ;
- preparation de l'integration de `cascadya_features` et `Grafana` ;
- definition du futur role / playbook Ansible pour la VM Vault ;
- mise a jour de la resolution DNS interne pour `auth.cascadya.internal`.

### 3.2 Hors perimetre

- refonte globale du RBAC metier du Control Panel ;
- unification immediate des permissions metier entre `Control Panel`, `Features` et `Grafana` ;
- remplacement de Vault comme gestionnaire de secrets ;
- redesign complet de la PKI ou du reverse proxy existant sur tout le SI ;
- migration immediate de tous les services vers OIDC si le decouplage de Keycloak n'est pas encore valide.

## 4. Architecture actuelle reelle

## 4.1 Inventaire fonctionnel des VMs concernees

### Control Panel VM

- VM cible : `control-panel-DEV1-S`
- acces SSH connu : `ubuntu@51.15.115.203`
- IP privee utilisee dans les docs et l'inventaire actuel : `10.42.1.2`
- services applicatifs concernes :
  - `Control Panel Auth Prototype`
  - `cascadya_features`

### Monitoring VM

- VM cible : `monitoring-DEV1-S`
- acces SSH connu : `ubuntu@51.15.83.22`
- acces Grafana aujourd'hui :
  - `http://10.42.1.4:3000`
- service partage futur concerne :
  - `Grafana`

### Vault VM

- VM cible : `vault-DEV1-S`
- acces SSH demande : `ubuntu@51.15.36.65`
- usage actuel identifie dans le workspace :
  - serveur Vault pour secrets et PKI
- adresse privee a **revalider** :
  - l'inventaire monitoring mentionne `10.42.2.4`
- aucun playbook Vault dedie n'a ete trouve dans le workspace local actuel.

## 4.2 Architecture actuelle du Control Panel

Le systeme d'identification actuellement deploye est **local a la VM Control Panel**.

### Composants actuellement heberges sur `control-panel-DEV1-S`

- `FastAPI` du Control Panel en service systemd, ecoute locale sur `127.0.0.1:8000`
- `Traefik` en Docker avec `network_mode: host`, termine TLS sur `:443`
- `postgres-fastapi` en Docker, base metier du Control Panel
- `postgres-keycloak` en Docker, base dediee a Keycloak
- `keycloak` en Docker, expose localement sur `127.0.0.1:8081`

### Exposition publique / interne actuelle

Le `Traefik` local route aujourd'hui :

- `control-panel.cascadya.internal` -> `http://127.0.0.1:8000`
- `auth.cascadya.internal` -> `http://127.0.0.1:8081`

Les deux routes sont protegees par le meme principe :

- acces borne aux CIDR WireGuard / reseaux autorises ;
- certificats TLS autosignes locaux generes sur la VM Control Panel.

### Resolution DNS actuelle

L'inventaire courant montre que `auth.cascadya.internal` pointe aujourd'hui vers la VM Control Panel :

- `auth.cascadya.internal` -> `10.42.1.2`

Ce point est central, car cela prouve que le hostname d'identite est actuellement colle a la VM Control Panel.

## 4.3 Cablage OIDC actuel dans l'application Control Panel

### Issuer public actuel

Le Control Panel est configure pour considerer `Keycloak` comme fournisseur OIDC sur :

- `https://auth.cascadya.internal/realms/cascadya-corp`

### Backchannel actuel

Le backend `FastAPI` ne parle pas a `Keycloak` via le hostname public.
Il utilise aujourd'hui un **backchannel local** :

- `AUTH_PROTO_OIDC_DISCOVERY_URL=http://127.0.0.1:8081/realms/cascadya-corp/.well-known/openid-configuration`
- `AUTH_PROTO_OIDC_INTERNAL_BASE_URL=http://127.0.0.1:8081`
- `AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL=http://127.0.0.1:8081`

Cela signifie que l'implementation actuelle est optimisee pour un `Keycloak` co-heberge.

### Flux web actuel

Le Control Panel utilise le flux OIDC standard suivant :

1. l'utilisateur est redirige vers `Keycloak` via `/auth/oidc/start`
2. `Keycloak` renvoie vers `/auth/callback`
3. le backend echange le `code` contre un `access_token`
4. le backend appelle `userinfo`
5. le backend fait du JIT provisioning local dans `postgres-fastapi`
6. une session serveur est creee dans `FastAPI`

### Flux API actuel

En plus de la session web, le backend supporte les bearer tokens :

1. introspection du token via l'endpoint OIDC
2. appel `userinfo`
3. synchronisation de l'utilisateur miroir local
4. evaluation des permissions RBAC locales

### Ce qui est mutualisable aujourd'hui

Partie mutualisable :

- le realm `Keycloak`
- les utilisateurs `Keycloak`
- les clients OIDC
- les jetons OIDC

Partie non mutualisable en l'etat :

- le RBAC metier du Control Panel
- la table miroir des utilisateurs du Control Panel
- les seeds de roles / permissions du Control Panel
- les endpoints d'administration d'utilisateurs propres au Control Panel

## 4.4 RBAC et miroir utilisateur actuels

Le Control Panel n'utilise pas `Keycloak` comme moteur de permissions metier.

Le modele actuel est :

- `Keycloak` authentifie ;
- le backend `FastAPI` cree ou retrouve un user miroir local ;
- ce user miroir porte :
  - `keycloak_uuid`
  - `email`
  - `preferred_username`
  - `display_name`
  - `is_active`
  - `last_login_at`
- les roles et permissions vivent dans la base metier locale `postgres-fastapi`.

Conclusion importante :

- deplacer `Keycloak` vers la VM Vault **ne deplace pas** le RBAC du Control Panel ;
- apres migration, le Control Panel continuera a gerer son autorisation metier localement.

## 4.5 Realm et clients actuellement provisionnes

Le template de realm actuellement versionne ne provisionne qu'un seul client :

- `control-panel-web`

Ce client :

- est confidentiel
- utilise le flux `authorization code`
- a pour redirect URI :
  - `https://control-panel.cascadya.internal/auth/callback`
- a pour post logout redirect :
  - `https://control-panel.cascadya.internal/auth/login`

Il n'existe pas aujourd'hui, dans le template versionne :

- de client OIDC pour `cascadya_features`
- de client OIDC pour `Grafana`

## 4.6 Etat actuel des autres services a partager

### `cascadya_features`

L'application `cascadya_features` tourne aujourd'hui :

- en `Flask`
- servie par `Waitress`
- localement sur `127.0.0.1:8766`
- derriere le `Traefik` de la VM Control Panel
- sur `https://features.cascadya.internal`

Etat actuel de l'authentification :

- pas de `Keycloak`
- pas d'OIDC
- pas de session SSO commune avec le Control Panel

### `Grafana`

`Grafana` sur la VM monitoring tourne aujourd'hui :

- en Docker
- expose sur `3000`
- administre par `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD`

Etat actuel de l'authentification :

- pas d'OIDC `Keycloak` configure
- pas de client `Keycloak` defini pour Grafana dans le workspace

## 4.7 Couplage Ansible actuel

Le role `auth_prototype/ansible/roles/control_panel_auth` gere aujourd'hui dans un seul bloc :

- l'environnement applicatif `FastAPI`
- le service systemd `control-panel-auth`
- `Traefik`
- `postgres-fastapi`
- `Keycloak`
- `postgres-keycloak`
- les certificats locaux Traefik pour `control-panel.cascadya.internal` et `auth.cascadya.internal`

Conclusion :

- le provisioning est actuellement **trop couple** a la VM Control Panel ;
- il n'existe pas de role dedie a un fournisseur d'identite partage heberge ailleurs.

## 5. Probleme a resoudre

L'architecture actuelle pose les limites suivantes :

1. `Keycloak` n'est pas mutualisable proprement car il vit sur la VM du Control Panel.
2. Le hostname `auth.cascadya.internal` est physiquement route vers la VM Control Panel.
3. Le backchannel `127.0.0.1:8081` empeche toute migration transparente sans recablage.
4. Le template de realm ne gere qu'un seul client applicatif.
5. `cascadya_features` et `Grafana` ne peuvent pas reutiliser le systeme actuel sans travail supplementaire.
6. Les secrets `Keycloak` et certains secrets Vault sont encore stockes dans des inventories Git-tracked, ce qui n'est pas acceptable comme etat cible.

## 6. Cible souhaitee

## 6.1 Cible d'architecture

La cible consiste a heberger sur la VM Vault :

- `postgres-keycloak`
- `keycloak`
- un reverse proxy ou point d'exposition TLS pour `auth.cascadya.internal`

Le Control Panel garde sur sa propre VM :

- `FastAPI`
- `postgres-fastapi`
- son `Traefik` local pour `control-panel.cascadya.internal`
- son RBAC local

La VM monitoring garde :

- `Grafana`
- son stack monitoring

`cascadya_features` reste sur la VM Control Panel, mais devient un client OIDC de l'IdP partage.

## 6.2 Principe directeur

Le systeme partage devient :

- **un fournisseur d'identite centralise**
- pas **une application RBAC centralisee unique**

Autrement dit :

- l'authentification est mutualisee ;
- l'autorisation reste, au moins dans un premier temps, specifique par service.

## 6.3 Resultat cible

### Service d'identite partage

- `Keycloak` heberge sur la VM Vault
- realm : `cascadya-corp`
- hostname conserve : `auth.cascadya.internal`

### Clients cibles a supporter

- `control-panel-web`
- `cascadya-features-web`
- `grafana-monitoring`

### Backchannels cibles

Le Control Panel doit cesser d'utiliser `127.0.0.1:8081` et pointer vers la VM Vault :

- soit via une URL privee inter-VM
- soit via le meme hostname `auth.cascadya.internal`
- soit via un hostname interne dedie si necessaire

### DNS cible

`auth.cascadya.internal` ne doit plus pointer vers `10.42.1.2`.
Il doit pointer vers l'adresse privee validee de la VM Vault.

## 7. Architecture cible recommandee

## 7.1 Topologie recommandee

### Sur la VM Vault

- `Vault` continue son role actuel de secrets / PKI
- `postgres-keycloak` tourne dans un scope isole
- `keycloak` tourne dans un scope isole
- un reverse proxy local termine TLS pour `auth.cascadya.internal`

### Sur la VM Control Panel

- `FastAPI` continue sur `127.0.0.1:8000`
- `postgres-fastapi` reste local
- `Traefik` local ne route plus `auth.cascadya.internal`
- `cascadya_features` reste derriere le `Traefik` local

### Sur la VM Monitoring

- `Grafana` reste local a la VM Monitoring
- son authentification est recablee vers le `Keycloak` centralise

## 7.2 Choix de reverse proxy sur la VM Vault

Deux options sont possibles.

### Option A - Traefik dedie sur la VM Vault

Avantages :

- homogene avec le pattern deja utilise sur le Control Panel
- reutilisation de l'expertise et des templates existants
- facile a raisonner pour `auth.cascadya.internal`

Inconvenients :

- deux Traefik differents dans le SI pour des usages differents

### Option B - Nginx ou Caddy dedie a Keycloak

Avantages :

- stack plus simple si seul `Keycloak` est expose sur cette VM

Inconvenients :

- moins homogene avec le reste du workspace

### Recommandation

La recommandation de ce PRD est :

- **Traefik dedie sur la VM Vault** si l'equipe veut conserver un pattern uniforme ;
- sinon **Nginx** si l'objectif est un hebergement minimal de `Keycloak`.

Le point obligatoire n'est pas le binaire du proxy, mais le resultat :

- `https://auth.cascadya.internal` doit etre servi par la VM Vault ;
- le service doit etre provisionnable a froid.

## 7.3 Strategie de backchannel recommandee

### Recommandation minimale

Conserver :

- `AUTH_PROTO_OIDC_ISSUER_URL=https://auth.cascadya.internal/realms/cascadya-corp`

et basculer le backchannel du Control Panel vers la VM Vault :

- `AUTH_PROTO_OIDC_DISCOVERY_URL=http://<vault_private_ip_or_name>:8081/realms/cascadya-corp/.well-known/openid-configuration`
- `AUTH_PROTO_OIDC_INTERNAL_BASE_URL=http://<vault_private_ip_or_name>:8081`
- `AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL=http://<vault_private_ip_or_name>:8081`

Avantage :

- le comportement applicatif existant est preserve avec un minimum de changement.

### Recommandation cible plus propre

Utiliser un backchannel TLS stable au lieu d'un HTTP prive inter-VM :

- `AUTH_PROTO_OIDC_DISCOVERY_URL=https://auth.cascadya.internal/realms/cascadya-corp/.well-known/openid-configuration`
- `AUTH_PROTO_OIDC_INTERNAL_BASE_URL=https://auth.cascadya.internal`
- `AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL=https://auth.cascadya.internal`

Condition :

- les VMs clientes doivent resoudre `auth.cascadya.internal` vers la bonne IP privee
- la confiance TLS doit etre geree proprement

### Decision recommandee

Phase 1 :

- backchannel prive simple pour reduire le risque

Phase 2 :

- convergence vers un backchannel TLS propre si necessaire

## 8. Impacts par service

## 8.1 Control Panel

### Ce qui reste identique

- logique applicative `FastAPI`
- gestion des sessions
- JIT provisioning local
- RBAC local
- admin d'utilisateurs via `Keycloak Admin API`

### Ce qui change

- `Keycloak` n'est plus local
- les URLs OIDC / admin changent
- `Traefik` du Control Panel ne route plus `auth.cascadya.internal`
- la VM doit joindre la VM Vault pour la partie OIDC / admin

## 8.2 Cascadya Features

### Etat actuel

- application interne sans OIDC

### Cible

`cascadya_features` devient un client OIDC du `Keycloak` central.

Deux modeles sont envisageables :

#### Mode 1 - Authentification simple

- tous les utilisateurs authentifies peuvent utiliser l'app
- peu ou pas de RBAC metier

#### Mode 2 - Autorisation par claims / groupes

- l'app lit des groupes ou roles remontees par `Keycloak`

### Recommandation

Commencer par le Mode 1.

Le besoin initial de `cascadya_features` est leger ; la priorite est de partager l'identification, pas de repliquer tout le RBAC du Control Panel.

## 8.3 Grafana

### Etat actuel

- admin local Grafana
- pas d'OIDC

### Cible

Grafana utilise `Keycloak` comme fournisseur OAuth/OIDC.

### Recommandation

Configurer Grafana avec `Generic OAuth` vers `Keycloak`.

Point d'attention :

- aujourd'hui Grafana semble expose via `http://10.42.1.4:3000`
- pour une integration propre, un hostname prive stable est recommande

Exemple de cible preferable :

- `https://grafana.cascadya.internal`

Si ce hostname n'existe pas encore, l'integration peut demarrer avec l'URL actuelle, mais ce n'est pas la cible ideale.

## 9. Evolution Ansible requise

## 9.1 Probleme du role actuel

Le role `control_panel_auth` regroupe aujourd'hui :

- l'application ;
- son RBAC ;
- `Traefik` ;
- `postgres-fastapi` ;
- `Keycloak` ;
- `postgres-keycloak`.

Ce role ne peut pas etre reutilise tel quel pour une architecture partagee.

## 9.2 Split recommande

### Nouveau role 1 - application Control Panel

Conserver ou extraire un role du type :

- `control_panel_app`

Responsabilites :

- env `FastAPI`
- systemd `control-panel-auth`
- `postgres-fastapi`
- `Traefik` du Control Panel
- migrations Alembic
- seed RBAC
- health checks applicatifs

### Nouveau role 2 - identity provider partage

Creer un role du type :

- `vault_vm_keycloak`

Responsabilites :

- dossiers runtime Keycloak
- `postgres-keycloak`
- `keycloak`
- proxy TLS pour `auth.cascadya.internal`
- realm import ou provisioning realm
- health checks `Keycloak`

### Nouveau role 3 - DNS interne

Mettre a jour le role qui gere `dnsmasq` / DNS interne pour :

- faire pointer `auth.cascadya.internal` vers la VM Vault
- potentiellement ajouter un hostname Grafana si retenu

## 9.3 Variables Ansible a introduire

### Variables communes d'identite partagee

- `shared_idp_domain`
- `shared_idp_realm`
- `shared_idp_public_base_url`
- `shared_idp_private_base_url`
- `shared_idp_http_port`
- `shared_idp_db_name`
- `shared_idp_db_user`
- `shared_idp_db_password`
- `shared_idp_admin_username`
- `shared_idp_admin_password`

### Variables par client OIDC

- `shared_idp_clients`
  - `client_id`
  - `client_name`
  - `client_secret`
  - `redirect_uris`
  - `post_logout_redirect_uris`
  - `web_origins`
  - `access_type`

Exemples cibles :

- `control-panel-web`
- `cascadya-features-web`
- `grafana-monitoring`

### Variables de recablage Control Panel

- `control_panel_oidc_issuer_url`
- `control_panel_oidc_discovery_url`
- `control_panel_oidc_internal_base_url`
- `control_panel_keycloak_admin_base_url`

### Variables DNS

- `wireguard_dns_records` pour `auth.cascadya.internal`
- eventuellement `grafana.cascadya.internal`

## 9.4 Gestion des secrets

Le workspace actuel montre que des secrets `Keycloak` et des secrets Vault ont ete poses dans des inventories suivis par Git.

Etat cible recommande :

- plus aucun secret `Keycloak` ou token Vault en clair dans un inventory Git-tracked ;
- secrets fournis via :
  - `Ansible Vault`, ou
  - variables d'environnement injectees au run, ou
  - lecture depuis `Vault` si un mecanisme d'amorcage existe deja.

Ce point doit faire partie de la migration, pas d'un chantier plus tard.

## 10. Strategie de migration recommandee

## Phase 0 - Baseline et preparation

Objectif :

- figer l'etat actuel avant de toucher a l'IdP

Actions :

- export du realm actuel
- sauvegarde ou snapshot de `postgres-keycloak`
- verification des clients et utilisateurs existants
- verification des redirects actuels du Control Panel

Sortie attendue :

- backup exploitable
- inventaire des utilisateurs / clients / realm settings

## Phase 1 - Decouplage du code et des templates

Objectif :

- separer dans Ansible ce qui releve de l'application et ce qui releve de l'IdP

Actions :

- extraire la logique `Keycloak` de `control_panel_auth`
- rendre les URLs OIDC et admin entierement variables
- preparer un template realm multi-clients

Sortie attendue :

- le Control Panel peut etre configure contre un IdP non local

## Phase 2 - Provisioning de Keycloak sur la VM Vault

Objectif :

- deployer un `Keycloak` equivalent sur la VM Vault sans encore basculer les clients

Actions :

- creer les repertoires runtime
- deployer `postgres-keycloak`
- deployer `keycloak`
- deployer le proxy de `auth.cascadya.internal`
- injecter le realm et les clients
- valider la disponibilite du realm

Sortie attendue :

- `https://auth.cascadya.internal` servi par la VM Vault en environnement de pre-bascule

## Phase 3 - Migration des donnees Keycloak

Objectif :

- restaurer le realm et les donnees dans la nouvelle cible

Options possibles :

### Option A - Import realm + recreation des users

acceptable si l'environnement est encore proto ou faible volume

### Option B - Migration DB / export-import complet

recommandee si l'on veut conserver exactement les users, IDs et etat du realm

Recommandation :

- privilegier l'approche qui preserve les `sub` / `keycloak_uuid`
- ne pas casser les correspondances deja stockees dans la base du Control Panel

Point critique :

- si les `sub` changent, le lien entre `Keycloak` et le miroir utilisateur local sera degrade.

## Phase 4 - Bascule du Control Panel

Objectif :

- faire du Control Panel le premier consommateur de l'IdP centralise

Actions :

- modifier les variables `AUTH_PROTO_OIDC_*`
- modifier `AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL`
- retirer la route locale `auth.cascadya.internal` du `Traefik` Control Panel
- ne plus deployer `Keycloak` sur la VM Control Panel
- valider login, callback, logout, introspection, admin API

Sortie attendue :

- le Control Panel s'authentifie contre le `Keycloak` sur VM Vault
- le RBAC local continue de fonctionner

## Phase 5 - Onboarding de Cascadya Features

Objectif :

- ajouter le second client sur la VM Control Panel

Actions :

- creer le client `cascadya-features-web`
- ajouter OIDC ou un mecanisme equivalent dans `cascadya_features`
- valider login / logout / session

Sortie attendue :

- `cascadya_features` partage la meme source d'identite

## Phase 6 - Onboarding de Grafana

Objectif :

- ajouter le client `grafana-monitoring`

Actions :

- creer le client `Keycloak`
- configurer `GF_AUTH_GENERIC_OAUTH_*`
- valider redirect URI et logout
- definir la politique de mapping roles/grafana

Sortie attendue :

- `Grafana` n'utilise plus uniquement un compte admin local pour l'acces operateur courant

## Phase 7 - Nettoyage et convergence

Actions :

- retirer `postgres-keycloak` et `keycloak` de la VM Control Panel
- retirer la route `auth.cascadya.internal` du `Traefik` Control Panel
- nettoyer les variables locales devenues obsoletes
- purger les secrets Git-tracked

## 11. Validation attendue

## 11.1 Validation cote VM Vault

- `Keycloak` repond sur son port local
- le proxy sert `auth.cascadya.internal`
- le realm `cascadya-corp` est lisible
- la base `postgres-keycloak` est reachable par `Keycloak`

## 11.2 Validation Control Panel

- `/auth/oidc/start` redirige bien vers `auth.cascadya.internal`
- `/auth/callback` fonctionne
- la session est creee
- `/auth/logout` fonctionne
- les bearer tokens sont encore introspectes correctement
- l'admin d'utilisateurs via `Keycloak Admin API` fonctionne encore

## 11.3 Validation Cascadya Features

- l'application peut utiliser un login commun
- un utilisateur authentifie atteint bien la feature

## 11.4 Validation Grafana

- login via `Keycloak`
- mapping correct des roles Grafana
- logout correct

## 11.5 Validation DNS

- `auth.cascadya.internal` ne pointe plus vers `10.42.1.2`
- il pointe vers la bonne IP privee de la VM Vault

## 12. Rollback

Le rollback doit etre prevu des le debut.

Rollback minimal :

1. remettre `auth.cascadya.internal` vers la VM Control Panel
2. restaurer l'ancien `Keycloak` local
3. remettre les variables `AUTH_PROTO_OIDC_*` vers `127.0.0.1:8081`
4. redemarrer le service `control-panel-auth`

Conditions pour rendre ce rollback possible :

- ne pas detruire trop tot le `Keycloak` local
- conserver snapshot DB / export realm
- conserver les anciens templates tant que la bascule n'est pas verifiee

## 13. Risques et points ouverts

## 13.1 Risques techniques

- casser les `sub` / `keycloak_uuid` si la migration utilisateur est mal faite
- perdre la compatibilite des redirects si `auth.cascadya.internal` change mal
- introduire un probleme TLS entre services et `Keycloak`
- rendre indisponible le Control Panel si le backchannel vers la VM Vault est mal configure

## 13.2 Risques de design

- confondre fournisseur d'identite partage et RBAC partage
- vouloir imposer trop tot le meme modele d'autorisation a `Control Panel`, `Features` et `Grafana`

## 13.3 Points ouverts a trancher

- adresse privee finale de la VM Vault a utiliser dans le DNS interne
- choix du reverse proxy sur la VM Vault
- mode de stockage des secrets `Keycloak`
- strategie exacte de migration des utilisateurs / `sub`
- hostname cible de Grafana pour une integration OIDC propre

## 14. Definition of done

La migration sera consideree reussie quand :

- `Keycloak` n'est plus heberge sur la VM Control Panel ;
- `auth.cascadya.internal` est servi par la VM Vault ;
- le Control Panel continue de fonctionner avec son RBAC local intact ;
- `cascadya_features` peut etre raccorde au meme IdP ;
- `Grafana` peut etre raccorde au meme IdP ;
- le provisioning Ansible de la VM Vault sait redeployer `Keycloak` et son stockage ;
- les secrets `Keycloak` ne vivent plus en clair dans des inventories versionnes ;
- la bascule est testee et rollbackable.

## 15. Recommandation finale

La bonne approche n'est pas de "deplacer toute l'identification du Control Panel vers Vault" au sens applicatif.

La bonne approche est :

1. centraliser `Keycloak` sur la VM Vault ;
2. conserver le `Control Panel` comme application qui gere son RBAC metier ;
3. transformer `Keycloak` en fournisseur d'identite commun ;
4. onboarder ensuite `cascadya_features` et `Grafana` comme nouveaux clients ;
5. split proprement l'Ansible pour rendre chaque VM reprovisionnable sans couplage cache.
