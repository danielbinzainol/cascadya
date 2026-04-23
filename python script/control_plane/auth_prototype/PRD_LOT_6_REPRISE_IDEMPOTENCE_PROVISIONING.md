# PRD - Lot 6 - Reprise deterministe, idempotence de provisioning et mode operateur VM

## 1. Objet

Ce document definit le lot 6 du Control Panel au 1 avril 2026, dans la
continuite des lots 4 et 5 :

- lot 4 : workflow complet `remote-unlock + edge-agent` ;
- lot 5 : verification E2E NATS, separation des chemins reseau et probe broker
  HTTPS.

Le lot 6 ne remplace pas ces lots. Il formalise un sujet apparu pendant les
tests reels du 1 avril 2026 :

- le flux de provisioning prouve deja une valeur fonctionnelle ;
- mais un rerun apres echec partiel n'est pas encore suffisamment
  deterministe ;
- la reprise manuelle depuis la VM `control-panel` reste necessaire pour
  debloquer le terrain ;
- les etats partiels laisses sur le control plane, le broker ou l'IPC peuvent
  deplacer le point de rupture d'un rerun vers une autre etape.

Le but du lot 6 est donc de rendre le provisioning :

- rejouable ;
- explicable ;
- repris manuellement de facon fiable ;
- pilotable selon deux modes operateur complementaires :
  - `auto` pour derouler tout le workflow ;
  - `manual` pour declencher seulement certaines playbooks ;
- moins sensible aux artefacts orphelins et aux transitions reseau
  intermediaires.

## 2. Contexte et constats du 1 avril 2026

Les essais reels du 1 avril 2026 sur `control-panel-DEV1-S`,
`broker-DEV1-S` et `cascadya-ipc-10-109` ont montre un comportement recurrent :

- un premier run peut valider plusieurs etapes successives ;
- un echec intermediaire laisse un etat partiel sur disque ou sur les VMs ;
- un rerun peut ensuite echouer plus loin ou plus tot, pour une raison
  differente, alors meme que l'operateur pense rejouer "le meme flux".

Exemples observes le 1 avril 2026 :

- step broker `remote-unlock-deploy-broker.yml` casse sur un
  `Permission denied` en lecture de
  `provisioning_ansible/.tmp/cascadya-remote-unlock/broker/server.key`
  apres regeneration manuelle avec ownership `root` sur le control-plane ;
- rerun manuel impossible apres suppression du job web car les fichiers
  `generated/<device_id>.job-<N>-...-secrets.json` n'existent plus ;
- le token du probe broker etait disponible dans
  `/etc/control-panel/auth-prototype.env`, mais pas resolu de facon uniforme
  par le role broker ;
- dans un run frais, les steps 1 a 6 passent, puis
  `remote-unlock-bootstrap.yml` finit par perdre l'acces SSH sur
  `192.168.10.109:22`, signe qu'une transition reseau a change les conditions
  de transport en cours de workflow.

Conclusion produit :

- les playbooks sont deja partiellement idempotents pris unitairement ;
- le workflow de bout en bout n'est pas encore resume-safe apres echec ;
- l'operateur manque d'un mode "reprise controlee" depuis la VM
  `control-panel`.

Addendum observe le `13 avril 2026` sur `cascadya-ipc-10-109` :

- le workflow complet expose maintenant `18` steps, avec `wazuh-agent` et
  `ipc-alloy` entre `remote-unlock` et `edge-agent` ;
- un run `real/auto` a progresse jusqu'a `remote-unlock-bootstrap.yml`, puis a
  echoue sur un timeout SSH `Connection timed out during banner exchange` ;
- la reprise manuelle canonique depuis `/opt/control-panel/control_plane/auth_prototype`
  a ensuite permis de valider tous les steps restants jusqu'a
  `edge-agent-nats-roundtrip.yml` ;
- les causes concretes mises en evidence pendant cette reprise sont :
  - rendu invalide de `cascadya-network-persist.service` par concatenation de
    lignes `ExecStart=` ;
  - absence d'un gate SSH robuste avant `edge-agent-deploy.yml` ;
  - dependance implicite du step final a `edge_agent_probe_broker_token`
    uniquement injecte par le runner auto ;
- les correctifs retenus dans le repo control-plane sont :
  - generation deterministe de l'unite
    `cascadya-network-persist.service` ;
  - attente explicite de connectivite SSH dans `edge-agent-deploy.yml` avant le
    role `edge-agent` ;
  - fallback environnement sur
    `AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_TOKEN` dans
    `edge-agent-nats-roundtrip.yml`.

## 3. Probleme produit a resoudre

Le produit ne doit pas seulement savoir "executer une liste de playbooks".

Il doit aussi :

- garder une interpretation stable de l'etat courant apres un echec ;
- savoir quelles etapes peuvent etre rejouees sans ambiguite ;
- expliciter quelles traces doivent etre conservees entre deux runs ;
- permettre une prise de main operateur en cours de workflow sans casser
  l'ordonnancement automatique ;
- eviter qu'un job supprime emporte les seuls secrets utilisables pour une
  reprise manuelle ;
- borner les transitions reseau qui changent la joignabilite de l'IPC au milieu
  d'un workflow.

## 4. Objectifs du lot 6

- Rendre la reprise apres echec partiel deterministe a l'echelle du workflow.
- Introduire un mode operateur clair pour relancer le flux depuis la VM
  `control-panel`.
- Introduire un dual-mode d'orchestration dans l'application :
  - `auto`
  - `manual`
- Permettre la bascule `auto` -> `manual` sans interrompre brutalement une
  etape deja en cours.
- Permettre la reprise `manual` -> `auto` exactement depuis le checkpoint
  atteint.
- Ne plus dependre exclusivement des fichiers
  `generated/<device_id>.job-<N>-...-secrets.json` pour une reprise manuelle.
- Rendre visibles les side effects de chaque etape avant et apres execution.
- Mieux separer :
  - les etapes purement locales au control-plane ;
  - les etapes broker ;
  - les etapes IPC avant mutation reseau ;
  - les etapes IPC apres mutation reseau ;
  - les etapes de verification seulement.
- Reduire les echec "deplace ailleurs" entre deux reruns.

## 5. Perimetre fonctionnel

### 5.1 Checkpoints de reprise par etape

Chaque etape du workflow doit declarer explicitement :

- ses preconditions ;
- ses artefacts attendus ;
- ses effets de bord distants ;
- son critere de succes observable ;
- la facon de la rejouer si ces artefacts existent deja.

Le runner doit pouvoir distinguer trois cas :

- `safe to skip` ;
- `safe to reconcile then continue` ;
- `unsafe to continue without operator action`.

### 5.2 Classification des etapes du workflow 1 -> 18

Le flux `full-ipc-wireguard-onboarding` doit etre relu comme suit :

- steps 1 a 3 :
  - artefacts controller + staging IPC ;
  - sensibles aux droits fichiers et a la disponibilite SSH initiale ;
- step 4 :
  - persistance reseau locale sur l'IPC ;
  - fige les adresses/routes detectees et prepare les reboot futurs ;
- steps 5 a 7 :
  - broker + Vault ;
  - sensibles a l'ownership du bundle `.tmp`, aux secrets broker et a
     l'exposition du probe HTTPS ;
- step 8 :
  - mutation reseau et bootstrap `remote-unlock` sur l'IPC ;
  - point de bascule critique car la joignabilite peut changer en cours de run ;
- steps 9 et 10 :
  - verification remote-unlock ;
  - ne doivent pas partir tant que la route SSH/`WireGuard` n'est pas
     revalidee ;
- steps 11 et 12 :
  - enrollment et verification `wazuh-agent` ;
  - dependent du manager Wazuh et de la route privee `IPC -> 10.42.1.7` ;
- steps 13 et 14 :
  - deploiement puis validation `node_exporter + Alloy` ;
  - dependent du chemin `IPC -> 10.42.1.4` et des routes de retour monitoring ;
- steps 15 a 18 :
  - bundle edge-agent, deploiement, validation et test NATS ;
  - dependent a la fois du broker, du bundle TLS, et du mode de transport NATS
    reel.

### 5.3 Secrets de reprise durables

Le lot 6 doit imposer la regle suivante :

- les jobs web peuvent continuer a materialiser des fichiers secrets
  temporaires ;
- mais une reprise manuelle ne doit pas dependre uniquement d'eux ;
- les secrets critiques doivent pouvoir etre reconstitues depuis
  `/etc/control-panel/auth-prototype.env` :
  - secrets SSH IPC ;
  - secrets SSH broker ;
  - token Vault broker ;
  - token probe broker.

### 5.4 Hygiene des artefacts controller

Le produit doit traiter explicitement les repertoires suivants comme des
artefacts sensibles de provisioning :

- `auth_prototype/generated/`
- `auth_prototype/provisioning_ansible/.tmp/cascadya-remote-unlock/`
- `auth_prototype/provisioning_ansible/.tmp/cascadya-edge-agent/`

Exigences :

- ownership coherent pour l'utilisateur applicatif du control-plane ;
- permissions compatibles avec un rerun lance par le site ;
- verification pre-step quand un playbook lit une cle privee ou un bundle
  genere localement.

### 5.5 Mode operateur depuis la VM control-panel

Le lot 6 introduit une attente produit claire :

- l'operateur doit pouvoir reprendre le flux directement depuis
  `/opt/control-panel/control_plane/auth_prototype` ;
- avec les inventories/vars deja generes ;
- sans devoir deviner quels secrets temporaires du job sont encore presents ;
- et avec un ordre manuel canonique documente.

Ce mode operateur doit rester aligne sur les memes playbooks que le site.

### 5.6 Gates reseau entre etapes

Le runner doit introduire des verifications explicites apres les etapes qui
modifient le reseau ou le transport :

- relecture de `ansible_host` effectif ;
- verification de la route SSH attendue ;
- verification de l'etat `wg0` quand le transport devient `WireGuard-first` ;
- blocage propre avec message explicite si l'etape suivante ne peut plus
  utiliser la meme cible SSH.

### 5.7 Dual-mode `auto` / `manual` dans le site

Le site doit permettre a l'operateur de choisir entre :

- mode `auto`
  - le workflow deroule de la prochaine etape `ready` jusqu'a completion,
    echec, pause demandee ou gate bloquant ;
- mode `manual`
  - l'operateur choisit explicitement quelles playbooks lancer pour des cas
    specifiques.

Traduction d'implementation retenue au 2 avril 2026 :

- le meme `provisioning_job` persiste le `dispatch_mode` ;
- `auto` prepare un job puis enchaine les steps dans l'ordre ;
- `manual` prepare le meme bundle d'artefacts mais garde les steps
  selectionnables pour lancer une playbook cible ;
- l'API d'execution accepte une `step_key` explicite pour rejouer un step
  manuel sans creer un runner parallele.

Regles de comportement :

- si l'operateur demande `manual` alors qu'une etape `auto` est en cours :
  - l'etape courante va jusqu'a sa fin ;
  - aucune nouvelle etape `auto` n'est dequeued ensuite ;
  - le job passe dans un etat `paused_for_manual` ;
- en mode `manual`, l'operateur peut lancer une ou plusieurs etapes
  explicitement autorisees ;
- quand l'operateur repasse en mode `auto`, le scheduler reprend depuis les
  checkpoints et statuts reellement atteints, pas depuis une position calculee
  en memoire.

### 5.8 Machine d'etat du job

Le dual-mode ne doit pas etre implemente comme deux runners differents.

Le produit doit garder :

- un seul job de provisioning ;
- un seul graphe d'etapes ;
- une seule source de verite pour les statuts de steps ;
- un mode de dispatch persistant sur le job.

Etats cibles supplementaires :

- `auto_running`
- `pause_requested`
- `paused_for_manual`
- `manual_running`
- `resume_requested`

Contrainte forte :

- une seule etape active a la fois par job ;
- aucune preemption brutale d'un playbook deja demarre ;
- toute transition de mode doit etre cooperative et persistante.

## 6. Hors perimetre volontaire

Le lot 6 ne couvre pas encore :

- un rollback automatise multi-etapes ;
- une remediaton automatique de toutes les erreurs reseau terrain ;
- les futures evolutions de performance et d'observabilite du hot flow NATS du
  lot 5 ;
- la reparation d'une image IPC defectueuse hors contrat de provisioning.

## 7. Mode operateur canonique cible

Le mode manuel direct depuis la VM `control-panel` doit suivre les principes
suivants :

- repartir des fichiers `generated/*.ini` et `generated/*.vars.json` deja
  produits par le site ;
- recharger l'environnement applicatif depuis
  `/etc/control-panel/auth-prototype.env` ;
- reconstruire si necessaire des `extra-vars` de secrets a partir de cet
  environnement ;
- rejouer les playbooks dans le meme ordre que l'UI ;
- verifier un gate de transport apres toute etape reseau avant de continuer.

Equivalent cote site :

- le mode `auto` et le mode `manual` doivent reutiliser exactement le meme
  moteur d'execution de steps ;
- le mode `manual` ne doit pas appeler des playbooks "a part" avec une autre
  logique ;
- la difference attendue porte uniquement sur la politique d'ordonnancement :
  - automatique
  - pas-a-pas operateur.

Ordre canonique a conserver :

1. `remote-unlock-generate-certs.yml`
2. `remote-unlock-generate-broker-certs.yml`
3. `remote-unlock-stage-certs.yml`
4. `ipc-persist-network-routing.yml`
5. `remote-unlock-prepare-broker-wireguard.yml`
6. `remote-unlock-deploy-broker.yml`
7. `remote-unlock-seed-vault-secret.yml`
8. `remote-unlock-bootstrap.yml`
9. `remote-unlock-preflight.yml`
10. `remote-unlock-validate.yml`
11. `wazuh-agent-deploy.yml`
12. `wazuh-agent-validate.yml`
13. `ipc-alloy-deploy.yml`
14. `ipc-alloy-validate.yml`
15. `edge-agent-generate-certs.yml`
16. `edge-agent-deploy.yml`
17. `edge-agent-validate.yml`
18. `edge-agent-nats-roundtrip.yml`

## 8. Exigences techniques cibles

### 8.1 Resume-safe sur les secrets

- le role broker doit savoir resoudre le token probe depuis l'environnement du
  control-plane ;
- la reprise manuelle ne doit pas casser si un job web a ete supprime ;
- les steps controller-only doivent aussi pouvoir resoudre leurs secrets
  critiques depuis l'environnement local (`EDGE_AGENT_VAULT_TOKEN` ou
  variables control-plane equivalentes) ;
- les messages d'erreur doivent indiquer si l'absence du secret provient :
  - d'un env manquant ;
  - d'un `job-*.json` absent ;
  - d'un `vars.json` incomplet.

### 8.2 Resume-safe sur les droits fichiers

- avant copie d'un bundle TLS local, le runner ou le playbook doit pouvoir
  verifier :
  - existence ;
  - taille non nulle ;
  - ownership lisible par le runner applicatif ;
  - mode coherent avec le type de fichier.

### 8.3 Resume-safe sur la cible SSH

- le runner doit tracer la cible SSH attendue avant chaque etape distante ;
- si `ansible_host` change implicitement apres mutation reseau, le produit doit
  l'afficher ;
- un timeout SSH apres bootstrap ne doit plus etre expose comme un echec
  "mysterieux", mais comme une rupture de transport entre deux checkpoints.
- les playbooks sensibles au flap SSH doivent pouvoir attendre explicitement le
  retour de la connectivite avant `Gathering Facts` ou avant leurs checks
  runtime.

### 8.4 Resume-safe sur les etapes de verification

- une etape `verify` ne doit pas masquer un echec plus tot dans le flux ;
- elle doit pouvoir lire les checkpoints des etapes precedentes ;
- elle doit distinguer :
  - "preconditions non satisfaites" ;
  - "service deploye mais unhealthy" ;
  - "transport indisponible".

### 8.5 Scheduler cooperatif auto/manual

La methode recommandee est une machine d'etat cooperative avec curseur
persistant de workflow.

Concepts minimaux :

- `dispatch_mode`
  - `auto`
  - `manual`
- `runner_state`
  - `idle`
  - `running`
  - `pause_requested`
  - `paused_for_manual`
  - `manual_running`
  - `failed`
  - `succeeded`
- `current_step_key`
- `next_ready_step_key`
- `lock_version` ou equivalent pour eviter les races entre UI et worker
  backend.

Regles d'implementation :

- le worker `auto` ne prend une nouvelle etape que si :
  - `dispatch_mode=auto`
  - `runner_state` autorise l'enchainement
  - aucune pause n'a ete demandee ;
- un clic vers `manual` ne tue jamais le process Ansible courant ;
- il pose seulement `pause_requested=true` ;
- a la fin de l'etape courante, le worker persiste `paused_for_manual` puis
  s'arrete proprement ;
- une action manuelle execute une step via le meme executor que le mode auto ;
- apres cette action, le moteur reindexe tous les steps, recalcule
  `next_ready_step_key`, puis laisse la main a l'operateur ou a la reprise
  `auto`.

Pattern a retenir :

- `cooperative pause/resume`, pas `hard stop/resume` ;
- `single job state machine`, pas deux files concurrentes ;
- `same step executor`, pas un chemin shell parallele distinct.

### 8.6 Garde-fous de selection manuelle

Le mode `manual` ne doit pas permettre un ordre arbitraire sans garde-fous.

L'UI peut proposer :

- les steps `ready` ;
- les steps `failed` a rejouer ;
- les steps `succeeded` seulement si la policy du step autorise explicitement
  un `reconcile/rerun`.

Le backend reste la source de verite finale :

- il revalide la policy du step avant execution ;
- il refuse un lancement manuel qui casserait les preconditions declarees ;
- il journalise la raison du refus.

## 9. Milestones proposees

### 9.1 Milestone 6A - Hygiene controller et secrets durables

Livrables minimaux :

- resolution systematique des secrets critiques depuis l'env control-plane ;
- normalisation des permissions des bundles `.tmp` ;
- doc operatoire mise a jour pour la reprise manuelle.

### 9.2 Milestone 6B - Checkpoints de workflow et resume policies

Livrables minimaux :

- statut `skip / reconcile / fail` par etape ;
- trace produit des artefacts et side effects deja presents ;
- reprise d'un workflow sans supposer un etat "tout ou rien".

### 9.3 Milestone 6C - Gates reseau post-bootstrap

Livrables minimaux :

- revalidation explicite du transport SSH apres mutation reseau ;
- distinction claire entre echec playbook et perte de transport ;
- message operateur actionnable avant step 8.

### 9.4 Milestone 6D - Mode operateur complet depuis la VM

Livrables minimaux :

- procedure manuelle canonique pour rejouer les 18 steps ;
- mapping clair entre steps UI et commandes shell ;
- suppression de la dependance implicite aux `job-*.secrets.json` ephemeres.

### 9.5 Milestone 6E - Bascule auto/manual sans rupture

Livrables minimaux :

- selecteur de mode `auto` / `manual` sur la page provisioning ;
- pause cooperative de la file auto ;
- reprise `auto` depuis le vrai checkpoint persiste ;
- verrouillage anti-concurrence sur les transitions de mode ;
- audit trail des actions manuelles lancees au milieu d'un workflow.

## 9bis. Etat de validation au 13 avril 2026

Progression constatee apres le rerun terrain du `13 avril 2026` :

- `6A` est partiellement valide :
  - les secrets critiques broker/probe sont resolus depuis
    `/etc/control-panel/auth-prototype.env` ;
  - le step final `edge-agent-nats-roundtrip.yml` relit le token proxy depuis
    l'environnement du control-plane en reprise manuelle ;
- `6C` est partiellement valide mais renforce :
  - la perte de transport SSH est maintenant identifiable ;
  - `edge-agent-deploy.yml` attend explicitement le retour de SSH avant son
    deploiement ;
  - un rerun `real/auto` ulterieur le `13 avril 2026` est alle jusqu'au
    `DONE provisioning finished (real)` sur `18/18` steps ;
  - en revanche le runner auto n'introduit pas encore un gate reseau persistant
    entre `remote-unlock-bootstrap.yml` et les steps suivants ;
- `6D` est valide operatoirement :
  - la reprise manuelle depuis la VM `control-panel` a permis d'aller jusqu'au
    dernier step du workflow ;
  - l'ordre canonique des `18` steps a ete rejoue avec succes ;
  - la meme cible termine aussi maintenant en `real/auto` complet sur la
    topologie validee ;
- `6E` n'est pas encore livre cote produit :
  - la pause/resume cooperative auto/manual reste un objectif d'implementation
    backend/UI.

Point ouvert hors perimetre immediat du repo :

- la persistance des routes de retour sur `monitoring-DEV1-S` reste a
  industrialiser dans le repo `ansible-monitoring`, meme si le chemin a ete
  valide manuellement pour permettre `ipc-alloy`.

## 10. Validation attendue

Le lot 6 sera considere valide si, pour un echec injecte volontairement au
milieu du workflow :

- le site montre clairement l'etape fautive ;
- un rerun n'introduit pas un nouveau point de rupture non explique ;
- la reprise manuelle depuis la VM control-panel est possible sans artefacts
  secrets ephemeres du job supprime ;
- les etapes 1 a 18 peuvent etre rejouees dans l'ordre avec des gates
  explicites ;
- une bascule `auto` -> `manual` en milieu de workflow ne relance pas une
  deuxieme file concurrente ;
- un retour `manual` -> `auto` reprend sur la prochaine step eligible sans
  reexecuter aveuglement tout le workflow ;
- le produit distingue enfin un vrai bug de provisioning d'un etat partiel a
  reconcilier.

## 11. Definition of Done retenue

Le lot 6 pourra etre considere comme atteint quand :

- le provisioning est non seulement fonctionnel, mais aussi reprenable ;
- les erreurs de rerun ne "se deplacent" plus silencieusement d'une etape a une
  autre ;
- les secrets critiques de reprise sont disponibles depuis la VM
  `control-panel` sans dependre d'un job web encore vivant ;
- les transitions reseau du step 8 sont bornees par un gate explicite avant les
  steps 9 a 18 ;
- la bascule `auto` / `manual` repose sur une machine d'etat cooperative
  persistante et non sur deux runners concurrents ;
- l'operateur terrain dispose d'un chemin manuel documente, stable et aligne
  sur le flux du site.
