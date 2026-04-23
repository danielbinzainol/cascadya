# PRD - Frontend Control Panel - Vue 3, stack retenue et plan technique

## 1. Objet

Ce document fixe la decision frontend pour le Control Panel apres la stabilisation du socle IAM et avant l'implementation du lot 3 `sites` / `inventory`.

Il couvre dans un meme document :

- le framework frontend retenu ;
- la stack technique choisie ;
- les raisons de ce choix ;
- la strategie d'integration avec `FastAPI` ;
- le plan technique de mise en oeuvre.

## 2. Decision retenue

Le framework retenu pour le frontend applicatif du Control Panel est :

- `Vue 3`

Le mode d'architecture retenu est :

- `SPA` (Single Page Application) ;
- build via `Vite` ;
- servie sur le meme domaine que `FastAPI` ;
- authentication conservee cote backend via session cookie et routes `/auth/*`.

Le choix n'est pas :

- ni un frontend SSR type `Nuxt` ;
- ni une application `React / Next.js` ;
- ni une simple continuation du server-rendered `Jinja` pour toute l'application.

## 3. Pourquoi Vue 3

### 3.1 Adequation au produit

Le Control Panel est :

- une application interne ;
- accessible derriere `WireGuard` ;
- sans besoin SEO ;
- basee sur des ecrans metier de type dashboard, tableaux, formulaires, fiches detail et vues d'administration.

Dans ce contexte, `Vue 3` est pertinent car il permet :

- une montee en puissance rapide ;
- une prise en main simple pour une equipe backend-first ;
- une ecriture claire des composants ;
- une bonne ergonomie pour les ecrans d'administration.

### 3.2 Adequation a l'architecture actuelle

Le backend existe deja :

- `FastAPI`
- `OIDC`
- sessions serveur
- cookies
- endpoints `/api/*`
- pages HTML actuelles en `Jinja`

Le frontend n'a donc pas besoin d'un framework qui remplace le backend web. Il a besoin d'un framework qui :

- consomme proprement les APIs existantes ;
- coexiste avec `FastAPI` ;
- n'impose pas un second serveur applicatif complexe en production.

### 3.3 Productivite

`Vue 3` offre un excellent compromis entre :

- lisibilite ;
- vitesse de prototypage ;
- maintenabilite ;
- qualite des composants UI.

Pour un control panel prive, cet equilibre est meilleur que de rajouter un framework plus lourd ou plus opinionne.

## 4. Pourquoi ne pas retenir les autres options

### 4.1 Pourquoi pas Nuxt

`Nuxt` n'est pas retenu a ce stade car :

- le SEO n'apporte rien sur une application privee sous VPN ;
- le SSR ajoute une couche serveur frontend inutile ;
- l'auth est deja geree par `FastAPI` ;
- le besoin principal est une SPA d'outillage, pas un site public ou hybride contenu / app.

### 4.2 Pourquoi pas React / Next.js

`React` ou `Next.js` ne sont pas retenus comme premier choix car :

- la base produit actuelle est plus proche d'un panel admin que d'un produit web public ;
- `Vue` est plus directe pour demarrer vite sur tableaux, filtres, details et formulaires ;
- `Next.js` reintroduirait un besoin serveur frontend peu utile dans l'etat actuel.

### 4.3 Pourquoi pas HTMX / Alpine seulement

`HTMX` ou `Alpine` seuls ne sont pas retenus comme solution cible car :

- ils prolongent bien un rendu serveur simple ;
- mais ils deviennent moins confortables quand l'application grossit en navigation, etat UI, tables filtrees, vues detail, stores et pages multi-modules ;
- le lot 3 `sites / inventory` justifie deja une vraie couche frontend applicative.

Ils peuvent rester utiles ponctuellement pour de petits ecrans server-rendered, mais pas comme base du frontend principal.

## 5. Stack frontend retenue

### 5.1 Coeur

- `Vue 3`
- `TypeScript`
- `Vite`
- `Vue Router`
- `Pinia`

### 5.2 Data fetching et synchronisation API

- `@tanstack/vue-query`

Raison :

- gestion propre des etats `loading / success / error`
- cache local simple
- invalidation apres mutation
- bonne ergonomie pour listes, details et formulaires admin

### 5.3 Validation et contrats frontend

- `zod`

Raison :

- validation des payloads frontend ;
- controle des reponses API si besoin ;
- schemas reutilisables pour formulaires `sites`, `inventory filters`, `admin user edit`.

### 5.4 Dates et formatting

- `dayjs`

Raison :

- formatage simple de `last_login_at`, `last_seen_at`, `scan started_at`, `scan finished_at`.

### 5.5 Styling

Le choix retenu est :

- `CSS variables`
- `component-scoped CSS`
- un petit design system interne

Le choix non retenu par defaut est :

- un framework UI lourd ;
- une dependance totale a un kit visuel externe ;
- un rendu generique type dashboard bootstrapise.

L'objectif visuel est :

- une interface propre ;
- nette ;
- technique ;
- moderne ;
- mais pas interchangeable ni generique.

### 5.6 Client HTTP

Le choix retenu est :

- `fetch` natif encapsule dans un petit client maison

Pas de dependance `axios` au depart, pour garder la stack legere et parce que :

- l'application sera en same-origin ;
- le backend expose deja des endpoints simples ;
- les cookies de session pourront etre reutilises sans mecanisme exotique.

## 6. Architecture frontend / backend cible

## 6.1 Repartition des responsabilites

### Backend `FastAPI`

`FastAPI` reste responsable de :

- `OIDC`
- `session cookie`
- `RBAC`
- logique metier
- routes `/api/*`
- routes `/auth/*`
- checks de sante

### Frontend `Vue`

Le frontend `Vue` devient responsable de :

- navigation applicative ;
- rendu des ecrans metier ;
- experience utilisateur ;
- consommation des APIs ;
- gestion de l'etat UI ;
- gestion de filtres, tableaux, formulaires et transitions de pages.

## 6.2 Same-origin

Le frontend doit rester sur le meme origin que le backend :

- `https://control-panel.cascadya.internal`

Raison :

- reutiliser les cookies de session existants ;
- eviter le bruit CORS ;
- garder une architecture simple ;
- limiter les effets de bord autour de l'auth.

## 6.3 Routing cible

Le backend conserve :

- `/auth/login`
- `/auth/oidc/start`
- `/auth/callback`
- `/auth/logout`
- `/api/*`
- `/healthz`
- `/healthz/db`

Le frontend Vue prendra progressivement en charge :

- `/app`
- `/admin`
- `/sites`
- `/sites/:id`
- `/inventory`
- `/inventory/assets/:id`

## 6.4 Strategie de transition

Pour reduire le risque, la transition recommandee est en deux temps.

### Phase initiale sous `/ui`

Monter d'abord le frontend Vue sous un namespace dedie :

- `/ui`

Exemples :

- `/ui/app`
- `/ui/admin`
- `/ui/sites`
- `/ui/inventory`

Cela permet :

- de developper sans casser les pages Jinja actuelles ;
- de comparer ancien et nouveau rendu ;
- de valider la consommation API avant le basculement.

### Phase de bascule

Une fois la parite fonctionnelle atteinte :

- `/app` redirige vers ou sert l'application Vue ;
- `/admin` idem ;
- les pages Jinja residuelles ne restent que pour `/auth/*` et eventuels ecrans de fallback.

## 7. Structure de projet recommandee

Le frontend doit etre ajoute dans un dossier dedie au repo actuel :

```text
auth_prototype/
  frontend/
    package.json
    vite.config.ts
    tsconfig.json
    index.html
    src/
      main.ts
      App.vue
      router/
        index.ts
      api/
        client.ts
        auth.ts
        users.ts
        sites.ts
        inventory.ts
      stores/
        app.ts
        session.ts
      layouts/
        AppShell.vue
        AuthLayout.vue
      components/
        ui/
        layout/
        tables/
        forms/
        states/
      modules/
        dashboard/
        admin/
        sites/
        inventory/
      styles/
        tokens.css
        base.css
        utilities.css
```

## 8. Organisation fonctionnelle du frontend

Le frontend doit etre decoupe par domaines metier et non par type technique uniquement.

Modules cibles :

- `dashboard`
- `admin`
- `sites`
- `inventory`
- plus tard :
  - `provisioning`
  - `audit`

Chaque module doit contenir :

- pages ;
- composants locaux ;
- requetes API ;
- schemas de validation ;
- types utiles.

## 9. Strategie d'authentification frontend

Le frontend ne doit pas reimplementer OIDC.

Le principe retenu est :

- le login reste un flux backend ;
- la SPA appelle `GET /api/me` au chargement ;
- si `401`, redirection vers `/auth/login` ;
- si `403`, affichage d'un ecran d'acces refuse ;
- si `200`, hydration du store session.

Cela garde une seule source de verite pour l'authentification :

- `FastAPI`

## 10. Strategie de donnees frontend

### 10.1 Source de verite metier

La source de verite metier reste le backend via `/api/*`.

Le frontend ne duplique pas la logique d'autorisation. Il :

- lit le profil courant ;
- lit les donnees metier ;
- adapte l'UI selon les permissions exposees.

### 10.2 Gestion des mutations

Le frontend doit :

- appeler les endpoints backend ;
- invalider les caches `vue-query` concernes ;
- afficher des messages de succes / erreur ;
- ne pas deviner la logique metier cote client.

## 11. Choix UX et design system

Le frontend doit viser une apparence :

- serieuse ;
- industrielle ;
- haut de gamme ;
- lisible ;
- efficace en exploitation.

Lignes directrices :

- un shell applicatif fort ;
- une navigation laterale claire ;
- des tables lisibles ;
- des cartes detail bien structurees ;
- des badges d'etat explicites ;
- des vues vides utiles ;
- des erreurs comprehensibles.

Le design system doit inclure des composants de base :

- button
- input
- select
- textarea
- badge
- card
- table
- modal
- toast
- empty state
- loading state

## 12. Plan technique de mise en oeuvre

## 12.1 Phase 0 - Decision et cadrage

- valider `Vue 3 + Vite + TypeScript`
- valider la strategie same-origin
- valider le namespace applicatif `/ui`
- figer ce document

## 12.2 Phase 1 - Socle frontend

Livrables :

- scaffold `frontend/`
- `Vite`
- `Vue Router`
- `Pinia`
- `vue-query`
- `zod`
- shell applicatif
- page `Not Found`
- page `Unauthorized`
- page `Loading`

Objectif :

- avoir un frontend compilable, navigable, et structure pour la suite.

## 12.3 Phase 2 - Integration backend minimale

Livrables :

- client `fetch` centralise
- gestion uniforme des erreurs HTTP
- bootstrap session via `GET /api/me`
- route guards frontend
- mapping des permissions dans le store session

Objectif :

- prouver que la SPA peut vivre sur le socle auth existant sans reouvrir le sujet OIDC.

## 12.4 Phase 3 - Premier apercu visuel

Livrables :

- `AppShell`
- menu lateral
- header utilisateur
- dashboard Vue branche sur des donnees reelles ou semi-reelles
- admin Vue branche sur `/api/admin/users`

Objectif :

- obtenir un premier apercu produit moderne sans attendre tout le lot 3.

## 12.5 Phase 4 - Module Sites

Livrables :

- page liste des sites
- page detail site
- formulaires create / edit
- statut actif / inactif
- enforcement frontend des permissions `site:read` et `site:write`

Objectif :

- brancher le premier module metier structure.

## 12.6 Phase 5 - Module Inventory

Livrables :

- page liste des assets
- filtres
- page detail asset
- page liste des scans
- action `request scan`
- enforcement frontend des permissions `inventory:read` et `inventory:scan`

Objectif :

- donner une vraie utilite operationnelle au Control Panel.

## 12.7 Phase 6 - Packaging et deploiement

Livrables :

- build `npm run build`
- integration du `dist/` dans le deploiement
- service par `FastAPI` ou depot statique devant `Traefik`
- adaptation Ansible

Recommandation de depart :

- premier temps : `FastAPI` sert les assets statiques du build
- deuxieme temps seulement si necessaire : service statique dedie

## 13. Strategie de deploiement recommandee

Le chemin le plus simple est :

- developpement local avec `Vite dev server`
- build de production via `npm run build`
- copie du `dist/` sur la VM
- service du bundle par le backend `FastAPI`

Cela evite d'ajouter :

- un `nginx` dedie ;
- un conteneur frontend supplementaire ;
- une complexite Traefik additionnelle trop tot.

## 14. Risques et mesures de maitrise

### 14.1 Coexistence Jinja / Vue

Risque :

- confusion entre anciennes pages et nouvelles routes.

Mesure :

- phase initiale sous `/ui` ;
- migration progressive ;
- suppression des pages Jinja seulement apres validation.

### 14.2 Auth et cookies

Risque :

- erreurs de comportement si le frontend tente de gerer lui-meme OIDC.

Mesure :

- ne pas dupliquer OIDC dans Vue ;
- laisser `FastAPI` gerer login, callback et logout.

### 14.3 Explosion de la complexite frontend

Risque :

- trop de librairies trop vite ;
- dette sur le design system.

Mesure :

- stack volontairement compacte ;
- pas de gros framework UI au depart ;
- modules par domaine metier.

### 14.4 Rupture de deploiement

Risque :

- build frontend non livre ou routes cassees.

Mesure :

- garder les routes backend de sante ;
- integrer le frontend au playbook de facon incrementale ;
- faire la bascule finale seulement apres validation fonctionnelle sous `/ui`.

## 15. Definition of Done du socle frontend

Le socle frontend sera considere atteint quand :

- le projet `Vue 3` compile ;
- il tourne en local ;
- il consomme `GET /api/me` ;
- il gere `401` et `403` proprement ;
- il affiche un `AppShell` credible ;
- il expose un premier apercu de `dashboard`, `admin`, `sites` et `inventory` ;
- il reste coherent avec l'architecture `FastAPI + OIDC + sessions cookies`.

## 16. Recommendation finale

Le choix recommande pour le Control Panel est :

- `Vue 3`
- `Vite`
- `TypeScript`
- `Vue Router`
- `Pinia`
- `@tanstack/vue-query`
- `zod`
- `dayjs`
- `fetch` natif encapsule
- `CSS variables + scoped CSS + design system interne`

Le mode recommande est :

- SPA same-origin ;
- auth geree par `FastAPI` ;
- mise en service initiale sous `/ui` ;
- bascule progressive des ecrans metier ensuite.

## 17. Suite immediate

La suite technique naturelle apres ce document est :

1. scaffold `auth_prototype/frontend/`
2. mettre en place le shell Vue
3. brancher `GET /api/me`
4. maqueter `dashboard / admin / sites / inventory`
5. seulement ensuite brancher le vrai lot 3 data model et APIs `sites / inventory`
