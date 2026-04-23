# PRD - Portal comme point d'entree unique et surface d'administration

Date de reference : 2026-04-16

## 1. Objet

Ce document decrit la cible voulue apres la migration de l'identite vers
`auth.cascadya.internal` sur la VM Vault :

- `portal.cascadya.internal` devient le point d'entree humain unique ;
- le portail devient la surface canonique pour acceder aux autres services ;
- la gestion admin aujourd'hui exposee par le Control Panel est migree vers le
  portail ;
- le `Control Panel` cesse d'etre une application d'entree generale et devient
  un microservice / backend de capacites.

L'objectif UX et architecture est simple :

- un utilisateur doit surtout se souvenir de `portal.cascadya.internal` ;
- il s'authentifie depuis le portail ;
- il lance ensuite n'importe quel service depuis le portail ;
- les autres services conservent leurs DNS natifs, mais ne sont plus l'entree
  principale de l'experience utilisateur.

## 2. Resume executif

Aujourd'hui, l'etat du SI est encore hybride :

- `portal.cascadya.internal` existe bien et joue un role de hub SSO ;
- `control-panel.cascadya.internal` expose encore :
  - sa propre page de login OIDC ;
  - sa propre navigation UI ;
  - sa propre surface admin frontend ;
  - sa propre API admin publique ;
- `features.cascadya.internal` reste une application native distincte ;
- `wazuh.cascadya.internal`, `grafana.cascadya.internal` et `auth.cascadya.internal`
  gardent leurs propres DNS et leurs propres frontaux ;
- `Keycloak` est maintenant heberge sur Vault via `auth.cascadya.internal`.

La cible de ce PRD est de faire du portail :

- le point d'entree memorisable ;
- le broker d'acces humain ;
- le frontend admin principal ;
- le backend admin public principal.

Le `Control Panel` devient alors :

- un service de capacites metier ;
- un backend prive pour les workflows, la RBAC metier et certaines operations ;
- une brique consommee par le portail, et non plus le hub principal.

## 3. Etat actuel reel

### 3.1 Portail actuel

Le portail est implemente dans le repo voisin `cascadya_main_page`.

Constats reels :

- le portail vit sur `portal.cascadya.internal` ;
- il utilise deja OIDC Keycloak ;
- il expose une session portail propre ;
- il affiche des cartes vers les outils natifs ;
- il ne reverse-proxy pas les autres services ;
- il est concu comme hub SSO, pas comme super-application monolithique.

Etat fonctionnel actuel :

- login via `portal -> auth.cascadya.internal -> portal` ;
- catalogues de cartes par sections :
  - operations
  - monitoring
  - security
  - platform
- routage serveur du portail :
  - `/auth/login`
  - `/auth/oidc/start`
  - `/auth/callback`
  - `/auth/logout`
  - `/`
  - `/operations`
  - `/monitoring`
  - `/security`
  - `/platform`
  - `/api/healthz`
  - `/api/status`
  - `/api/me`

Limite actuelle :

- le portail reste seulement un hub de liens ;
- il n'heberge pas encore la vraie gestion admin metier ;
- il ne force pas encore le passage prealable par le portail pour l'acces aux
  autres services.

### 3.2 Control Panel actuel

Le Control Panel dans `auth_prototype` expose aujourd'hui encore a la fois :

- un frontend utilisateur ;
- un frontend admin ;
- un backend metier ;
- un backend admin ;
- sa propre logique de login OIDC.

Constats reels dans le code :

- pages / routes humaines :
  - `/auth/login`
  - `/auth/oidc/start`
  - `/auth/callback`
  - `/auth/logout`
  - `/app`
  - `/admin`
  - `/ui/*`
- endpoints admin publics :
  - `GET /api/admin/audit`
  - `GET /api/admin/rbac/catalog`
  - `GET /api/admin/users`
  - `POST /api/admin/users/invite`
  - `GET /api/admin/users/{user_id}`
  - `PUT /api/admin/users/{user_id}`
  - `PUT /api/admin/users/{user_id}/roles`
  - `PUT /api/admin/users/{user_id}/status`
  - `DELETE /api/admin/users/{user_id}`

Dependances de cette surface admin :

- base locale `postgres-fastapi` pour :
  - utilisateurs miroir
  - roles
  - permissions
  - statut actif/inactif
  - audit
- API admin Keycloak pour :
  - invitation / creation d'utilisateur
  - mise a jour
  - suppression

Conclusion :

- aujourd'hui le Control Panel porte encore trop de responsabilites frontales ;
- cela contredit la cible "portal first".

### 3.3 Identite partagee actuelle

Etat confirme au 2026-04-16 :

- `Keycloak` tourne sur Vault ;
- `auth.cascadya.internal` sert bien la discovery OIDC ;
- clients confirms en base :
  - `control-panel-web`
  - `cascadya-features-web`
  - `grafana-monitoring`
  - `cascadya-portal-web`

Ce point est important :

- l'identite centralisee existe deja ;
- le client OIDC du portail est maintenant operable ;
- le chantier a faire maintenant est surtout un chantier de point d'entree, de
  surface admin et de contrats inter-services.

## 4. Probleme produit a resoudre

Problemes actuels :

- un utilisateur doit encore connaitre plusieurs URLs importantes ;
- le Control Panel reste un point d'entree concurrent du portail ;
- la surface admin est accrochee au Control Panel au lieu d'etre centralisee ;
- l'experience "un seul point de depart" n'est pas encore tenue ;
- la responsabilite "gouverner l'acces aux outils" n'est pas entierement portee
  par le portail.

Probleme cible exprime metier :

- "je veux me rappeler juste de `portal.cascadya.internal`"
- "je veux passer par le portail avant n'importe quel autre service"
- "le Control Panel devient un microservice, pas le point d'entree principal"

## 5. Principes d'architecture cibles

### 5.1 Principe cardinal

`portal.cascadya.internal` devient le point d'entree humain canonique.

### 5.2 Principe identite

`auth.cascadya.internal` reste reserve a l'identite.

Il ne devient pas un portail et ne doit pas exposer autre chose que :

- OIDC / Keycloak
- console admin Keycloak reservee aux admins IAM

### 5.3 Principe de separation

Le portail n'est pas un mega reverse proxy generique.

Il devient :

- un portail d'acces
- un broker de redirection
- un frontend admin
- un backend admin public

Mais les services natifs gardent :

- leurs DNS
- leurs frontaux
- leurs backends applicatifs

### 5.4 Principe microservice

Le `Control Panel` garde ses capacites metier, mais perd son role de porte
d'entree universelle.

Il devient une brique derriere le portail :

- backend de workflows
- backend de fleet / orchestration
- backend RBAC metier
- fournisseur de donnees / operations pour le portail admin

## 6. Architecture cible recommandee

### 6.1 Vue d'ensemble

Flux cible :

1. utilisateur ouvre `https://portal.cascadya.internal`
2. le portail verifie la session
3. si besoin, redirection vers `auth.cascadya.internal`
4. retour sur le portail
5. le portail affiche :
   - cartes services
   - et surface admin centralisee
6. toute ouverture d'un service se fait via une route portail de lancement
7. le portail redirige ensuite vers le DNS natif du service cible

### 6.2 Composants cibles

#### Portail

Le portail doit porter :

- le login humain canonique
- les pages d'entree et de navigation
- les routes de lancement vers les services
- la surface admin
- les APIs admin publiques
- la logique d'autorisation d'acces aux cartes et aux actions humaines

#### Keycloak

Keycloak reste le fournisseur d'identite partage.

Il porte :

- authentification
- session SSO
- claims / roles / groupes
- federation future si besoin

#### Control Panel

Le Control Panel doit cesser d'etre la surface admin humaine principale.

Il garde :

- logique metier
- persistance RBAC metier existante
- workflows
- endpoints internes ou semi-internes utilises par le portail

### 6.3 Regle UX forte

Le portail doit devenir la reponse par defaut a la question :

- "ou je vais pour acceder a Cascadya ?"

La reponse attendue doit etre :

- `portal.cascadya.internal`

## 7. Cible fonctionnelle detaillee

### 7.1 Portail comme hub d'acces unique

Le portail doit fournir :

- une page d'accueil authentifiee
- une navigation claire par domaines
- des cartes / launchers
- des routes de redirection controlees
- un statut d'acces clair selon les tags / roles de l'utilisateur

Nouveaux principes de navigation :

- les cartes deviennent les points de depart officiels ;
- les URLs natives restent techniques et partageables entre admins, mais ne
  sont plus l'entree recommandee ;
- les communications et runbooks doivent pointer d'abord vers le portail.

### 7.2 Portail comme surface admin principale

La gestion admin doit migrer vers le portail :

- gestion utilisateurs
- attribution / retrait de roles
- activation / desactivation
- audit de base
- visibilite RBAC

Le frontend admin cible doit donc vivre sur :

- `portal.cascadya.internal/admin/*`

Exemples de routes cibles :

- `/admin`
- `/admin/users`
- `/admin/users/{id}`
- `/admin/roles`
- `/admin/audit`
- `/admin/catalog`

### 7.3 Portail comme backend admin public

Le backend public de cette surface admin ne doit plus etre expose par le Control
Panel comme contrat principal.

Le contrat public cible devient :

- `portal.cascadya.internal/api/admin/*`

Exemples :

- `GET /api/admin/users`
- `POST /api/admin/users/invite`
- `PUT /api/admin/users/{id}`
- `PUT /api/admin/users/{id}/roles`
- `PUT /api/admin/users/{id}/status`
- `DELETE /api/admin/users/{id}`
- `GET /api/admin/rbac/catalog`
- `GET /api/admin/audit`

## 8. Strategie backend recommandee

### 8.1 Decision recommandee

La bonne cible n'est pas :

- que le portail ecrive directement dans la base `postgres-fastapi` du Control
  Panel

La bonne cible recommande est :

- un backend admin public porte par le portail ;
- un backend metier interne porte par le Control Panel ;
- un contrat inter-service explicite entre portail et Control Panel.

### 8.2 Pourquoi cette cible est la bonne

Elle permet de :

- deplacer l'experience utilisateur et l'API publique vers le portail ;
- garder la source de verite metier la ou elle est deja ;
- eviter un couplage DB dangereux entre deux applis ;
- faire du Control Panel un vrai microservice de capacites ;
- avancer par phases sans re-ecrire tout le modele RBAC d'un coup.

### 8.3 Modele cible recommande

#### Portail backend

Le portail backend devient un BFF admin / access broker.

Il porte :

- session humaine
- controle d'acces a la surface admin
- endpoints admin publics
- routes `/go/<service_key>`
- orchestration entre Keycloak et les services internes

#### Control Panel backend

Le Control Panel expose des endpoints internes dedies, par exemple :

- `/internal/admin/users`
- `/internal/admin/users/{id}`
- `/internal/admin/users/{id}/roles`
- `/internal/admin/users/{id}/status`
- `/internal/admin/audit`
- `/internal/admin/rbac/catalog`

Le portail appelle ces endpoints via :

- reseau prive
- secret de service ou mTLS a definir
- sans exposition publique directe aux utilisateurs finaux

#### Keycloak

Le portail appelle aussi directement Keycloak pour les actions identite :

- invitation / creation
- mise a jour attributs
- suppression
- verification de certains clients / mappings

### 8.4 Ce que l'on evite volontairement

- portail qui ecrit directement dans la base du Control Panel
- mega reverse proxy de tous les services dans le portail
- duplication des modeles RBAC metier dans plusieurs bases
- maintien durable de deux surfaces admin humaines concurrentes

## 9. Mode d'acces cible aux services

### 9.1 Lancement depuis le portail

Chaque service doit etre lance depuis le portail via un routeur de lancement,
par exemple :

- `/go/control-panel`
- `/go/features`
- `/go/grafana`
- `/go/wazuh`
- `/go/keycloak-admin`

Comportement attendu :

1. le portail verifie que l'utilisateur a une session
2. le portail verifie que l'utilisateur a les tags requis
3. le portail journalise l'intention de lancement si necessaire
4. le portail redirige vers le service natif

### 9.2 Acces direct a un service

Cible UX :

- si un utilisateur non authentifie arrive directement sur un service, il doit
  etre renvoye vers le portail, pas vers une experience locale concurrente

Pour le Control Panel en priorite :

- `/auth/login` ne doit plus etre la page de login recommande ;
- elle doit a terme rediriger vers :
  - `https://portal.cascadya.internal/auth/login?next=<retour_portail_ou_go_route>`

Pour les autres services :

- soit ils supportent aussi un redirect portal-first ;
- soit ils restent techniquement accessibles en direct, mais toute la
  documentation et les launchers passent par le portail.

### 9.3 Ce que "passer par le portail" veut dire ici

Cela ne veut pas dire :

- proxyfier toutes les requetes applicatives via le portail

Cela veut dire :

- authentification humaine initiale depuis le portail ;
- lancement des outils depuis le portail ;
- redirection vers le DNS natif une fois la session SSO disponible.

## 10. Impacts par composant

### 10.1 Portail

Le portail doit evoluer pour ajouter :

- surface admin HTML
- surface admin API
- routes `/go/*`
- notion de service registry canonique
- eventuelle page "access denied" plus riche par service
- eventuel catalogue dynamique a terme

### 10.2 Control Panel

Le Control Panel doit evoluer pour :

- deprecier son login humain comme point d'entree principal
- deprecier son frontend admin public
- isoler ses contrats backend internes
- garder son moteur RBAC et ses workflows metier

### 10.3 Features

`features.cascadya.internal` doit rester un outil natif, mais :

- son acces doit etre lance depuis le portail ;
- la doc et les parcours utilisateurs doivent le presenter comme une destination
  issue du portail, pas comme une URL a memoriser seule.

### 10.4 Grafana / Wazuh / Keycloak Admin

Ces outils restent natifs.

Le portail doit :

- filtrer les cartes selon les tags
- devenir le point de depart recommande
- journaliser ou au moins structurer les parcours d'acces si necessaire

## 11. Plan de migration recommande

### Phase 1 - Portal first sans casser les services

Objectif :

- faire du portail l'entree recommandee immediatement

Travaux :

- valider et stabiliser `cascadya-portal-web` dans Keycloak
- stabiliser les cartes et les tags portail
- ajouter les routes `/go/*`
- mettre a jour les docs / bookmarks / runbooks pour pointer d'abord vers le
  portail

### Phase 2 - Migration du frontend admin vers le portail

Objectif :

- sortir la surface admin humaine du Control Panel

Travaux :

- creer les pages admin portail
- reproduire les usages utiles de :
  - liste users
  - detail user
  - roles
  - statut
  - audit

### Phase 3 - Migration du backend admin public vers le portail

Objectif :

- faire du portail le contrat public d'administration

Travaux :

- introduire `/api/admin/*` sur le portail
- introduire un contrat backend interne explicite avec le Control Panel
- retirer l'exposition publique directe des endpoints admin du Control Panel
  ou les marquer comme internes

### Phase 4 - Portal-first redirects

Objectif :

- forcer le parcours humain par le portail

Travaux prioritaires :

- Control Panel :
  - rediriger `/auth/login` vers le portail
  - ne plus presenter la page locale comme porte d'entree principale
- autres services :
  - definir service par service le comportement de redirect ou de simple
    deprecation de l'acces direct

### Phase 5 - Cleanup

Objectif :

- eliminer les doubles surfaces et les ambiguities d'entree

Travaux :

- retirer ou masquer les liens UI admin locaux du Control Panel
- retirer la route legacy `auth.cascadya.internal` sur le Traefik local du
  Control Panel
- aligner les PRDs, inventaires et playbooks

## 12. Contrats techniques cibles

### 12.1 Contrat portail vers Control Panel

Contrat recommande :

- REST interne prive
- authentification de service a service
- aucune ecriture directe DB depuis le portail

Operations minimales a fournir par le Control Panel :

- lister les utilisateurs miroir
- lire le catalogue RBAC
- modifier les roles metier
- modifier l'etat actif / inactif
- lire l'audit utile a l'admin

### 12.2 Contrat portail vers Keycloak

Le portail doit pouvoir :

- provisionner un utilisateur
- mettre a jour un utilisateur
- supprimer un utilisateur
- verifier la configuration des clients necessaires

### 12.3 Contrat portail vers catalogues de services

Le portail doit disposer d'un registre de services au moins declaratif :

- cle service
- URL native
- tags requis
- section
- libelle
- mode de lancement

Exemple :

- `control-panel`
- `features`
- `grafana`
- `wazuh`
- `keycloak-admin`

## 13. Acceptance criteria

La cible est atteinte si :

- un utilisateur se souvient principalement de `portal.cascadya.internal`
- le portail est la porte d'entree recommandee pour tous les services
- la surface admin humaine n'est plus sur le Control Panel
- l'API admin publique est exposee par le portail
- le Control Panel reste operable comme microservice derriere le portail
- le login du portail passe par `auth.cascadya.internal`
- le lancement d'un service passe par le portail puis redirige vers le service
  natif
- l'acces direct non authentifie au Control Panel ne propose plus un parcours
  concurrent au portail

## 14. Risques et points de vigilance

Principaux risques :

- deplacer trop vite le frontend admin sans contrat backend interne stable
- dupliquer la logique RBAC entre portail et Control Panel
- faire du portail un proxy applicatif trop lourd
- garder deux parcours de login humains concurrents trop longtemps
- ne pas distinguer clairement :
  - identite partagee
  - acces humain
  - logique metier microservice

Point de vigilance important :

- "migrer frontend + backend admin vers le portail" ne doit pas se traduire par
  "le portail ecrit directement dans la base du Control Panel".

## 15. Decision recommandee

La bonne architecture cible est :

- `portal.cascadya.internal` comme point d'entree humain unique ;
- `auth.cascadya.internal` comme plan d'identite unique ;
- portail comme surface admin frontend ;
- portail comme backend admin public ;
- `Control Panel` comme microservice metier et backend interne ;
- lancement des autres outils via des routes portail `/go/*` puis redirection
  vers les DNS natifs ;
- suppression progressive des parcours humains concurrents sur le Control Panel.

## 16. Suite logique

Les prochains livrables recommandes sont :

1. PRD de migration du frontend admin du Control Panel vers le portail
2. PRD de contrat backend interne portail <-> control-panel
3. validation Keycloak du client `cascadya-portal-web` et de ses roles
4. patch portail pour ajouter les routes `/go/*`
5. patch control-panel pour rediriger son login humain vers le portail
