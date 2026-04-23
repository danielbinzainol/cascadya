# PRD - Portal comme point d'entree unique et surface d'administration

Date de reference : `2026-04-16`

## 1. Objet

Ce document decrit la cible voulue apres la migration de l'identite vers
`auth.cascadya.internal` sur la VM Vault :

- `portal.cascadya.internal` devient le point d'entree humain unique
- le portail devient la surface canonique pour acceder aux autres services
- la gestion admin aujourd'hui exposee par le Control Panel est migree vers le portail
- le `Control Panel` cesse d'etre une application d'entree generale et devient un microservice ou backend de capacites

L'objectif UX et architecture est simple :

- un utilisateur doit surtout se souvenir de `portal.cascadya.internal`
- il s'authentifie depuis le portail
- il lance ensuite n'importe quel service depuis le portail
- les autres services conservent leurs DNS natifs, mais ne sont plus l'entree principale de l'experience utilisateur

## 2. Resume executif

Aujourd'hui, l'etat du SI est encore hybride :

- `portal.cascadya.internal` existe bien et joue deja un role de hub SSO
- `control-panel.cascadya.internal` expose encore sa propre page de login OIDC, sa propre navigation UI et sa propre surface admin frontend
- `features.cascadya.internal` reste une application native distincte
- `wazuh.cascadya.internal`, `grafana.cascadya.internal` et `auth.cascadya.internal` gardent leurs propres DNS et leurs propres frontaux
- `Keycloak` est maintenant heberge sur Vault via `auth.cascadya.internal`

La cible de ce PRD est de faire du portail :

- le point d'entree memorisable
- le broker d'acces humain
- le frontend admin principal
- le backend admin public principal

Le `Control Panel` devient alors :

- un service de capacites metier
- un backend prive pour les workflows, la RBAC metier et certaines operations
- une brique consommee par le portail, et non plus le hub principal

## 3. Etat actuel reel

### 3.1 Portail actuel

Le portail est implemente dans le repo voisin `cascadya_main_page`.

Constats reels :

- le portail vit sur `portal.cascadya.internal`
- il utilise deja OIDC Keycloak
- il expose une session portail propre
- il affiche des cartes vers les outils natifs
- il ne reverse-proxy pas les autres services
- il est concu comme hub SSO, pas comme super-application monolithique

Etat fonctionnel actuel :

- login via `portal -> auth.cascadya.internal -> portal`
- client OIDC `cascadya-portal-web` deja cree dans le realm `cascadya-corp`
- catalogues de cartes par sections :
  - `operations`
  - `monitoring`
  - `security`
  - `platform`
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

Limites actuelles :

- le portail reste surtout un hub de liens
- il n'heberge pas encore la vraie gestion admin metier
- il n'expose pas encore les routes `/go/*`
- les cartes sont deja filtrees par roles, mais les roles metier ne sont pas encore provisionnes dans Keycloak pour les utilisateurs testes

Important :

- le probleme actuel n'est plus le login OIDC
- le probleme actuel est l'autorisation metier qui debloque les cartes

### 3.2 Control Panel actuel

Le Control Panel dans `auth_prototype` expose aujourd'hui encore a la fois :

- un frontend utilisateur
- un frontend admin
- un backend metier
- un backend admin
- sa propre logique de login OIDC

Conclusion :

- aujourd'hui le Control Panel porte encore trop de responsabilites frontales
- cela contredit la cible `portal first`

### 3.3 Identite partagee actuelle

Etat confirme au `2026-04-16` :

- `Keycloak` tourne sur Vault
- `auth.cascadya.internal` sert bien la discovery OIDC
- clients confirms en base :
  - `control-panel-web`
  - `cascadya-features-web`
  - `grafana-monitoring`
  - `cascadya-portal-web`

Ce point est important :

- l'identite centralisee existe deja
- le client portail existe deja
- le chantier immediat a faire est surtout un chantier de roles Keycloak, de point d'entree, de surface admin et de contrats inter-services

## 4. Probleme produit a resoudre

Problemes actuels :

- un utilisateur doit encore connaitre plusieurs URLs importantes
- le Control Panel reste un point d'entree concurrent du portail
- la surface admin est accrochee au Control Panel au lieu d'etre centralisee
- l'experience "un seul point de depart" n'est pas encore tenue
- la responsabilite "gouverner l'acces aux outils" n'est pas encore entierement portee par le portail
- les cartes visibles dans le portail restent bloquees faute de roles Keycloak adaptes

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

- OIDC et Keycloak
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

Le `Control Panel` garde ses capacites metier, mais perd son role de porte d'entree universelle.

Il devient une brique derriere le portail :

- backend de workflows
- backend de fleet ou orchestration
- backend RBAC metier
- fournisseur de donnees ou d'operations pour le portail admin

## 6. Cible d'autorisation immediate

### 6.1 Blocage actuel

Le portail sait deja :

- authentifier l'utilisateur
- lire les roles remontes par Keycloak
- filtrer les cartes selon ces roles

Le blocage actuel est donc :

- les roles metier attendus n'existent pas encore partout dans Keycloak
- ou ils ne sont pas encore affectes aux utilisateurs ou groupes cibles

### 6.2 Roles a creer ou confirmer dans Keycloak

Roles realm cibles :

- `portal-access`
- `portal-admin`
- `control-panel-user`
- `monitoring-user`
- `grafana-user`
- `wazuh-user`
- `security-user`

### 6.3 Politique phase 1 recommandee

Pour cette premiere phase, la priorite est de rendre le portail vraiment utilisable sans toucher encore au `Control Panel`.

Chemin recommande :

- verifier le client `cascadya-portal-web`
- creer les roles realm cibles
- affecter d'abord un jeu minimal de roles a un utilisateur de test

Jeu minimal recommande :

- `portal-access`
- `control-panel-user`
- `monitoring-user`
- `grafana-user`

Effet attendu :

- `Control Panel`
- `Features`
- `Grafana`
- `Mimir`

doivent devenir accessibles dans le portail.

### 6.4 Variante "tout ouvert" pour test rapide

Si l'objectif est un test rapide sans gerer finement les cartes, on peut attribuer temporairement :

- `portal-admin`

Consequences :

- toutes les cartes du MVP s'ouvrent
- le futur onglet admin devra aussi etre reserve a ce role
- il ne faut pas utiliser cette option comme modele durable pour tous les comptes

### 6.5 Ouverture large ulterieure si souhaite

Si, dans un second temps, vous voulez que tous les utilisateurs humains accedent aux cartes principales sans leur donner `portal-admin`, alors :

- creer un groupe Keycloak du type `portal-standard-users`
- mapper ce groupe vers les roles metier utiles
- garder un groupe distinct du type `portal-admins` pour `portal-admin`

## 7. Cible fonctionnelle detaillee

### 7.1 Portail comme hub d'acces unique

Le portail doit fournir :

- une page d'accueil authentifiee
- une navigation claire par domaines
- des cartes ou launchers
- des routes de redirection controlees a terme
- un statut d'acces clair selon les tags, roles ou groupes de l'utilisateur

Principes de navigation :

- les cartes deviennent les points de depart officiels
- les URLs natives restent techniques et partageables entre admins, mais ne sont plus l'entree recommandee
- les communications et runbooks doivent pointer d'abord vers le portail

### 7.2 Portail comme surface admin principale

La gestion admin doit migrer vers le portail :

- gestion utilisateurs
- attribution ou retrait de roles
- activation ou desactivation
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

### 7.3 Visibilite de l'onglet admin

Le futur onglet admin du portail doit etre visible seulement pour :

- `portal-admin`

Cela vaut aussi pour :

- la carte `Keycloak Admin`
- les futures pages `/admin/*`
- les futures APIs `portal.cascadya.internal/api/admin/*`

## 8. Strategie backend recommandee

### 8.1 Decision recommandee

La bonne cible n'est pas :

- que le portail ecrive directement dans la base `postgres-fastapi` du Control Panel

La bonne cible recommande est :

- un backend admin public porte par le portail
- un backend metier interne porte par le Control Panel
- un contrat inter-service explicite entre portail et Control Panel

### 8.2 Pourquoi cette cible est la bonne

Elle permet de :

- deplacer l'experience utilisateur et l'API publique vers le portail
- garder la source de verite metier la ou elle est deja
- eviter un couplage DB dangereux entre deux applis
- faire du Control Panel un vrai microservice de capacites
- avancer par phases sans re-ecrire tout le modele RBAC d'un coup

### 8.3 Modele cible recommande

#### Portail backend

Le portail backend devient un BFF admin et access broker.

Il porte :

- session humaine
- controle d'acces a la surface admin
- endpoints admin publics
- routes `/go/<service_key>` a terme
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

- invitation ou creation
- mise a jour attributs
- suppression
- verification de certains clients ou mappings

## 9. Mode d'acces cible aux services

### 9.1 Lancement depuis le portail

Chaque service doit etre lance depuis le portail via un routeur de lancement, par exemple :

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

### 9.2 Etat reel aujourd'hui

Aujourd'hui :

- les cartes existent deja
- les liens applicatifs existent deja
- les routes `/go/*` ne sont pas encore implementees
- le verrou principal reste l'autorisation Keycloak

### 9.3 Acces direct a un service

Cible UX :

- si un utilisateur non authentifie arrive directement sur un service, il doit a terme etre renvoye vers le portail, pas vers une experience locale concurrente

Pour le Control Panel en priorite :

- `/auth/login` ne doit plus etre la page de login recommandee
- elle doit a terme rediriger vers :
  - `https://portal.cascadya.internal/auth/login?next=<retour_portail_ou_go_route>`

## 10. Impacts par composant

### 10.1 Portail

Le portail doit evoluer pour ajouter :

- surface admin HTML
- surface admin API
- routes `/go/*`
- notion de service registry canonique
- eventuelle page `access denied` plus riche par service

### 10.2 Control Panel

Le Control Panel doit evoluer pour :

- deprecier son login humain comme point d'entree principal
- deprecier son frontend admin public
- isoler ses contrats backend internes
- garder son moteur RBAC et ses workflows metier

### 10.3 Features

`features.cascadya.internal` doit rester un outil natif, mais :

- son acces doit etre lance depuis le portail
- la doc et les parcours utilisateurs doivent le presenter comme une destination issue du portail, pas comme une URL a memoriser seule

### 10.4 Grafana, Wazuh et Keycloak Admin

Ces outils restent natifs.

Le portail doit :

- filtrer les cartes selon les tags
- devenir le point de depart recommande
- journaliser ou au moins structurer les parcours d'acces si necessaire

## 11. Plan de migration recommande

### Phase 1 - Deblocage Keycloak du portail

Objectif :

- rendre le portail vraiment utilisable, sans toucher encore au `Control Panel`

Travaux :

- verifier seulement le client `cascadya-portal-web`
  - `Valid redirect URIs` contient `https://portal.cascadya.internal/auth/callback`
  - `Valid post logout redirect URIs` contient `https://portal.cascadya.internal/`
  - `Standard flow` est actif
- creer ou confirmer les roles realm dans Keycloak Vault
- affecter a un utilisateur de test :
  - `portal-access`
  - `control-panel-user`
  - `monitoring-user`
  - `grafana-user`
- ou, pour un test "tout ouvert" :
  - `portal-admin`
- se deconnecter completement du portail
- se deconnecter de Keycloak si necessaire
- recharger `https://portal.cascadya.internal`
- verifier que `Control Panel`, `Features`, `Grafana` et `Mimir` sont ouverts

### Phase 2 - Portal first sans casser les services

Objectif :

- faire du portail l'entree recommandee immediatement

Travaux :

- stabiliser les cartes et les tags portail
- mettre a jour les docs, bookmarks et runbooks pour pointer d'abord vers le portail
- preparer les routes `/go/*`

### Phase 3 - Migration du frontend admin vers le portail

Objectif :

- sortir la surface admin humaine du Control Panel

Travaux :

- creer l'onglet admin portail
- creer les pages admin portail
- reproduire les usages utiles de :
  - liste users
  - detail user
  - roles
  - statut
  - audit

### Phase 4 - Migration du backend admin public vers le portail

Objectif :

- faire du portail le contrat public d'administration

Travaux :

- introduire `/api/admin/*` sur le portail
- introduire un contrat backend interne explicite avec le Control Panel
- retirer l'exposition publique directe des endpoints admin du Control Panel ou les marquer comme internes

### Phase 5 - Portal-first redirects

Objectif :

- forcer le parcours humain par le portail

Travaux prioritaires :

- Control Panel :
  - rediriger `/auth/login` vers le portail
  - ne plus presenter la page locale comme porte d'entree principale
- autres services :
  - definir service par service le comportement de redirect ou de simple deprecation de l'acces direct

## 12. Acceptance criteria

La cible est atteinte si :

- un utilisateur se souvient principalement de `portal.cascadya.internal`
- le portail est la porte d'entree recommandee pour tous les services
- les cartes principales sont debloquees pour les utilisateurs humains standards
- l'onglet admin n'est visible que pour `portal-admin`
- la surface admin humaine n'est plus sur le Control Panel
- l'API admin publique est exposee par le portail
- le Control Panel reste operable comme microservice derriere le portail
- le lancement d'un service passe a terme par le portail puis redirige vers le service natif

## 13. Risques et points de vigilance

Principaux risques :

- deplacer trop vite le frontend admin sans contrat backend interne stable
- dupliquer la logique RBAC entre portail et Control Panel
- faire du portail un proxy applicatif trop lourd
- garder deux parcours de login humains concurrents trop longtemps
- ne pas distinguer clairement identite partagee, acces humain et logique metier microservice

Point de vigilance important :

- "migrer frontend + backend admin vers le portail" ne doit pas se traduire par "le portail ecrit directement dans la base du Control Panel"

## 14. Decision recommandee

La bonne architecture cible est :

- `portal.cascadya.internal` comme point d'entree humain unique
- `auth.cascadya.internal` comme plan d'identite unique
- portail comme surface admin frontend
- portail comme backend admin public
- `Control Panel` comme microservice metier et backend interne
- lancement progressif des autres outils via des routes portail `/go/*` puis redirection vers les DNS natifs
- suppression progressive des parcours humains concurrents sur le Control Panel

## 15. Suite logique

Les prochains livrables recommandes sont :

1. appliquer le bootstrap des roles Keycloak sur Vault pour debloquer les cartes
2. PRD de migration du frontend admin du Control Panel vers le portail
3. PRD de contrat backend interne portail `<->` Control Panel
4. patch portail pour ajouter l'onglet admin
5. patch portail pour ajouter les routes `/go/*`
6. patch Control Panel pour rediriger son login humain vers le portail
