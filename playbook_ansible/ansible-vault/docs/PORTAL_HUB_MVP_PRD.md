# PORTAL_HUB_MVP_PRD

## 1. Objet

Ce document cadre un MVP de portail d'entree applicatif apres authentification Keycloak.

Le but est d'offrir une page centrale, hebergee sur la VM `control-panel-DEV1-S`, qui presente les services Cascadya disponibles apres login :

- `control-panel`
- `features`
- `grafana`
- `wazuh`
- `mimir`
- autres services a venir

Le Keycloak partage reste heberge sur `vault-DEV1-S` et continue d'etre publie sur `https://auth.cascadya.internal`.

## 2. Contexte actuel

Etat deja en place :

- `Keycloak` partage tourne sur `vault-DEV1-S`
- realm actif : `cascadya-corp`
- endpoint public de reference : `https://auth.cascadya.internal`
- `control-panel-web` est deja recable vers ce Keycloak
- des clients existent deja pour `control-panel-web`, `cascadya-features-web`, `grafana-monitoring` et `cascadya-portal-web`
- le portail est deja deploye sur `control-panel-DEV1-S` et publie sur `https://portal.cascadya.internal`
- le flux OIDC du portail fonctionne deja de bout en bout
- le portail cree bien sa session applicative apres retour Keycloak
- le filtrage des cartes par roles et tags est deja actif
- le blocage restant porte sur l'absence de roles metier portail sur les comptes utilisateurs testes

Contrainte structurante :

- le portail peut continuer d'etre developpe ailleurs, mais il est heberge sur la VM `control-panel-DEV1-S`

## 3. Vision produit MVP

Un utilisateur se connecte une fois via Keycloak, puis arrive sur un portail central qui :

- affiche les applications accessibles
- donne un point d'entree clair vers chaque outil
- peut afficher des sections ou sous-pages par domaine fonctionnel
- n'embarque pas les applications dans la page pour ce premier lot

Le portail est donc un hub de navigation SSO, pas une super-application qui integre toutes les UIs dans un seul frontend.

## 4. Resultat attendu pour l'utilisateur

Parcours cible :

1. l'utilisateur ouvre le portail
2. si besoin, le portail le redirige vers Keycloak
3. apres authentification, Keycloak le renvoie vers le portail
4. le portail affiche les cartes et sections autorisees pour cet utilisateur
5. un clic sur une carte ouvre l'application cible, qui reutilise la meme session Keycloak

Parcours directs a conserver :

- si l'utilisateur tape `https://control-panel.cascadya.internal`, il arrive directement sur le `control-panel`
- si l'utilisateur tape `https://grafana.cascadya.internal`, il arrive directement sur `grafana`
- si l'utilisateur tape le DNS du portail, il arrive sur la page centrale

## 5. Decision d'architecture recommandee

### Recommandation principale

Ne pas faire de `auth.cascadya.internal` la page d'entree metier.

A la place :

- `auth.cascadya.internal` reste reserve a l'identite
- le portail a son propre DNS et son propre client OIDC
- les applications gardent leurs DNS et leurs clients OIDC

Cette separation est la plus propre pour le MVP, car elle evite de melanger :

- l'interface d'authentification
- l'administration Keycloak
- les callbacks OIDC
- la navigation utilisateur vers les outils

### Pourquoi ne pas rediriger globalement Keycloak vers le portail ?

Ce serait tentant, mais ce n'est pas le bon niveau de responsabilite.

Risques :

- casser certains usages d'administration Keycloak
- compliquer les endpoints `/realms`, `/admin`, `/resources`
- rendre la plateforme moins lisible
- introduire des cas particuliers dans `nginx` ou dans un theme Keycloak

Conclusion MVP :

- on laisse `Keycloak` jouer uniquement son role d'IdP
- on fait du portail le point d'entree humain par convention produit et DNS

## 6. Proposition de DNS et de routage

### DNS recommandes

- `auth.cascadya.internal` : Keycloak partage sur la VM Vault
- `portal.cascadya.internal` : portail central heberge sur la VM Control Panel
- `control-panel.cascadya.internal` : Control Panel
- `features.cascadya.internal` : Features
- `grafana.cascadya.internal` : Grafana
- `wazuh.cascadya.internal` : Wazuh
- `mimir.cascadya.internal` : Mimir ou point d'entree associe

### Routage recommande pour le portail

Le portail lui-meme peut exposer :

- `/` : page d'accueil
- `/operations` : acces Control Panel, Features, outils operationnels
- `/monitoring` : acces Grafana, Mimir, outils d'observabilite
- `/security` : acces Wazuh, Vault si souhaite
- `/platform` : acces techniques ou administratifs

### Strategie recommandee pour les applications

Pour le MVP, chaque application garde son propre domaine et sa propre UI.

Le portail :

- ne reverse-proxy pas les autres applications
- ne les embarque pas en iframe
- ne remplace pas leurs routes
- ne fait que presenter des cartes, liens et metadonnees d'acces

Cette approche evite les problemes de :

- cookies inter-applications
- CSP / X-Frame-Options
- logout central trop intrusif
- debugging reseau complique

## 7. Proposition de flux d'authentification

### Portail

Le portail doit avoir son propre client OIDC, par exemple :

- client id : `cascadya-portal-web`
- redirect URI : `https://portal.cascadya.internal/auth/callback`
- post logout redirect URI : `https://portal.cascadya.internal/`

Comportement :

- si l'utilisateur arrive non authentifie, le portail declenche un login OIDC
- apres login, Keycloak renvoie vers `portal.cascadya.internal`
- le portail consomme les claims minimales, cree sa session, puis affiche la page hub ou un ecran d'acces refuse si les roles metier attendus manquent

### Applications cibles

Chaque application garde son propre client OIDC.

Exemples deja existants ou attendus :

- `control-panel-web`
- `cascadya-features-web`
- `grafana-monitoring`
- un futur client `wazuh-web` si necessaire
- un futur client `mimir-web` ou un autre client si `Mimir` n'a pas de UI directe exploitable

Important :

- si `Mimir` n'a pas de vraie interface utilisateur finale, le portail ne doit pas faire semblant
- dans ce cas, la carte `Mimir` doit pointer vers la bonne interface operable, souvent `Grafana` ou une page documentaire technique

## 8. Redirection "apres login"

### Comportement recommande

Le "redirect directly to this page" doit etre obtenu ainsi :

- l'utilisateur commence sur `portal.cascadya.internal`
- le portail envoie vers Keycloak
- Keycloak revient naturellement vers le portail via `redirect_uri`

Autrement dit :

- on ne configure pas Keycloak pour rediriger tous les logins vers le portail
- on fait du portail le premier URL utilisateur a utiliser

### Option secondaire plus tard

Si un jour on veut que `https://auth.cascadya.internal/` affiche une experience plus orientee produit, il faudra le traiter comme un lot separe, avec un arbitrage explicite sur :

- la page d'accueil Keycloak
- la console d'admin
- les endpoints techniques
- le theme ou les regles `nginx`

Ce n'est pas recommande pour le MVP.

## 9. Contenu fonctionnel MVP du portail

### MVP minimum

La page d'accueil doit afficher :

- nom du produit ou de la plateforme
- nom de l'utilisateur connecte
- cartes vers les applications
- description courte de chaque outil
- badge d'environnement si utile
- bouton logout

### Sous-pages MVP

Sous-pages deja presentes ou ciblees pour le MVP :

- une page `home`
- une page `operations`
- une page `monitoring`
- une page `security`
- une page `platform`

Chaque sous-page peut rester tres simple :

- titre
- quelques cartes
- lien retour accueil

## 10. Gestion des droits et de la visibilite

La checklist operationnelle cote Keycloak pour ce sujet est detaillee dans `docs/PORTAL_KEYCLOAK_CHECKLIST_PRD.md`.

La trajectoire d'architecture `portal first` avec futur onglet admin et migration progressive de la surface admin est detaillee dans `docs/PORTAL_POINT_ENTREE_ADMIN_PRD.md`.

Le portail ne doit pas afficher la meme chose a tout le monde sans nuance.

Recommandation MVP :

- filtrer les cartes selon les roles ou groupes Keycloak
- conserver un mapping simple `role -> cartes visibles`
- commencer en phase 1 par debloquer les cartes via Keycloak, sans toucher encore au `Control Panel`

Exemples de roles possibles :

- `portal-access`
- `portal-admin`
- `control-panel-user`
- `monitoring-user`
- `grafana-user`
- `wazuh-user`

Pour la phase 1 immediate :

- test minimal : `portal-access`, `control-panel-user`, `monitoring-user`, `grafana-user`
- test "tout ouvert" : `portal-admin`

Le portail peut alors :

- cacher une carte si le role manque
- afficher une carte en lecture seule si besoin
- afficher une section admin seulement a certains profils
- reserver le futur onglet admin portail a `portal-admin`

## 11. Hebergement sur la VM Control Panel

Le portail etant heberge sur `control-panel-DEV1-S`, il est recommande de :

- lui donner un vhost ou route dediee
- ne pas le melanger au code runtime du `control-panel` si ce n'est pas necessaire
- preferer un service distinct, meme s'il tourne sur la meme VM

Deux options raisonnables :

### Option A - DNS dedie

- `portal.cascadya.internal` pointe vers `control-panel-DEV1-S`
- service portail distinct
- meilleur decouplage

C'est l'option recommandee.

### Option B - Sous-chemin du Control Panel

- exemple : `https://control-panel.cascadya.internal/portal`

Inconvenients :

- couplage fort avec le `control-panel`
- confusion entre produit `control-panel` et produit `portal`
- evolution plus difficile

Cette option n'est pas recommandee pour le MVP si un DNS dedie est possible.

## 12. Routing UX recommande

### Recommandation simple

- `portal.cascadya.internal/` = hub general
- `portal.cascadya.internal/operations` = operations
- `portal.cascadya.internal/monitoring` = monitoring
- `portal.cascadya.internal/security` = security

Chaque carte ouvre l'application cible sur son domaine natif.

### Pourquoi c'est mieux qu'un mega reverse proxy

Parce que cela :

- garde chaque application responsable de son auth et de ses routes
- minimise le travail d'infrastructure du MVP
- limite les regressions
- rend les migrations futures plus simples

## 13. Securite et contraintes

- le certificat de `auth.cascadya.internal` est actuellement auto-signe
- le portail devra donc soit :
  - faire confiance a ce certificat
  - soit desactiver temporairement la verification TLS si sa stack le permet
- ce contournement doit rester temporaire
- en DEV, le portail fonctionne actuellement avec verification TLS desactivee cote OIDC

Points de vigilance :

- ne pas stocker de `client_secret` dans le repo
- ne pas faire porter au portail les credentials des autres apps
- ne pas tenter de mutualiser les sessions applicatives par bricolage frontend

## 14. Hors scope MVP

- federation d'identite supplementaire
- portail qui embarque les UIs tierces
- recherche transverse entre applications
- provisioning complet des roles, groupes et affectations Keycloak
- gestion fine des permissions applicatives depuis le portail
- theme Keycloak transforme en portail produit

## 15. Criteres d'acceptation MVP

Le MVP est considere comme atteint si :

- un utilisateur ouvre `https://portal.cascadya.internal`
- il est redirige vers Keycloak si non connecte
- apres login, il revient sur le portail
- le portail affiche les cartes attendues
- un clic sur `control-panel`, `grafana` ou `features` ouvre bien l'application cible
- ces applications reutilisent la session Keycloak existante sans nouveau login manuel dans le cas nominal

## 16. Etat d'avancement au `2026-04-16`

### Deja realise

- PRD portail cree
- DNS portail retenu : `portal.cascadya.internal`
- client Keycloak `cascadya-portal-web` cree dans `cascadya-corp`
- portail expose sur `control-panel-DEV1-S`
- login OIDC integre et fonctionnel
- session portail creee apres callback
- navigation principale visible
- filtrage des cartes par roles et tags deja branche

### Reste a finaliser pour clore le MVP technique

- creer ou confirmer les roles realm metier dans Keycloak
- attribuer les bons roles a au moins un compte utilisateur de test
- verifier l'ouverture effective des cartes `Control Panel`, `Features`, `Grafana` et `Mimir`
- automatiser ensuite, si souhaite, les roles et groupes Keycloak dans Ansible
- tourner le `client_secret` temporaire du portail apres validation

## 17. Recommandations finales

Pour ce MVP, le meilleur compromis est :

- Keycloak sur la VM Vault reste un service d'identite pur
- un portail dedie tourne sur la VM Control Panel
- le portail a un DNS dedie, recommande : `portal.cascadya.internal`
- les applications gardent leurs DNS natifs
- les utilisateurs commencent sur le portail, pas sur `auth.cascadya.internal`

Cette approche minimise le risque d'infrastructure tout en donnant tres vite une experience "main page" claire et evolutive.
