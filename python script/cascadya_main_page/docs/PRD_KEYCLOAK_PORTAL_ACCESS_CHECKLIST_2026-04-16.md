# PRD - Checklist Keycloak pour le portail Cascadya

## 1. Objet

Ce document cadre les modifications a appliquer dans Keycloak, heberge sur `vault-DEV1-S`, pour rendre le portail `portal.cascadya.internal` pleinement exploitable apres authentification.

Le but n'est pas de refaire l'authentification elle-meme, qui fonctionne deja, mais de finaliser la partie autorisation:

- acces au portail
- visibilite des cartes
- ouverture des services cibles selon les roles metier

## 2. Etat actuel constate

Le portail est deja deploye sur `control-panel-DEV1-S` et publie via Traefik sur `portal.cascadya.internal`.

Ce qui fonctionne deja:

- redirection OIDC vers Keycloak
- callback `https://portal.cascadya.internal/auth/callback`
- creation de session portail
- lecture des claims Keycloak
- filtrage des cartes par tags / roles / groupes

Constat actuel sur un compte utilisateur reel:

- l'utilisateur se connecte correctement
- le portail recupere des roles standards Keycloak:
  - `default-roles-cascadya-corp`
  - `manage-account`
  - `manage-account-links`
  - `offline_access`
  - `uma_authorization`
  - `view-profile`
- aucune carte metier ne s'ouvre car aucun role metier du portail n'est encore assigne

Conclusion:

- l'authentification est OK
- la projection des claims est OK
- le manque porte sur l'attribution des roles metier dans Keycloak

## 3. Perimetre des changements a faire sur Vault

Les actions attendues se limitent a Keycloak dans le realm `cascadya-corp`.

Le portail ne demande pas:

- de changement d'architecture
- de changement de DNS
- de changement de backend applicatif
- de changement de flux OIDC

Le besoin est:

- verifier le client `cascadya-portal-web`
- creer ou confirmer les roles realm utilises par le portail
- attribuer ces roles aux utilisateurs ou groupes
- relancer une connexion utilisateur pour verifier les cartes

## 4. Modele d'autorisation cible pour le MVP

### 4.1 Regle globale d'entree portail

Le portail supporte une garde globale configurable via:

- `PORTAL_REQUIRED_TAGS`

La valeur recommandee pour le mode cible est:

- `portal-access,portal-admin`

Cela veut dire:

- un utilisateur avec `portal-access` entre dans le portail
- un utilisateur avec `portal-admin` entre aussi

### 4.2 Regles par carte

Les cartes sont filtrees individuellement.

Mapping actuel:

- `Control Panel`
  - roles attendus: `control-panel-user` ou `portal-admin`
- `Features`
  - roles attendus: `control-panel-user` ou `portal-admin`
- `Grafana`
  - roles attendus: `grafana-user` ou `monitoring-user` ou `portal-admin`
- `Mimir`
  - roles attendus: `monitoring-user` ou `portal-admin`
- `Wazuh`
  - roles attendus: `wazuh-user` ou `security-user` ou `portal-admin`
- `Keycloak Admin`
  - roles attendus: `portal-admin`

## 5. Strategie recommandee cote Keycloak

Pour ce MVP, la strategie la plus simple et la plus robuste est:

- utiliser des `realm roles`
- attribuer ces roles directement aux utilisateurs ou a des groupes
- conserver les groupes comme mecanisme optionnel d'agragation

Pourquoi ce choix:

- le portail recoit deja correctement les `realm_access.roles`
- les `default-roles-*` remontent deja dans les claims
- il y a moins de variables qu'avec une logique basee d'abord sur les groupes

## 6. Checklist de modification dans Keycloak

### 6.1 Verifier le realm

- ouvrir `https://auth.cascadya.internal/admin/`
- se connecter a la console d'administration Keycloak
- selectionner le realm `cascadya-corp`

### 6.2 Verifier le client OIDC du portail

Dans `Clients`, verifier l'existence du client:

- `cascadya-portal-web`

Verifier au minimum:

- `Client authentication`: active si le portail utilise un `client_secret`
- `Standard flow`: active
- `Direct access grants`: desactive si inutile
- `Valid redirect URIs`:
  - `https://portal.cascadya.internal/auth/callback`
- `Valid post logout redirect URIs`:
  - `https://portal.cascadya.internal/`
  - ou plus souplement `https://portal.cascadya.internal/*`
- `Web origins`:
  - `https://portal.cascadya.internal`
  - ou `+` si vous conservez la config Keycloak par defaut pour ce MVP

### 6.3 Verifier la projection des roles dans les tokens

Verifier que les roles realm sont bien exposes.

Bonne nouvelle:

- ce point semble deja OK, car les `default-roles-cascadya-corp` remontent deja dans le portail

Verification attendue:

- les `realm roles` apparaissent apres login
- idealement dans `access token`
- et si possible aussi via `userinfo`

### 6.4 Creer les roles realm metier si absents

Dans `Realm roles`, creer si besoin:

- `portal-access`
- `portal-admin`
- `control-panel-user`
- `monitoring-user`
- `grafana-user`
- `wazuh-user`
- `security-user`

### 6.5 Attribuer les roles a l'utilisateur de test

Pour debloquer rapidement le compte de test de `Daniel Bin Zainol`, deux options raisonnables:

Option minimale:

- `portal-access`
- `control-panel-user`
- `monitoring-user`
- `grafana-user`

Option large pour administration du MVP:

- `portal-admin`

Recommandation:

- commencer par l'option minimale
- reserver `portal-admin` aux comptes d'administration plateforme

### 6.6 Variante par groupes si souhaite

Si vous preferez une gestion par groupes:

- creer un groupe portail ou metier
- attribuer les `realm roles` aux groupes
- ajouter l'utilisateur dans les groupes

Exemple:

- groupe `portal-users` -> role `portal-access`
- groupe `monitoring-users` -> roles `monitoring-user`, `grafana-user`
- groupe `control-panel-users` -> role `control-panel-user`

Important:

- meme avec une strategie groupes, il reste recommande de s'appuyer sur des `realm roles`
- les groupes servent surtout de mecanisme d'affectation, pas de contrat technique principal

## 7. Sequence de validation apres modification

### 7.1 Cote Keycloak

- verifier que le compte utilisateur porte bien les nouveaux roles

### 7.2 Cote portail

- se deconnecter du portail
- supprimer la session navigateur si necessaire
- relancer une connexion via `https://portal.cascadya.internal`

### 7.3 Resultat attendu

Avec un compte portant:

- `portal-access`
- `control-panel-user`
- `monitoring-user`
- `grafana-user`

Le portail doit afficher au minimum:

- `Control Panel`
- `Features`
- `Grafana`
- `Mimir`

Et ne doit pas afficher comme ouvertes:

- `Wazuh`
- `Keycloak Admin`

Avec un compte portant:

- `portal-admin`

Le portail doit afficher toutes les cartes du MVP.

## 8. Criteres d'acceptation

Le lot Keycloak est considere comme termine si:

- le client `cascadya-portal-web` est valide
- les roles metier du portail existent dans `cascadya-corp`
- un utilisateur de test recupere les bons roles apres login
- le portail n'affiche plus seulement les `default-roles-*`
- au moins une carte metier devient ouverte pour l'utilisateur
- le comportement de filtrage des cartes est coherent avec les roles attribues

## 9. Recommandation operative immediate

Pour sortir rapidement du blocage actuel:

1. creer ou verifier les roles realm metier
2. attribuer a `Daniel Bin Zainol`:
   - `portal-access`
   - `control-panel-user`
   - `monitoring-user`
   - `grafana-user`
3. se deconnecter puis se reconnecter au portail
4. verifier que les cartes `Control Panel`, `Features`, `Grafana` et `Mimir` passent en mode ouvert

## 10. Etape suivante apres validation

Une fois les roles confirmes en prod technique:

- remettre `PORTAL_REQUIRED_TAGS=portal-access,portal-admin` si cette garde a ete relachee pendant les tests
- documenter officiellement le modele role -> cartes dans le PRD portail
- ajouter ensuite le DNS `portal.cascadya.internal` dans `dnsmasq` si ce n'est pas encore fait
