# PRD - Lot 3 - Module Sites et Inventory

## 1. Objet

Ce document definit le lot 3 du Control Panel apres la stabilisation du socle IAM du lot 2.

Le lot 3 introduit le premier vrai module metier visible du produit :

- un registre de `sites` ;
- une vue `inventory` des equipements connus ;
- un debut de workflow de `scan / refresh` pilote par permissions ;
- une premiere composition operateur du `dashboard` a partir des sites reellement
  retenus pour l'exploitation ;
- un usage strict du catalogue RBAC dans l'administration des roles.

L'objectif n'est pas encore de livrer toute la chaine industrielle de decouverte automatique. Le but est de poser :

- le modele de donnees metier ;
- les vues UI principales ;
- les APIs de consultation et d'administration ;
- le premier usage concret des permissions `site:*` et `inventory:*`.

## 2. Contexte

Le lot 1 a apporte :

- PostgreSQL metier ;
- schema RBAC ;
- seed roles / permissions ;
- checks de sante et automatisation Ansible.

Le lot 2 a apporte :

- Keycloak ;
- OIDC ;
- JIT user mirroring ;
- enforcement RBAC ;
- administration des utilisateurs.

Le Control Panel dispose maintenant d'un socle IAM stable. La suite logique est de brancher ce socle sur un perimetre metier reel :

- quels sites existent ;
- quels equipements sont connus ;
- quel est leur etat observable ;
- qui peut lire, modifier ou demander un scan.

## 3. Objectifs du lot 3

- Ajouter un registre persistants des sites industriels.
- Ajouter un catalogue persistants des equipements d'inventory.
- Exposer des pages UI de consultation pour `sites` et `inventory`.
- Exposer des APIs JSON pour lire et administrer ces objets.
- Appliquer les permissions deja existantes :
  - `site:read`
  - `site:write`
  - `inventory:read`
  - `inventory:scan`
- Introduire une premiere notion de job de scan ou refresh.
- Permettre au dashboard de se composer a partir des sites issus des IPC
  reellement provisionnes.
- Remplacer les saisies libres de roles cote admin par une selection stricte
  dans le catalogue RBAC.
- Livrer un lot utile sans attendre le moteur final de decouverte industrielle.

## 4. Perimetre fonctionnel

### 4.1 Registre de sites

Le module `sites` doit permettre de :

- lister les sites ;
- consulter le detail d'un site ;
- creer un site ;
- modifier un site ;
- activer / desactiver un site ;
- voir les equipements rattaches a un site ;
- voir l'etat du dernier scan connu pour ce site.

### 4.2 Catalogue d'inventory

Le module `inventory` doit permettre de :

- lister les equipements connus ;
- filtrer par site ;
- filtrer par type d'equipement ;
- filtrer par etat ;
- consulter le detail d'un equipement ;
- afficher la derniere date de vue ;
- afficher la source de la donnee.

### 4.3 Jobs de scan / refresh

Le lot 3 doit introduire un premier workflow simple :

- un operateur ou un admin peut demander un scan ;
- un enregistrement de job est cree en base ;
- le statut du job evolue ;
- les resultats mettent a jour le catalogue `inventory_assets`.

Le moteur reel de decouverte peut rester simple au lot 3 :

- mode manuel ;
- mode mock ;
- ou connecteur minimal.

L'essentiel est de valider les objets, les ecrans, les APIs et les permissions.

## 5. Architecture cible du lot 3

```text
Navigateur VPN
   ->
Traefik
   ->
FastAPI Control Panel
   ->
PostgreSQL metier
   ->
tables sites / inventory / scans
   ->
optionnel: connecteur de scan ou importeur simple
```

Le lot 3 repose sur les composants deja en place :

- `Traefik`
- `FastAPI`
- `postgres-fastapi`
- `Keycloak`

Il n'ajoute pas de nouvelle brique d'authentification.

## 6. Roles et permissions cibles

Le lot 3 doit s'appuyer sur les permissions deja seedees au lot 1.

### 6.1 Lecture des sites

- permission requise : `site:read`
- roles concernes :
  - `viewer`
  - `operator`
  - `provisioning_manager`
  - `admin`

### 6.2 Ecriture des sites

- permission requise : `site:write`
- role concerne dans l'etat actuel :
  - `admin`

### 6.3 Lecture de l'inventory

- permission requise : `inventory:read`
- roles concernes :
  - `viewer`
  - `operator`
  - `provisioning_manager`
  - `admin`

### 6.4 Demande de scan

- permission requise : `inventory:scan`
- roles concernes :
  - `operator`
  - `provisioning_manager`
  - `admin`

## 7. Modele de donnees cible

Le lot 3 doit introduire au minimum trois nouvelles tables.

### 7.1 Table `sites`

Champs cibles :

- `id`
- `code`
- `name`
- `customer_name`
- `country`
- `city`
- `timezone`
- `address_line1`
- `notes`
- `is_active`
- `created_at`
- `updated_at`

Contraintes fonctionnelles :

- `code` unique
- `name` obligatoire
- `is_active` a `true` par defaut

### 7.2 Table `inventory_assets`

Champs cibles :

- `id`
- `site_id`
- `asset_type`
- `hostname`
- `ip_address`
- `mac_address`
- `serial_number`
- `vendor`
- `model`
- `firmware_version`
- `status`
- `source`
- `first_seen_at`
- `last_seen_at`
- `created_at`
- `updated_at`

Exemples de `asset_type` :

- `router`
- `industrial_pc`
- `switch`
- `gateway`
- `sensor_hub`

Exemples de `status` :

- `online`
- `offline`
- `warning`
- `unknown`

### 7.3 Table `inventory_scans`

Champs cibles :

- `id`
- `site_id`
- `requested_by_user_id`
- `status`
- `trigger_type`
- `source`
- `started_at`
- `finished_at`
- `summary_json`
- `error_message`
- `created_at`
- `updated_at`

Exemples de `status` :

- `requested`
- `running`
- `succeeded`
- `failed`
- `cancelled`

Exemples de `trigger_type` :

- `manual`
- `scheduled`
- `system`

## 8. UI cible

### 8.1 Page `/sites`

Objectif :

- afficher la liste des sites ;
- permettre le filtrage simple ;
- permettre la creation si `site:write`.

Contenu attendu :

- tableau des sites
- code
- nom
- client
- localisation
- statut
- nombre d'equipements rattaches
- date du dernier scan

### 8.2 Page `/sites/{id}`

Objectif :

- afficher le detail d'un site ;
- afficher les equipements rattaches ;
- permettre la modification si `site:write` ;
- permettre de demander un scan si `inventory:scan`.

Contenu attendu :

- fiche site
- equipements du site
- dernier scan
- historique recent des scans

### 8.3 Page `/inventory`

Objectif :

- afficher tous les equipements connus ;
- filtrer rapidement ;
- permettre d'entrer par site ou par type.

Contenu attendu :

- tableau des assets
- lien vers le site parent
- type
- IP
- statut
- vendor / model
- last seen

### 8.4 Page `/inventory/assets/{id}`

Objectif :

- afficher le detail d'un equipement
- montrer son contexte site
- montrer la derniere observation connue

### 8.5 Page `/dashboard`

Objectif :

- afficher les sites reellement suivis par l'operateur ;
- permettre d'ajouter un site au dashboard a partir d'un IPC dont le dernier job
  de provisioning est en statut `succeeded` ;
- permettre de retirer un site du dashboard sans supprimer le site lui-meme ;
- recalculer la carte `Sites actifs` en fonction de cette liste visible.

Comportement attendu :

- la liste des candidats est derivee des jobs de provisioning reussis ;
- l'ajout d'un IPC ajoute son site parent au dashboard ;
- la selection visible est persistante cote navigateur pour l'operateur ;
- les singletons globaux `ems-core` et `ems-light` ne sont plus presentes
  comme pseudo-services propres a chaque site.

### 8.6 Page `/admin`

Objectif :

- assigner les roles via un vrai select operateur ;
- interdire les saisies libres de noms de roles.

Contenu attendu :

- un dropdown ouvert au clic ;
- une liste strictement limitee aux roles definis dans le produit ;
- reutilisation du meme composant pour l'invitation et l'edition des
  utilisateurs.

## 9. API cible

### 9.1 Sites

- `GET /api/sites`
- `POST /api/sites`
- `GET /api/sites/{id}`
- `PUT /api/sites/{id}`
- `PUT /api/sites/{id}/status`

Permissions attendues :

- lecture : `site:read`
- ecriture : `site:write`

### 9.2 Inventory

- `GET /api/inventory/assets`
- `GET /api/inventory/assets/{id}`
- `GET /api/inventory/scans`
- `GET /api/inventory/scans/{id}`
- `POST /api/inventory/scans`
- `POST /api/sites/{id}/inventory/scan`

Permissions attendues :

- lecture : `inventory:read`
- creation de scan : `inventory:scan`

### 9.3 Dashboard

Le dashboard existant doit commencer a montrer des donnees metier reelles :

- nombre de sites actifs
- nombre total d'equipements
- nombre d'equipements en warning ou offline
- nombre de scans en echec

Comportement retenu au 2 avril 2026 :

- `Sites actifs` suit le nombre de sites effectivement ajoutes au dashboard ;
- les sites visibles sont choisis depuis la liste des IPC provisionnes avec un
  dernier job `succeeded` ;
- la navigation haute ne doit plus presenter le placeholder `Ouest Consigne`,
  remplace par des entrees produit generiques et stables.

Comportement retenu au 3 avril 2026 :

- le dashboard charge ses donnees depuis les APIs reelles `sites`,
  `inventory/assets` et `provisioning jobs` ;
- les `industrial_pc` visibles sur le dashboard servent de base operateur pour
  composer des regroupements par entreprise ;
- une section `Entreprises` permet de :
  - creer une entreprise ;
  - lui rattacher des IPC deja visibles sur le dashboard ;
  - ouvrir / refermer la section via un chevron ;
  - editer localement `Lieu du site` et `Region` par IPC rattache ;
- une barre de recherche permet de retrouver un site par :
  - nom ;
  - code ;
  - ville ;
  - entreprise ;
  - region ;
  - nom ou IP d'un IPC ;
- des filtres de vue permettent :
  - le tri alphabetique ascendant ou descendant ;
  - le filtrage par lieu ;
  - le filtrage par region ;
  - le filtrage par entreprise ;
- dans cette premiere version, la composition du dashboard et les
  regroupements d'entreprises sont persistants cote navigateur via
  `localStorage` ;
- aucun backend partage de type `companies` n'est encore introduit a ce stade.

## 10. Comportements fonctionnels attendus

### 10.1 Creation d'un site

Un admin peut :

- creer un site ;
- lui donner un code stable ;
- renseigner ses metadonnees principales ;
- le voir apparaitre immediatement dans `/sites`.

### 10.2 Consultation d'un site

Un utilisateur avec `site:read` peut :

- consulter les donnees du site ;
- voir les assets rattaches ;
- voir le dernier scan associe.

### 10.3 Lecture inventory

Un utilisateur avec `inventory:read` peut :

- lister les assets ;
- filtrer par site ;
- ouvrir la fiche d'un asset ;
- voir la date de derniere observation.

### 10.4 Demande de scan

Un utilisateur avec `inventory:scan` peut :

- demander un scan global ou par site ;
- voir le job cree avec le statut `requested` ;
- suivre l'evolution du job jusqu'a `succeeded` ou `failed`.

### 10.5 Mise a jour des assets

Le lot 3 doit garantir que :

- un job de scan reussi met a jour `inventory_assets` ;
- les assets deja connus sont mis a jour sans duplication abusive ;
- les nouveaux assets sont rattaches au bon site ;
- la date `last_seen_at` est exploitable dans l'UI.

### 10.6 Composition operateur du dashboard

Un utilisateur autorise doit pouvoir :

- voir quels sites sont deja affiches sur le dashboard ;
- ajouter un site depuis un IPC provisionne avec un dernier job `succeeded` ;
- retirer ce site de la vue dashboard sans supprimer le site ni ses assets ;
- retrouver le meme perimetre au rechargement du navigateur ;
- creer un regroupement `Entreprise` local au dashboard ;
- rattacher a cette entreprise des IPC deja presents dans la vue ;
- visualiser les IPC rattaches en ouvrant la section entreprise ;
- enrichir localement chaque rattachement avec :
  - un `Lieu du site` ;
  - une `Region` ;
- rechercher rapidement un site par texte libre ;
- filtrer la vue des sites par ordre alphabetique, lieu, region ou entreprise.

### 10.7 Administration des roles

L'administration des utilisateurs doit :

- proposer les roles via un composant dropdown ;
- reutiliser strictement le catalogue RBAC existant ;
- eviter toute saisie libre d'un role non reconnu.

## 11. Strategie d'implementation recommandee

Pour garder le lot 3 realiste, le decoupage recommande est :

### 11.1 Etape A - socle data

- migration Alembic pour `sites`, `inventory_assets`, `inventory_scans`
- modeles SQLAlchemy
- endpoints JSON de lecture
- seed ou jeu de donnees de demo

### 11.2 Etape B - UI lecture

- page `/sites`
- page `/sites/{id}`
- page `/inventory`
- widgets dashboard

### 11.3 Etape C - actions metier

- creation / edition de site
- statut actif / inactif
- creation de jobs de scan
- historique simple des scans

### 11.4 Etape D - connecteur de scan minimal

- mode mock ou manuel acceptable
- mise a jour reelle de `inventory_assets`
- boucle complete permission -> action -> resultat

## 12. Validation attendue

Le lot 3 sera considere valide si les points suivants sont atteints :

- migration Alembic appliquee sans casser le lot 2
- nouvelles tables presentes et coherentes
- `GET /api/sites` et `GET /api/inventory/assets` operationnels
- affichage UI `/sites` et `/inventory` operationnel
- enforcement RBAC correct sur lecture et ecriture
- un admin peut creer et modifier un site
- un viewer peut lire mais pas modifier
- un operator peut demander un scan mais pas modifier un site
- au moins un scan de demonstration alimente `inventory_assets`
- dashboard affiche des donnees metier reelles
- le dashboard peut etre compose a partir de sites issus du provisioning
  reussi
- un operateur peut creer au moins une entreprise sur le dashboard et y
  rattacher des IPC visibles
- la recherche et les filtres du dashboard permettent de retrouver un site par
  entreprise, lieu, region ou IPC
- les roles admin sont selectionnes depuis le catalogue RBAC, sans saisie libre

## 13. Hors perimetre volontaire du lot 3

Le lot 3 ne doit pas encore couvrir :

- topologie reseau complete ;
- discovery industrielle multi-protocoles avancee ;
- SNMP, Modbus, SSH ou agents definitifs a pleine capacite ;
- rapprochement CMDB complet ;
- audit detaille de chaque changement d'asset ;
- workflow complet de provisionnement ;
- cartographie temps reel.

## 14. Definition of Done cible

Le lot 3 sera considere atteint quand :

- les sites existent comme objets metier persistants ;
- l'inventory existe comme catalogue persistants des equipements ;
- les vues UI principales sont navigables ;
- les APIs sont protegees par les permissions deja seedees ;
- un utilisateur autorise peut demander un scan ;
- un scan peut mettre a jour l'inventory ;
- le dashboard peut etre ajuste a partir des sites provisionnes visibles ;
- le dashboard peut regrouper ces sites et IPC sous des entreprises locales a
  l'operateur ;
- l'administration des roles reemploie strictement les roles definis ;
- le Control Panel affiche enfin un premier contenu metier concret.

## 15. Suite logique apres le lot 3

Une fois `sites` et `inventory` stabilises, la suite naturelle sera :

- lot 4 : jobs de provisionnement et suivi d'execution
- lot 5 : audit trail metier et observabilite applicative
- lot 6 : durcissement produit et experience operateur
