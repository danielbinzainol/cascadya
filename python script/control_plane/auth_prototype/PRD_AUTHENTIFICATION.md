# PRD - Systeme d'authentification du prototype Control Plane

## 1. Contexte

Ce document decrit le systeme d'authentification du prototype web du control panel present dans `auth_prototype/`.
Il couvre le fonctionnement actuel, les choix de conception, les composants techniques, les flux de connexion, la gestion de session, le controle d'acces, les limites connues et la trajectoire d'evolution vers un vrai fournisseur d'identite comme Keycloak.

Le prototype actuel a un objectif volontairement limite :

- valider le flux UX de connexion operateur ;
- valider la protection de pages HTML et d'endpoints API ;
- valider une premiere couche de RBAC simple ;
- preparer un socle remplaçable ensuite par OIDC/Keycloak.

Ce prototype n'est pas encore une solution de production.

## 2. Objectifs produit

### 2.1 Objectifs

- Permettre a un operateur de se connecter au control panel via une interface web.
- Etablir une session authentifiee reutilisable entre plusieurs requetes HTTP.
- Restreindre l'acces a certaines pages et API selon le role de l'utilisateur.
- Poser une architecture simple a remplacer plus tard par une authentification federée.

### 2.2 Hors perimetre actuel

- Federation OIDC / SSO.
- Gestion d'utilisateurs en base PostgreSQL.
- MFA.
- Rotation de mots de passe.
- CSRF dedie.
- Audit persistant en base.
- Revocation serveur centralisee des sessions.

## 3. Vue d'ensemble de l'architecture

Le prototype repose sur `FastAPI` et `Starlette SessionMiddleware`.

### 3.1 Composants utilises

- Framework web : `FastAPI` dans [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L23)
- Moteur de templates HTML : `Jinja2Templates` dans [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L21)
- Middleware de session : `SessionMiddleware` dans [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L24)
- Signature cryptographique de session : `itsdangerous`, indirectement utilise par `SessionMiddleware`
- Validation de formulaire : `Form(...)` de FastAPI dans [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L93)
- Verification de mot de passe : `hashlib.scrypt` + `hmac.compare_digest` dans [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py#L51)

### 3.2 Architecture logique

```text
Navigateur
   ->
FastAPI
   -> SessionMiddleware
   -> routes HTML
   -> routes JSON protegees
   -> verification utilisateur / roles
   -> templates Jinja2
```

### 3.3 Principe fondamental

Le systeme ne genere pas de JWT applicatif.
Il utilise une session web stockee cote client dans un cookie signe.
Le contenu de la session est valide a chaque requete grace a une cle secrete serveur.

## 4. Structure du systeme

### 4.1 Fichiers principaux

- Configuration : [config.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/config.py)
- Securite et utilisateurs : [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py)
- Application et routes : [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py)
- Documentation de lancement : [README.md](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/README.md)
- Templates HTML : `auth_prototype/app/templates/`

### 4.2 Parametres runtime

Les parametres sont centralises dans `Settings` dans [config.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/config.py#L15).

Champs exposes :

- `app_name`
- `session_secret`
- `session_cookie_name`
- `secure_cookies`
- `same_site`
- `session_ttl_seconds`

Chargement :

- via variables d'environnement ;
- avec mise en cache process via `@lru_cache(maxsize=1)` dans [config.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/config.py#L25).

## 5. Modele d'identite

### 5.1 Types de donnees

Le systeme distingue deux representations :

- `DemoUserRecord` : representation source d'un utilisateur local avec hash de mot de passe dans [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py#L10)
- `SessionUser` : representation epuree de l'utilisateur authentifie dans [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py#L18)

### 5.2 Utilisateurs de demonstration

Le prototype integre 2 comptes statiques dans [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py#L29) :

- `operator` avec role `operator`
- `admin` avec roles `operator`, `admin`

Ces comptes existent pour permettre le test local sans base de donnees et sans fournisseur d'identite externe.

### 5.3 Roles

Le systeme RBAC actuel utilise une liste de roles attachee a l'utilisateur :

- `operator` : acces au dashboard et a l'API `GET /api/me`
- `admin` : acces supplementaire a la page `/admin` et a l'endpoint `GET /api/admin/audit`

Le role admin est teste via la propriete `is_admin` dans [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py#L24).

## 6. Gestion des mots de passe

### 6.1 Algorithme utilise

Le prototype utilise `scrypt` via `hashlib.scrypt` dans [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py#L63).

Format du hash :

```text
scrypt$N$r$p$base64(salt)$base64(digest)
```

Ce format contient :

- l'algorithme ;
- les parametres `N`, `r`, `p` ;
- le sel (`salt`) ;
- le digest derive.

### 6.2 Verification

La verification fonctionne ainsi :

1. parser la chaine stockee ;
2. decoder le sel et le digest attendus ;
3. recalculer le digest avec le mot de passe fourni ;
4. comparer avec `hmac.compare_digest` pour eviter une comparaison naive.

Implementation : [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py#L51).

### 6.3 Choix de conception

Pourquoi `scrypt` :

- disponible dans la lib standard Python ;
- meilleur qu'un hash simple type SHA-256 pour un mot de passe ;
- suffisant pour un prototype local sans dependance externe.

Pourquoi ce n'est pas la cible finale :

- en production, on preferera probablement `Argon2id` avec une couche de stockage centralisee ;
- les comptes ne doivent plus etre codés en dur.

## 7. Gestion de session

### 7.1 Type de session

Le prototype utilise une session web basee sur cookie signe.
Ce n'est pas une session stockee en base.
Ce n'est pas non plus un access token OAuth.

### 7.2 Middleware

Le middleware est configure dans [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L24) avec :

- `secret_key=settings.session_secret`
- `session_cookie=settings.session_cookie_name`
- `same_site=settings.same_site`
- `https_only=settings.secure_cookies`
- `max_age=settings.session_ttl_seconds`

### 7.3 Contenu de session

Une fois connecte, le backend stocke dans `request.session["user"]` un payload minimal construit par `build_session_payload()` dans [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py#L87).

Payload :

```json
{
  "username": "operator",
  "display_name": "Operator Demo",
  "roles": ["operator"]
}
```

### 7.4 Rehydratation

A chaque requete, `_current_user()` lit `request.session.get("user")` puis reconstruit un `SessionUser` via `session_user_from_payload()` :

- lecture : [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L42)
- conversion : [security.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/security.py#L95)

### 7.5 Destruction de session

Au login reussi et au logout, `request.session.clear()` est appele :

- login : [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L114)
- logout : [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L122)

But :

- eviter la conservation de donnees de session anterieures ;
- repartir d'un etat propre.

## 8. Parcours utilisateur et flux fonctionnels

### 8.1 Flux de base

```text
Utilisateur non connecte
  -> GET /auth/login
  -> saisie username/password
  -> POST /auth/login
  -> verification des credentials
  -> creation session
  -> redirect 303 vers /app
```

### 8.2 Flux de redirection post-login

Le systeme accepte un parametre `next` ou `next_path` pour revenir sur la ressource initialement demandee.

Sanitisation : `_safe_next_path()` dans [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L34)

Protections appliquees :

- si la valeur est vide : retour sur `/app`
- si la valeur ne commence pas par `/` : rejet
- si la valeur commence par `//` : rejet

Objectif : eviter un open redirect trivial.

### 8.3 Flux de login detaille

1. l'utilisateur ouvre `/auth/login`
2. s'il a deja une session, il est redirige vers `next` ou `/app`
3. sinon le template `login.html` est rendu
4. le formulaire envoie `username`, `password`, `next_path`
5. `authenticate()` cherche l'utilisateur et verifie le mot de passe
6. en cas d'echec, la page de login est rendue avec code `400`
7. en cas de succes :
   - vidage de session
   - ecriture du payload utilisateur
   - redirection `303` vers la destination cible

Implementation principale : [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L93).

### 8.4 Flux d'acces a une page protegee

Exemple `/app` :

1. le backend lit la session ;
2. si aucun utilisateur n'est present, redirection vers `/auth/login?next=/app` ;
3. sinon rendu du dashboard.

Implementation : [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L128).

### 8.5 Flux d'acces admin

Exemple `/admin` :

1. controle de presence d'utilisateur ;
2. si absent, redirection vers login ;
3. si present mais sans role admin, rendu d'une page `403` dediee ;
4. si admin, rendu du template admin.

Implementation : [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L145).

### 8.6 Flux API protegee

Exemple `GET /api/me` :

1. FastAPI appelle la dependance `require_api_user`
2. si la session ne contient pas d'utilisateur, une `HTTPException 401` est levee
3. sinon l'endpoint retourne le profil minimal

Implementation :

- dependance user : [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L46)
- endpoint : [main.py](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/main.py#L171)

## 9. Endpoints

### 9.1 HTML

- `GET /` : redirige vers `/app` si connecte, sinon vers `/auth/login`
- `GET /auth/login` : page de connexion
- `POST /auth/login` : soumission du formulaire
- `POST /auth/logout` : destruction de session puis redirection
- `GET /app` : dashboard protege
- `GET /admin` : page admin protegee par role

### 9.2 API JSON

- `GET /healthz` : endpoint de sante, non protege
- `GET /api/me` : retourne l'identite courante, protege
- `GET /api/admin/audit` : retourne un exemple d'audit, protege admin

## 10. UX et templates

Le prototype inclut une mini UI pour tester la logique auth sans frontend React.

Ecrans :

- login
- dashboard
- admin
- unauthorized

Raison de ce choix :

- decoupler la validation du backend auth de la future UI React ;
- permettre un test manuel immediat via navigateur ;
- reduire le cout de mise au point.

## 11. Choix de conception

### 11.1 Pourquoi FastAPI

- coherent avec l'architecture cible du control plane ;
- simple pour exposer routes HTML et JSON ;
- bon support des dependances d'auth ;
- facile a migrer vers OIDC ensuite.

### 11.2 Pourquoi une session cookie et pas un JWT maison

- flux navigateur plus simple a tester ;
- moins de decisions de design prematurees sur l'API frontend ;
- compatible avec un futur backend qui gerera des redirections/login web ;
- bon choix de prototype pour pages server-rendered et API interne.

### 11.3 Pourquoi des comptes locaux

- zero dependance externe ;
- test offline ;
- mise au point rapide du flux de connexion ;
- ideal pour preparer les garde-fous avant Keycloak.

### 11.4 Pourquoi du RBAC minimal

Le besoin immediat etait de valider deux niveaux :

- utilisateur connecte ;
- utilisateur admin.

Cela permet deja de tester les mecanismes suivants :

- lecture de session ;
- dependances FastAPI ;
- filtrage par role ;
- differences de comportement HTML vs API.

## 12. Securite actuelle

### 12.1 Mesures presentes

- mots de passe hashes avec `scrypt`
- comparaison sure via `hmac.compare_digest`
- session signee avec cle secrete
- TTL de session configurable
- option `SameSite`
- option `Secure` via `AUTH_PROTO_SECURE_COOKIES`
- prevention simple des open redirects avec `_safe_next_path`
- separation claire entre routes non protegees et routes protegees

### 12.2 Ce que le prototype ne fait pas encore

- CSRF tokens explicites sur les formulaires
- rotation/revocation centralisee de session
- lockout apres echecs repetes
- rate limiting
- journaux d'auth persistants
- hash Argon2id
- stockage d'utilisateurs en base
- MFA
- federation d'identite

## 13. Risques et limitations

### 13.1 Limites structurelles

- les utilisateurs sont dans le code ;
- les roles sont statiques ;
- pas de persistence des utilisateurs ni des sessions ;
- l'absence de CSRF est acceptable pour un prototype local, pas pour une exposition Internet ;
- le secret de session a une valeur par defaut de demonstration si l'env n'est pas surcharge.

### 13.2 Risques si deployee telle quelle sur Internet

- comptes demo connus ;
- politique de mot de passe non geree ;
- pas de MFA ;
- pas de federation entreprise ;
- controle d'acces trop rudimentaire ;
- pas de secret manager branche ;
- pas d'audit conforme.

## 14. Non-fonctionnel

### 14.1 Exploitabilite

L'app se lance avec `uvicorn` selon [README.md](C:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/README.md#L18).

### 14.2 Configurabilite

Variables d'environnement supportees :

- `AUTH_PROTO_APP_NAME`
- `AUTH_PROTO_SESSION_SECRET`
- `AUTH_PROTO_SESSION_COOKIE`
- `AUTH_PROTO_SECURE_COOKIES`
- `AUTH_PROTO_SAMESITE`
- `AUTH_PROTO_SESSION_TTL_SECONDS`

### 14.3 Observabilite

Actuellement minimale :

- logs du serveur `uvicorn`
- codes HTTP
- absence d'audit applicatif persistant

## 15. Scenarios de test

### 15.1 Cas nominal

- ouvrir `/auth/login`
- se connecter avec `operator`
- verifier acces `/app`
- verifier `GET /api/me`

### 15.2 Cas admin

- se connecter avec `admin`
- verifier acces `/admin`
- verifier `GET /api/admin/audit`

### 15.3 Cas refus

- mauvais mot de passe -> page login avec erreur `400`
- acces `/app` sans session -> redirection login
- acces `/admin` avec `operator` -> page 403
- acces `/api/admin/audit` sans admin -> `403`

## 16. Evolutions cibles vers la version production

### 16.1 Etape 1

Conserver FastAPI mais remplacer les comptes locaux par une source d'identite reelle.

### 16.2 Etape 2

Basculer vers Keycloak OIDC pour les operateurs humains :

- Authorization Code Flow + PKCE pour le frontend React ;
- validation des tokens cote backend ;
- mapping groupes/roles Keycloak -> roles applicatifs.

### 16.3 Etape 3

Conserver Vault pour :

- secrets applicatifs ;
- PKI ;
- credentials techniques ;
- eventuellement dynamic secrets PostgreSQL.

### 16.4 Etape 4

Durcir la couche auth :

- CSRF ;
- rate limiting ;
- audit trail ;
- MFA ;
- revocation de session ;
- persistance des permissions ;
- secret manager ;
- cookies `Secure` obligatoires en HTTPS.

## 17. Decision d'architecture recommandee

### 17.1 Pour le prototype actuel

Le design actuel est adapte parce qu'il maximise la vitesse d'apprentissage :

- simple ;
- testable en local ;
- faible complexite ;
- proche du futur backend FastAPI.

### 17.2 Pour la cible produit

Le design final recommande est :

```text
React/Vite
  -> Keycloak (OIDC)
  -> FastAPI
     -> validation token / session applicative
     -> RBAC
     -> PostgreSQL
     -> Vault
```

Le prototype n'est donc pas une impasse.
Il sert de couche d'experimentation pour :

- le parcours login ;
- la protection des routes ;
- la structuration du code auth ;
- la future migration vers une auth d'entreprise.

## 18. Resume executif

Le systeme d'authentification actuel du prototype Control Plane est un backend `FastAPI` avec sessions cookies signees par `SessionMiddleware`, rendu HTML par `Jinja2`, mots de passe verifies via `scrypt`, et un RBAC minimal base sur deux roles (`operator`, `admin`).

Il a ete concu pour valider rapidement le comportement fonctionnel et securitaire minimum du futur control panel sans dependre d'un service externe.

Ses forces :

- simple ;
- lisible ;
- testable localement ;
- aligne avec le futur backend FastAPI.

Ses limites :

- utilisateurs locaux en dur ;
- pas de MFA ;
- pas de CSRF ;
- pas de SSO ;
- pas de persistance.

Conclusion :

le prototype est une bonne base de travail technique, mais il doit evoluer vers `Keycloak + OIDC` pour l'authentification des operateurs et conserver `Vault` pour les secrets et la PKI.
