# PRD - MVP Modbus TCP Scanner / Extractor

## 1. Vue d'ensemble

### Nom du produit
Modbus TCP Scanner / Extractor MVP

### Vision
Permettre a un IPC connecte en Ethernet a un automate inconnu de decouvrir, de maniere strictement non destructive, les zones Modbus TCP lisibles exposees par cet automate, d'en extraire les valeurs brutes, puis de produire une carte memoire exploitable pour la R&D.

### Probleme
Dans de nombreux contextes industriels, l'equipe dispose d'un PLC ou d'une machine dont la table d'echange Modbus est absente, incomplete ou obsolete. Sans cette documentation, l'analyse, la reprise de site, la retro-ingenierie et l'integration sont lentes et risquees.

### Opportunite
Un outil de scan read-only, prudent et industrialisable permettrait :
- d'identifier rapidement les zones Modbus TCP actives ;
- d'accelerer les phases R&D et de diagnostic ;
- de constituer une base de travail pour l'analyse fonctionnelle ulterieure ;
- de reduire la dependance a la documentation constructeur ;
- d'adapter automatiquement la cadence de scan a la capacite reelle du PLC.

## 2. Objectif du MVP

Le MVP doit permettre de :
- se connecter a un equipement Modbus TCP ;
- trouver un ou plusieurs `Unit ID` repondants ;
- scanner en lecture seule les 4 grandes familles Modbus :
  - Coils
  - Discrete Inputs
  - Input Registers
  - Holding Registers
- detecter les plages valides via un algorithme de scan adaptatif ;
- estimer une frequence de scan sure a partir d'un test de debit non destructif ;
- faire varier automatiquement la frequence pendant le scan sans depasser un plafond configure ;
- enregistrer les valeurs brutes lues ;
- proposer un premier niveau d'interpretation de type ;
- exporter les resultats dans un format simple exploitable par la R&D.

Le MVP ne doit pas chercher a "comprendre" automatiquement la signification metier des variables. Il doit fournir une carte memoire brute et fiable, avec des indices d'interpretation et une strategie de communication prudente.

## 3. Contexte et hypothese cle

Le protocole Modbus ne fournit pas de mecanisme natif de decouverte des variables exposees. Il n'existe pas de fonction standard qui retourne "la liste des registres utilises". Le produit doit donc inferer la carte memoire en testant des lectures d'adresses, puis en interpretant les reponses du PLC.

Hypothese centrale :
si un equipement expose des donnees en Modbus TCP, un scan de lecture controle, progressif et adaptatif permet d'en cartographier une partie ou la totalite accessible.

Hypothese secondaire :
la capacite de reponse d'un PLC peut etre estimee de maniere suffisamment sure par un profilage de debit prudent, base sur la derive du temps de reponse plutot que sur la recherche du point de crash.

## 4. Utilisateurs cibles

### Utilisateurs principaux
- Ingenieur automatisme
- Ingenieur integration / commissioning
- Equipe R&D
- Technicien de diagnostic avance

### Utilisateurs secondaires
- Data engineer industriel
- Equipe support technique
- Equipe maintenance experte

## 5. Cas d'usage du MVP

### Cas d'usage 1
En tant qu'ingenieur R&D, je veux connecter un IPC a un automate inconnu en Modbus TCP et lancer un scan pour obtenir une carte memoire brute sans documentation constructeur.

### Cas d'usage 2
En tant qu'integrateur, je veux identifier rapidement quelles plages d'adresses repondent en lecture afin de reduire le temps de mise en service ou de retro-ingenierie.

### Cas d'usage 3
En tant qu'analyste, je veux exporter les resultats en JSON ou CSV pour comparer les valeurs avec des evenements terrain et deduire le role probable des registres.

### Cas d'usage 4
En tant qu'utilisateur prudent en environnement industriel, je veux que le scanner soit strictement read-only, maintienne une seule connexion TCP stable, et limite son debit pour eviter de destabiliser le PLC.

### Cas d'usage 5
En tant qu'utilisateur avance, je veux definir un plafond de frequence de requetes et laisser l'outil determiner automatiquement une frequence operationnelle sure en dessous de cette limite.

## 6. Proposition de valeur

Le produit apporte une valeur immediate en :
- reduisant fortement le temps necessaire pour trouver les zones utiles ;
- standardisant la collecte de donnees sur des PLC peu documentes ;
- fournissant une base de donnees reutilisable pour des analyses ulterieures ;
- minimisant les risques grace a une approche lecture seule avec throttling ;
- optimisant la vitesse de scan sans chercher la saturation destructive du PLC.

## 7. Portee du MVP

### Inclus dans le MVP
- Connexion Modbus TCP
- Maintien d'une connexion TCP persistante unique pendant le profilage et le scan
- Detection manuelle ou semi-automatique du `Unit ID`
- Scan read-only des objets Modbus standards :
  - FC01 Read Coils
  - FC02 Read Discrete Inputs
  - FC03 Read Holding Registers
  - FC04 Read Input Registers
- Algorithme de scan adaptatif avec taille de bloc dynamique
- Module de `safe throughput profiling`
- Gouverneur de frequence pendant le scan
- Gestion des erreurs Modbus, des timeouts et des resets TCP
- Journalisation du scan et du profilage
- Export JSON
- Export CSV
- Heuristiques simples d'interpretation :
  - bool
  - uint16
  - int16
  - uint32
  - int32
  - float32
  - ASCII simple
  - decomposition bit a bit
- Resume de scan par type d'objet
- Resume de profilage reseau

### Hors perimetre du MVP
- Modbus RTU
- Ecriture Modbus
- Modification de parametres automate
- Detection automatique de la signification metier des variables
- Support de protocoles non Modbus
- Interface graphique riche
- Historisation longue duree
- Correlation automatique avec des actions terrain
- Fingerprinting avance inter-machines
- Gestion multi-equipements en parallele
- Authentification / gestion utilisateurs
- Decodages avances constructeur-specifiques

## 8. Exigences fonctionnelles

### FR-1 Connexion
Le systeme doit permettre a l'utilisateur de se connecter a un equipement Modbus TCP.

### FR-2 Parametrage minimal
Le systeme doit permettre de definir les parametres suivants :
- IP cible ;
- port TCP, avec `502` par defaut ;
- timeout ;
- `Unit ID` cible ou plage de `Unit ID` ;
- familles d'objets a scanner ;
- plage d'adresses ;
- `block_size_initial` ;
- `block_size_max` ;
- `max_requests_per_second` comme plafond dur ;
- nombre de retries ;
- delai minimal entre requetes si configure.

### FR-3 Detection du Unit ID
Le systeme doit pouvoir tester une plage de `Unit ID` et identifier ceux qui repondent.

### FR-4 Scan par famille d'objets
Le systeme doit scanner separement :
- les coils ;
- les discrete inputs ;
- les input registers ;
- les holding registers.

### FR-5 Scan adaptatif par taille de bloc
Le systeme doit utiliser une taille de bloc dynamique avec les regles minimales suivantes :
- taille initiale configurable ;
- sur succes, augmentation progressive de la taille de bloc jusqu'a une limite max ;
- sur `Illegal Data Address`, reduction de la taille de bloc ;
- si la taille atteint 1 et echoue, l'adresse est marquee invalide et le scan continue ;
- le scan ne doit jamais faire d'ecriture pour verifier une adresse.

### FR-6 Profilage de debit securise
Le systeme doit pouvoir executer, avant le scan principal, un test de debit non destructif pour estimer une frequence operationnelle sure.

Le module de profilage doit respecter les contraintes suivantes :
- utiliser une connexion TCP persistante unique ;
- n'avoir qu'une seule requete en vol a la fois ;
- utiliser une lecture minimale sur une adresse valide de reference ;
- calculer une baseline de latence au repos ;
- augmenter la frequence par paliers ;
- surveiller la derive de latence plutot que chercher le point de timeout ;
- s'arreter avant saturation des que des seuils de deviation sont atteints ;
- retourner une `recommended_requests_per_second` inferieure ou egale a `max_requests_per_second`.

### FR-7 Selection de l'adresse de reference pour le profilage
Le systeme doit permettre deux modes :
- adresse de reference fournie par l'utilisateur ;
- adresse de reference decouverte automatiquement.

Si aucune adresse de reference n'est fournie, le systeme doit :
- tenter une decouverte a faible impact pour trouver une premiere lecture valide ;
- utiliser cette lecture comme sonde de profilage ;
- revenir a une frequence conservative par defaut si aucune sonde valide n'est trouvee dans le budget de recherche defini.

### FR-8 Gouverneur de frequence pendant le scan
Le systeme doit ajuster la cadence pendant le scan selon les signaux d'etat observes.

Le gouverneur doit au minimum :
- partir de la frequence recommandee par le profilage, ou d'une valeur conservative par defaut ;
- ne jamais depasser `max_requests_per_second` ;
- ralentir en cas de derive persistante du RTT, de timeouts, de resets TCP ou d'augmentation anormale du jitter ;
- re-accelerer progressivement si la connexion redevient stable ;
- journaliser les changements de frequence.

### FR-9 Gestion des erreurs
Le systeme doit differencier au minimum :
- succes de lecture ;
- `Illegal Data Address` ;
- `Illegal Function` ;
- timeout / absence de reponse ;
- reset TCP / fermeture de socket ;
- erreur de connexion.

### FR-10 Journalisation
Le systeme doit conserver un journal incluant :
- date et heure ;
- parametres utilises ;
- `Unit ID` ;
- type d'objet scanne ;
- plage adressee ;
- resultat ;
- temps de reponse ;
- nombre de retries ;
- frequence instantanee ou palier actif ;
- raison des ralentissements ou arrets du profilage.

### FR-11 Stockage des resultats
Le systeme doit stocker pour chaque adresse ou plage valide :
- type d'objet Modbus ;
- adresse brute ;
- valeur brute ;
- statut de lecture ;
- timestamp de collecte ;
- interpretations candidates lorsque disponibles.

### FR-12 Interpretation basique
Le systeme doit proposer, pour les registres lus, des vues candidates sans affirmer la verite metier :
- `uint16`
- `int16`
- `uint32`
- `int32`
- `float32` avec variantes de word order si configurees
- texte ASCII simple si pertinent
- decomposition binaire pour les registres de statut

### FR-13 Export
Le systeme doit exporter les resultats dans :
- un fichier JSON complet ;
- un fichier CSV simplifie pour analyse rapide.

### FR-14 Resume de fin d'execution
Le systeme doit produire un resume contenant :
- equipement cible ;
- `Unit ID` retenu ;
- familles Modbus scannees ;
- nombre d'adresses testees ;
- nombre d'adresses valides ;
- nombre d'adresses invalides ;
- nombre d'erreurs par type ;
- duree totale du scan ;
- frequence initiale retenue ;
- frequence moyenne observee ;
- frequence max stable observee ;
- raison d'eventuels ralentissements majeurs.

## 9. Exigences non fonctionnelles

### NFR-1 Securite operationnelle
Le produit doit etre strictement read-only dans le MVP. Aucune fonction d'ecriture ne doit etre exposee par l'outil.

### NFR-2 Robustesse industrielle
Le produit doit integrer un mecanisme de throttling, de backoff et de connexion persistante afin de limiter la charge sur des PLC anciens ou fragiles.

### NFR-3 Tracabilite
Chaque scan doit etre reproductible via les parametres journalises et les artefacts exportes.

### NFR-4 Performance raisonnable
Le systeme doit etre significativement plus rapide qu'un scan registre par registre sur des zones denses, grace au scan adaptatif et a la regulation de frequence.

### NFR-5 Respect du port TCP
Le systeme ne doit pas ouvrir et fermer des connexions TCP en boucle pendant le profilage ou le scan normal. Le mode nominal doit utiliser une socket persistante unique par cible.

### NFR-6 Extensibilite
L'architecture doit permettre d'ajouter plus tard :
- nouveaux decodeurs ;
- strategies de scan alternatives ;
- UI graphique ;
- correlation temporelle ;
- fingerprinting ;
- plugins protocolaires.

### NFR-7 Portabilite
Le backend doit pouvoir fonctionner au minimum sur un IPC Windows industriel. Le support Linux est souhaite si l'architecture le permet sans complexite excessive.

## 10. Flux fonctionnel cible

### Etape 1 - Configuration
L'utilisateur renseigne les parametres de connexion TCP et fixe, s'il le souhaite, un plafond de frequence de requetes.

### Etape 2 - Validation de communication
Le systeme verifie qu'une communication de base est possible via une connexion TCP persistante.

### Etape 3 - Detection du Unit ID
Si necessaire, le systeme teste une plage de `Unit ID` pour identifier un esclave repondant.

### Etape 4 - Selection ou decouverte d'une sonde valide
Le systeme recupere une adresse de reference pour le profilage :
- adresse fournie par l'utilisateur ;
- ou premiere lecture valide decouverte avec un budget de recherche limite.

### Etape 5 - Profilage de debit securise
Le systeme mesure une baseline de latence, monte progressivement en frequence et calcule une frequence operationnelle sure.

### Etape 6 - Selection du scan
L'utilisateur choisit :
- les familles Modbus a scanner ;
- la plage d'adresses ;
- la taille de bloc initiale ;
- la taille de bloc max ;
- le plafond de frequence ;
- les delais / retries.

### Etape 7 - Scan adaptatif
Le systeme execute un scan read-only avec taille de bloc dynamique et gouverneur de frequence.

### Etape 8 - Decodage preliminaire
Le systeme applique les decodeurs simples aux donnees collectees.

### Etape 9 - Export
Le systeme genere les fichiers de sortie et un resume d'execution.

## 11. Algorithme MVP de scan adaptatif

### Principe
Le moteur de scan tente de lire des plages contigues pour gagner du temps dans les zones denses, puis reduit automatiquement la granularite lorsqu'une erreur d'adresse apparait.

### Regles MVP
- `block_size_initial` configurable
- `block_size_max` configurable
- sur succes, croissance de la taille du bloc
- sur `Illegal Data Address`, division de la taille du bloc
- sur echec a taille 1, marquage de l'adresse comme invalide et passage a l'adresse suivante
- sur timeout repetes ou reset TCP, ralentissement global du moteur
- les adaptations de bloc et de frequence sont independantes mais coordonnees

### Comportement attendu
- scan rapide sur zones continues
- scan precis sur zones fragmentees
- faible risque sur automate lent

## 12. Algorithme MVP de safe throughput profiling

### Objectif
Determiner une frequence de requetes soutenable sans chercher a provoquer la saturation, le timeout ou le crash du PLC.

### Principe
Le profilage n'essaie pas de trouver la latence max. Il cherche le dernier palier stable avant derive significative du temps de reponse.

### Regles MVP
- une seule connexion TCP persistante ;
- une seule requete simultanee ;
- lecture minimale sur une sonde valide ;
- phase baseline avec lectures lentes et espacees ;
- mesure au minimum de `median_rtt_ms` et `p95_rtt_ms` ;
- montee par paliers de frequence ;
- arret si la latence derive au-dela d'un seuil configure ;
- arret immediat en cas de timeout, reset TCP ou erreur de communication repetee ;
- calcul d'une frequence recommandee comme marge de securite du dernier palier stable ;
- respect du plafond `max_requests_per_second`.

### Exemple de politique par defaut
- baseline sur `10` a `20` lectures lentes
- paliers croissants de type `2, 5, 10, 15, 20, 30, 40 req/s`
- seuil d'alerte base sur une derive du `p95 RTT`
- frequence recommandee par defaut = `70%` du dernier palier stable

### Resultat attendu
Le profilage produit :
- `baseline_median_rtt_ms`
- `baseline_p95_rtt_ms`
- `last_stable_req_per_sec`
- `recommended_req_per_sec`
- `stop_reason`

## 13. Modele de donnees de sortie

### Enregistrement unitaire attendu
Chaque enregistrement exporte doit pouvoir contenir au minimum :
- `scan_id`
- `timestamp`
- `connection_type`
- `target`
- `unit_id`
- `object_type`
- `address`
- `count`
- `raw_value`
- `raw_words`
- `status`
- `error_type`
- `response_time_ms`
- `effective_requests_per_second`
- `candidate_decodings`

### Resume de profilage attendu
L'export doit pouvoir contenir un resume de profilage avec :
- `probe_object_type`
- `probe_address`
- `baseline_median_rtt_ms`
- `baseline_p95_rtt_ms`
- `tested_steps_req_per_sec`
- `last_stable_req_per_sec`
- `recommended_req_per_sec`
- `configured_max_req_per_sec`
- `stop_reason`

### Exemple logique
- un coil valide : adresse + etat bool
- un holding register valide : adresse + mot brut + decodages candidats
- une adresse invalide : adresse + statut invalide + type d'erreur
- un profilage prudent : baseline + dernier palier stable + frequence recommandee

## 14. UX du MVP

Le MVP peut etre livre sous forme de CLI.

### Commandes attendues
- lancer un scan TCP
- lancer un profilage TCP seul
- lancer un scan TCP avec profilage automatique
- limiter le scan a certains types d'objets
- definir plage d'adresses
- definir `Unit ID`
- definir taille initiale et taille max
- definir `max_requests_per_second`
- activer ou desactiver le profilage initial
- exporter vers un dossier cible

### Sorties utilisateur
- progression de scan
- statistiques en temps reel simples
- frequence actuelle
- resume final lisible
- chemins des fichiers exportes

## 15. Criteres d'acceptation MVP

Le MVP est accepte si :
- il peut se connecter a au moins un equipement Modbus TCP de test ;
- il detecte correctement un `Unit ID` repondant sur une plage donnee ;
- il scanne en lecture seule sans envoyer de fonctions d'ecriture ;
- il identifie au moins une plage valide et une plage invalide lorsqu'elles existent ;
- il exporte des resultats JSON et CSV ;
- il journalise les erreurs, les timeouts et les variations de frequence ;
- il supporte le scan adaptatif avec taille de bloc configurable ;
- il peut realiser un profilage de debit prudent sans ouvrir et fermer des connexions en boucle ;
- il calcule une frequence recommandee inferieure ou egale au plafond configure ;
- il ralentit automatiquement si la derive de latence ou les erreurs reseau augmentent ;
- il reste stable face a des erreurs d'adresses et a des timeouts moderes.

## 16. Risques et limites

### Risques techniques
- certains PLC repondent de maniere non standard ;
- certains gateways Modbus TCP vers serie masquent ou transforment les erreurs ;
- certains automates sont sensibles a un debit de scan trop eleve ;
- un timeout ne signifie pas toujours "adresse invalide" ;
- une sonde de profilage mal choisie peut fausser l'estimation du debit soutenable.

### Limites produit
- l'outil ne peut pas decouvrir les noms symboliques des variables ;
- l'outil ne peut pas garantir que toutes les variables utiles sont exposees en Modbus ;
- un registre valide avec valeur `0` n'est pas "vide", seulement lisible et a zero ;
- la signification metier necessitera souvent des essais terrain ou de la correlation temporelle ;
- si aucune lecture valide n'est trouvee rapidement, le profilage devra retomber sur une cadence conservative plutot que sur une estimation precise ;
- la frequence calculee reste une estimation prudente, pas une capacite absolue garantie du PLC.

## 17. Indicateurs de succes

Pour le MVP, on suivra idealement :
- temps moyen de scan sur un equipement de test ;
- nombre moyen d'adresses valides identifiees ;
- taux d'echec de connexion ;
- nombre de scans completes sans crash ;
- qualite percue des exports par l'equipe R&D ;
- ecart entre frequence recommandee et frequence reellement soutenue en scan ;
- nombre de scans ayant necessite un fallback sur frequence conservative.

## 18. Roadmap post-MVP

Fonctionnalites candidates pour les versions suivantes :
- interface graphique locale
- profils par constructeur ou par gamme PLC
- fingerprinting de structure memoire
- snapshots repetes et diff entre scans
- correlation automatique avec des actions operateur
- heuristiques avancees de detection de types
- catalogue de signatures connues
- support Modbus RTU
- support de protocoles additionnels
- scan distribue ou multi-equipements
- etiquetage manuel collaboratif des registres

## 19. Questions ouvertes pour la phase suivante

- Quelle plage d'adresses doit etre scannee par defaut ?
- Faut-il imposer un plafond global par defaut, meme si l'utilisateur n'en fournit pas ?
- Quelle politique par defaut doit etre retenue pour le calcul de `recommended_req_per_sec` : `60%`, `70%` ou `80%` du dernier palier stable ?
- Quel budget maximal de recherche doit etre alloue a la decouverte automatique de la sonde de profilage ?
- Veut-on memoriser l'historique des profils reseau par machine des le MVP ou plus tard ?
- Quels automates de test serviront de reference de validation ?

## 20. Decision produit recommandee

Pour maximiser la vitesse d'execution et limiter le risque, la recommandation pour le MVP est :
- backend Python ;
- execution en CLI ;
- support Modbus TCP uniquement pour la v1 ;
- connexion TCP persistante unique ;
- scan strictement read-only ;
- profilage de debit prudent avant scan quand une sonde valide est disponible ;
- gouverneur de frequence actif pendant le scan ;
- exports JSON + CSV ;
- architecture modulaire preparee pour des decodeurs, strategies et protocoles futurs.

## 21. Resume executif

Le MVP vise a creer un outil de cartographie Modbus TCP prudent, utile et extensible. Sa mission n'est pas d'expliquer automatiquement la machine, mais de reveler ce qui est lisible, de structurer les donnees brutes et de fournir une base fiable pour l'analyse R&D. Le succes du MVP reposera sur quatre piliers :
- securite operationnelle ;
- robustesse du scan adaptatif ;
- profilage de debit non destructif ;
- qualite des exports pour l'exploitation humaine.
