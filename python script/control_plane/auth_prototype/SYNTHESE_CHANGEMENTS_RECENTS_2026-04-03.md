# Synthese - changements recents Control Panel

Date de reference : 3 avril 2026

## 1. Vue d'ensemble

Ces derniers lots ont permis de faire passer le Control Panel d'un etat
principalement demonstratif a un etat beaucoup plus proche d'un produit
operable sur l'infrastructure reelle.

Les evolutions se structurent autour de 4 axes :

- le dashboard principal est maintenant pilote par des donnees reelles de sites,
  d'assets et de jobs de provisioning ;
- l'observabilite E2E et la partie `Orders` permettent de tester et comprendre
  le flux chaud `Control Panel -> Broker -> IPC` ;
- le provisioning IPC est plus robuste, plus pilotable et mieux adapte aux
  incidents reseau terrain ;
- une VM Wazuh Manager dediee a ete preparee et installee pour ouvrir le sujet
  supervision securite de l'IPC.

## 2. Dashboard principal

Le dashboard a ete enrichi pour devenir une vraie vue operateur :

- les sites visibles ne sont plus une liste figee de demonstration ;
- l'operateur peut composer le dashboard a partir de sites issus de jobs de
  provisioning `succeeded` ;
- le dashboard charge maintenant les sites, les assets inventory et les jobs
  depuis les APIs reelles.

Une nouvelle logique de regroupement par entreprise a ete ajoutee :

- l'operateur peut creer des entreprises sur le dashboard ;
- il peut y rattacher des IPC deja visibles dans la vue ;
- chaque entreprise peut etre ouverte ou refermee ;
- les IPC rattaches sont affiches dans la section correspondante ;
- l'operateur peut enrichir localement chaque rattachement avec :
  - un `Lieu du site`
  - une `Region`

Une couche de recherche et de filtrage a aussi ete ajoutee :

- recherche texte par site, ville, region, entreprise ou IPC ;
- tri alphabetique ascendant / descendant ;
- filtre par lieu ;
- filtre par region ;
- filtre par entreprise.

Point important :

- dans cette premiere version, les entreprises, les rattachements et les champs
  `Lieu du site` / `Region` sont persistants dans le navigateur via
  `localStorage` ;
- ils ne sont donc pas encore partages entre plusieurs operateurs tant qu'un
  backend `companies` n'a pas ete introduit.

## 3. Observabilite E2E et Orders

Le lot E2E a fortement progresse.

L'ecran E2E permet maintenant :

- de choisir un flux `ems-site` ou `ems-light` ;
- de distinguer le cas `ems-site` cible par IPC et le cas `ems-light`
  singleton ;
- de travailler en `mode manuel` ou `mode auto` ;
- en manuel, de definir le nombre de mesures et la cadence ;
- en auto, de definir une frequence de test ;
- de tracer un graphe d'evolution dans le temps ;
- de vider ce graphe avec `Reset graph`.

La lecture des temps a ete clarifiee :

- le RTT actif est affiche avec et sans `Traitement broker` ;
- le terme `proxy broker` a ete remplace par `Traitement broker` pour etre plus
  lisible pour un non-specialiste ;
- le chemin `ems-light` a ete aligne sur la meme logique de decomposition que
  `ems-site` quand la connexion est disponible.

La partie `Orders` permet maintenant :

- de voir le flux `cascadya.routing.command` observe par le broker ;
- de piloter un `watchdog ping` ;
- d'utiliser un panneau `Execution` avec commandes placeholder.

Sur le plan du diagnostic, cela a permis de mieux distinguer :

- les problemes reseau reels ;
- les problemes de subscriber NATS absents ;
- les derivees de RTT sur des canaux distincts tels que
  `gateway_modbus` et `telemetry_publisher`.

## 4. Provisioning IPC et robustesse reseau

Le provisioning IPC a ete etendu pour mieux coller aux besoins terrain :

- un mode `auto` permet de jouer l'ensemble des playbooks dans l'ordre ;
- un mode `manuel` permet de lancer uniquement un playbook cible ;
- cela rend les reprises plus simples apres incident ou apres un rerun partiel.

Une nouvelle etape de persistance reseau a ete ajoutee pour l'IPC :

- les IPs et routages utiles peuvent etre figes sur les interfaces voulues ;
- l'objectif est d'eviter de reperdre les bons mappings au reboot ;
- cela adresse directement un probleme constate en reel lors d'un redemarrage
  d'IPC et de simulateur Modbus.

Cette capacite est importante car les incidents observes ont montre que :

- une inversion d'IP entre les interfaces terrain peut casser le chemin vers le
  simulateur Modbus ;
- si le simulateur ou le mapping reseau tombe, `gateway_modbus` et
  `telemetry_publisher` disparaissent de NATS ;
- le Control Panel remonte alors des erreurs `NoRespondersError`, non pas parce
  que le broker est en panne, mais parce qu'aucun edge-agent n'est encore
  abonne au sujet request/reply.

## 5. Wazuh

Le chantier Wazuh a avance sur la partie infrastructure et plateforme.

Ce qui est deja fait :

- formalisation du besoin dans un PRD dedie ;
- definition des regles d'ouverture reseau pour une VM `wazuh-Dev1-S` ;
- creation de la VM via Terraform avec un sizing reduit `4 vCPU / 8 Go RAM /
  50 Go data` adapte au lab ;
- preparation du disque data ;
- installation du stack Wazuh all-in-one :
  - indexer
  - manager
  - filebeat
  - dashboard

Etat actuel :

- la plateforme Wazuh est operationnelle ;
- le dashboard web repond ;
- l'agent IPC n'est pas encore integre dans le workflow automatise de
  provisioning, car un point de cadrage avec la direction etait prevu avant
  implementation.

## 6. Pourquoi ces choix

Les choix recents ont ete faits pour 3 raisons :

- fiabilite terrain : mieux survivre aux reboots, aux pertes de routage et aux
  incidents reseau reels ;
- lisibilite operateur : rendre les informations comprenables par quelqu'un qui
  n'est pas forcement specialiste NATS ou reseau ;
- progressivite produit : livrer vite une valeur exploitable sans bloquer sur
  un backend complet quand une persistance locale navigateur suffit pour une
  premiere iteration.

## 7. Prochaines suites logiques

Les prochaines etapes naturelles sont :

- transformer le regroupement `Entreprises` en donnee backend partagee si la
  fonctionnalite doit devenir multi-operateur ;
- industrialiser l'installation `wazuh-agent` sur l'IPC comme playbook de
  provisioning ;
- continuer la stabilisation reseau de l'IPC pour fiabiliser les tests E2E
  apres reboot ;
- consolider les verifications post-deploiement dans les workflows manuels et
  automatiques.
