# PRD - Contrat Modbus Rev02 SteamSwitch / SBC

Date: 2026-04-21
Source fonctionnelle: `Table d'echange concept - Rev 02 du 2026 04 15.xlsm`
Scope: commandes SteamSwitch, planificateur SBC, simulateur Modbus, gateway IPC, telemetrie edge et panneau Orders.

## 1. Objectif

Le but est de rendre le flux SteamSwitch/SBC conforme a la revision 2 de la table d'echange pour les fonctions testees bout a bout:

- ajout, modification et suppression des ordres;
- RAZ planificateur;
- visualisation du planificateur trie automatiquement par date/heure;
- calcul et lecture du CRC planificateur;
- controles fonctionnels C1/C2/C3 avec statuts d'operation;
- surveillance horloge/watchdog automate;
- exposition d'une documentation lisible depuis la page Orders.

Cette migration remplace le mapping laboratoire historique par le mapping officiel Rev02 pour les ordres et le planificateur.

## 2. Non-objectifs et limite importante

La table Excel Rev02 contient aussi de nombreuses variables procede hors planificateur. Le present changement ne pretend pas piloter toute l'usine physique depuis le simulateur.

Il fait deux choses strictes:

- aligner a 100% le contrat des ordres, triggers, statuts et slots planificateur utilise par SteamSwitch;
- isoler les signaux propres au digital twin dans une extension `%MW9000+`, pour ne plus collisionner avec les plages officielles Excel;
- exposer un miroir procede Rev02 decale dans une zone haute selon la regle `registre_simule = registre_reel + 9200`.

Donc `%MW1000+`, `%MW1044+` et `%MW8100+` sont le contrat Rev02. `%MW9000+` reste une extension interne runtime. Les variables procede Rev02 lues en simulation sont disponibles en `%MW9200+`, avec un mapping explicite vers les registres reels LCI.

## 3. Acteurs et fichiers

- Gateway IPC: `provisioning_ansible/roles/edge-agent/files/src/agent/gateway_modbus_sbc.py`
- Simulateur SBC: `modbus_simulator/src/main_sim.py`
- Miroir procede Rev02 simulateur: `modbus_simulator/src/rev02_process.py`
- Scheduler simulateur: `modbus_simulator/src/scheduler.py`
- Monitor local simulateur: `modbus_simulator/src/monitor.py`
- Telemetry publisher IPC: `provisioning_ansible/roles/edge-agent/files/src/agent/telemetry_publisher.py`
- UI Orders: `frontend/src/modules/orders/views/OrdersView.vue`
- UI Monitor Orders: `frontend/src/modules/orders/views/OrdersMonitorView.vue`

### 3.1 Chemins exacts dans le repo local

Depuis le workspace local `python script/control_plane`, les fichiers a ouvrir pour expliquer le flux sont:

| Role | Fichier repo | Ce qu'il faut expliquer |
|---|---|---|
| PRD / support fonctionnel | `auth_prototype/PRD_MODBUS_REV02_REGISTER_CONTRACT.md` | Carte registre, mecanismes, statuts, preuves de validation. |
| Gateway IPC | `auth_prototype/provisioning_ansible/roles/edge-agent/files/src/agent/gateway_modbus_sbc.py` | Reception commande NATS, encodage Rev02, write Modbus, triggers, read_plan, CRC. |
| Telemetry IPC | `auth_prototype/provisioning_ansible/roles/edge-agent/files/src/agent/telemetry_publisher.py` | Lecture `%MW250-%MW256`, `%MW9000+`, miroir procede `%MW9200+`, `%MW9070+`, publication NATS telemetry. |
| Serveur Modbus simulateur | `auth_prototype/modbus_simulator/src/main_sim.py` | Creation serveur Modbus, horloge/watchdog, runtime `%MW9000+`, appel du miroir procede et boucle physique. |
| Miroir procede simulateur | `auth_prototype/modbus_simulator/src/rev02_process.py` | Ecriture des variables procede Rev02 dans la zone haute `reel + 9200`, sans toucher les registres terrain bas. |
| Planificateur simulateur | `auth_prototype/modbus_simulator/src/scheduler.py` | Coeur Rev02: triggers, validation, tri, slots `%MW8120+`, CRC `%MW8101`, execution ordre. |
| Monitor simulateur | `auth_prototype/modbus_simulator/src/monitor.py` | Affichage humain des registres Rev02 et runtime digital twin. |
| Page Orders | `auth_prototype/frontend/src/modules/orders/views/OrdersView.vue` | Formulaire, validation UI, preview CRC, section repliable de cartographie registre. |
| Monitor web Orders | `auth_prototype/frontend/src/modules/orders/views/OrdersMonitorView.vue` | Vue dynamique du planificateur, du runtime et du miroir procede en second onglet. |

### 3.2 Chemins exacts sur les VMs

| VM | Fichier deploye | Correspondance repo |
|---|---|---|
| IPC `cascadya@192.168.10.109` | `/data/cascadya/agent/gateway_modbus_sbc.py` | `provisioning_ansible/roles/edge-agent/files/src/agent/gateway_modbus_sbc.py` |
| IPC `cascadya@192.168.10.109` | `/data/cascadya/agent/telemetry_publisher.py` | `provisioning_ansible/roles/edge-agent/files/src/agent/telemetry_publisher.py` |
| Simulateur `cascadya@192.168.50.2` | `/home/cascadya/simulator_sbc/main_sim.py` | `modbus_simulator/src/main_sim.py` |
| Simulateur `cascadya@192.168.50.2` | `/home/cascadya/simulator_sbc/rev02_process.py` | `modbus_simulator/src/rev02_process.py` |
| Simulateur `cascadya@192.168.50.2` | `/home/cascadya/simulator_sbc/scheduler.py` | `modbus_simulator/src/scheduler.py` |
| Simulateur `cascadya@192.168.50.2` | `/home/cascadya/simulator_sbc/monitor.py` | `modbus_simulator/src/monitor.py` |
| Control Panel `ubuntu@51.15.115.203` | `/opt/control-panel/control_plane/auth_prototype/frontend/src/modules/orders/views/OrdersView.vue` | `frontend/src/modules/orders/views/OrdersView.vue` |
| Control Panel `ubuntu@51.15.115.203` | `/opt/control-panel/control_plane/auth_prototype/frontend/src/modules/orders/views/OrdersMonitorView.vue` | `frontend/src/modules/orders/views/OrdersMonitorView.vue` |

### 3.3 Ordre conseille pour expliquer le code ligne par ligne

1. Commencer par `scheduler.py`: c'est la reference du comportement SBC. Expliquer les constantes de registres, les statuts, puis le cycle `_process_exchange_bits -> _handle_order_upsert -> _sync_queue_to_modbus -> _execute_due_orders`.
2. Passer a `gateway_modbus_sbc.py`: montrer comment une commande applicative devient un bloc `%MW1000+`, comment le trigger `%MW1044` est pose, puis comment `read_plan` relit `%MW8100+`.
3. Montrer `main_sim.py`: expliquer que le serveur Modbus publie l'horloge `%MW250-%MW256`, les signaux runtime `%MW9000+`, et appelle le scheduler.
4. Montrer `rev02_process.py`: expliquer le pare-feu memoire `reel + 9200` et pourquoi le simulateur ne doit pas ecrire dans `%MW388/%MW508/%MW574`.
5. Montrer `telemetry_publisher.py`: expliquer que ce service ne commande rien, il lit seulement les registres runtime/procede et publie la telemetrie.
6. Montrer `monitor.py`: expliquer que c'est l'outil de demonstration locale pour voir les memes registres a l'ecran.
7. Finir avec `OrdersView.vue` et `OrdersMonitorView.vue`: montrer la validation operateur, le payload, la preview CRC, la section repliable qui documente la table et la vue dynamique de la file.

## 4. Carte registre officielle Rev02 utilisee

### 4.1 Mode, planification, horloge et watchdog

| Registre | Nom Rev02 | Sens | Proprietaire | Fonction |
|---|---|---|---|---|
| `%MW238 bit 0` | `EX10_DISTANT` | SBC vers SteamSwitch | SBC | Mode distant actif. Le simulateur force la valeur mot a `1`. |
| `%MW245 bit 8` | `EX10_PLANIF` | SBC vers SteamSwitch | SBC | Planificateur actif. Le simulateur force bit 8, donc mot `256`. |
| `%MW250` | `GE00_ANNEE` | SBC vers SteamSwitch | SBC | Annee automate. |
| `%MW251` | `GE00_MOIS` | SBC vers SteamSwitch | SBC | Mois automate. |
| `%MW252` | `GE00_JOUR` | SBC vers SteamSwitch | SBC | Jour automate. |
| `%MW253` | `GE00_HEURE` | SBC vers SteamSwitch | SBC | Heure automate. |
| `%MW254` | `GE00_MINUTE` | SBC vers SteamSwitch | SBC | Minute automate. |
| `%MW255` | `GE00_SECONDE` | SBC vers SteamSwitch | SBC | Seconde automate, surveillee par le gateway. |
| `%MW256` | `GE00_WATCHDOG` | SBC vers SteamSwitch | SBC | Mot de vie incremente chaque seconde. Le gateway le lit, il ne l'ecrit plus. |
| `%MW600-%MW605` | `DT00_*` | SteamSwitch vers SBC | SteamSwitch | Zone d'ecriture date/heure. Reservee, non utilisee comme horloge simulateur. |

### 4.2 Ordre en preparation

Le gateway ecrit l'ordre complet dans `%MW1000-%MW1043`, puis pose un trigger. Le simulateur lit cette zone, valide, copie dans le planificateur si valide, ecrit le statut, puis remet le trigger a `0`.

| Registre | Champ | Type | Detail |
|---|---|---|---|
| `%MW1000-%MW1001` | `IB02_OPERATION_ORDRE.ID` | `UDINT` | ID BDD sur deux mots, mot bas puis mot haut (`MODBUS_U32_WORD_ORDER=low_word_first`). `0` ou negatif refuse. |
| `%MW1002` | Jour | `INT` | Jour execution. |
| `%MW1003` | Mois | `INT` | Mois execution. |
| `%MW1004` | Annee | `INT` | Annee execution AAAA. |
| `%MW1005` | Heure | `INT` | Heure execution. |
| `%MW1006` | Minute | `INT` | Minute execution. |
| `%MW1007` | Seconde | `INT` | Seconde execution. |
| `%MW1008` | C1.ATT1 | `INT` | Profil: `2`, `3`, `4`, `5`, `6`. |
| `%MW1010-%MW1011` | C1.ATT2 | `REAL` | Limitation puissance en kW, IEEE-754 avec mots Modbus inverses: mot bas puis mot haut. Plage projet: `[0;50]`. |
| `%MW1012-%MW1013` | C1.ATT3 | `REAL` | Consigne ELEC en bar. Plage `[0;18]`. |
| `%MW1014` | C1.ATT4 | `INT` | Reserve projet, doit rester `0`. |
| `%MW1015` | C1.ATT5 | `INT` | Reserve projet, doit rester `0`. |
| `%MW1016` | C1.ATT6 | `INT` | Reserve projet, doit rester `0`. |
| `%MW1018` | C2.ATT1 | `INT` | Activation MET. Selon profil: `5` pour profils `2`/`5`, sinon `0`. |
| `%MW1020-%MW1021` | C2.ATT2 | `REAL` | Type MET. Valeurs fonctionnelles: `0` ou `2` selon profil. |
| `%MW1022-%MW1023` | C2.ATT3 | `REAL` | Consigne MET en bar. `[0;18]`; obligatoire `0` pour profils `3`/`4`/`6`. |
| `%MW1024` | C2.ATT4 | `INT` | Reserve projet, doit rester `0`. |
| `%MW1025` | C2.ATT5 | `INT` | Reserve projet, doit rester `0`. |
| `%MW1026` | C2.ATT6 | `INT` | Reserve projet, doit rester `0`. |
| `%MW1028` | C3.ATT1 | `INT` | Secours. `0` ou `1` pour profils `2`/`5`; `0` pour profils `3`/`4`/`6`. |
| `%MW1029-%MW1033` | C3.ATT2..ATT6 | `INT` | Reserves projet, doivent rester `0`. |
| `%MW1034-%MW1043` | Reserves | `INT[10]` | Reserve protocole, forcee a `0`. |

Les champs C1/C2 de type `REAL` sont encodes IEEE-754 32 bits en big-endian dans chaque mot, avec ordre des mots Modbus `mot bas puis mot haut` (`MODBUS_FLOAT_WORD_ORDER=low_word_first`). Exemple: `5.3` bar est ecrit comme deux mots Modbus, et non comme `53`.

Les champs `UDINT` Rev02 (`Order ID` dans `%MW1000-%MW1001`, slots `%MW8120+`, runtime actif `%MW9071-%MW9072`) utilisent le meme principe d'ordre de mots: mot bas puis mot haut (`MODBUS_U32_WORD_ORDER=low_word_first`). Ce choix securise l'alignement avec l'automate reel LCI lorsque son processeur interprete les mots 16 bits dans l'ordre inverse de l'ancien simulateur.

### 4.3 Triggers et statuts operationnels

| Registre | Fonction | Sens | Mecanisme |
|---|---|---|---|
| `%MW1044 bit 0` | Ajout/modification | SteamSwitch vers SBC | Gateway ecrit `1`; simulateur traite puis remet `0`. |
| `%MW1045` | Statut ajout/modification | SBC vers SteamSwitch | Code resultat de l'ajout/modification. |
| `%MW1056 bit 0` | Suppression | SteamSwitch vers SBC | Gateway ecrit `1`; simulateur traite puis remet `0`. |
| `%MW1057` | Statut suppression | SBC vers SteamSwitch | Code resultat de suppression. |
| `%MW1068 bit 0` | RAZ planificateur | SteamSwitch vers SBC | Gateway ecrit `1`; simulateur vide la file puis remet `0`. |
| `%MW1069` | Statut RAZ | SBC vers SteamSwitch | Code resultat de RAZ. |

Si plusieurs triggers sont actifs en meme temps, le simulateur renvoie `8` sur les statuts d'operation et remet les triggers a `0`.

### 4.4 Planificateur officiel

| Registre | Nom | Type | Fonction |
|---|---|---|---|
| `%MW8100` | `IB02_PLANIFICATEUR_ETAT` | `INT` | `0=OK`, `1=NOK/plein`. Le simulateur met `1` quand les 10 slots sont pleins. |
| `%MW8101` | `IB02_PLANIFICATEUR_CRC` | `INT` | CRC16 Modbus calcule sur les 10 slots de 46 mots. |
| `%MW8102` | `IB02_PLANIFICATEUR_CRC_ETAT` | `INT` | `1` pendant recalcul/copie, `0` quand stable. |
| `%MW8120` | Slot 0 | 46 mots | Premier ordre planifie. |
| `%MW8166` | Slot 1 | 46 mots | Deuxieme ordre. |
| `%MW8212` | Slot 2 | 46 mots | Troisieme ordre. |
| `%MW8258` | Slot 3 | 46 mots | Quatrieme ordre. |
| `%MW8304` | Slot 4 | 46 mots | Cinquieme ordre. |
| `%MW8350` | Slot 5 | 46 mots | Sixieme ordre. |
| `%MW8396` | Slot 6 | 46 mots | Septieme ordre. |
| `%MW8442` | Slot 7 | 46 mots | Huitieme ordre. |
| `%MW8488` | Slot 8 | 46 mots | Neuvieme ordre. |
| `%MW8534` | Slot 9 | 46 mots | Dixieme ordre. |

Chaque slot utilise la meme structure que l'ordre en preparation, avec deux mots supplementaires:

- offset `+44`: statut de l'ordre dans le slot;
- offset `+45`: padding/reserve.

Le stride est donc `46`, pas `20`. La capacite officielle retenue est `10` ordres, pas `15`.

## 5. Regles C1/C2/C3 implementees

| Profil | C1-1 | C1-2 Limitation puissance | C1-3 Consigne ELEC | C2-1 | C2-2 Type MET | C2-3 Consigne MET | C3-1 Secours |
|---|---:|---|---|---:|---|---|---|
| `2.5.*` | `2` | `[0;50] kW` | `[0;18] bar` | `5` | `0 ou 2` | `[0;18] bar` | `0 ou 1` |
| `3.0.0` | `3` | `[0;50] kW` | `[0;18] bar` | `0` | `0` | `0 obligatoire` | `0 obligatoire` |
| `4.0.0` | `4` | `[0;50] kW` | `[0;18] bar` | `0` | `0` | `0 obligatoire` | `0 obligatoire` |
| `5.5.*` | `5` | `[0;50] kW` | `[0;18] bar` | `5` | `0 ou 2` | `[0;18] bar` | `0 ou 1` |
| `6.0.0` | `6` | `0 obligatoire` | `0 obligatoire` | `0` | `0` | `0 obligatoire` | `0 obligatoire` |

Champs reserves obligatoires a `0`:

- C1-4, C1-5, C1-6;
- C2-4, C2-5, C2-6;
- C3-2, C3-3, C3-4, C3-5, C3-6;
- reserves `%MW1034-%MW1043`.

## 6. Statuts operationnels

### 6.1 Ajout/modification `%MW1045`

| Code | Sens |
|---:|---|
| `0` | Succes. |
| `1` | Planificateur plein. |
| `2` | Annee invalide, hors annee courante ou annee courante + 1. |
| `3` | Mois invalide. |
| `4` | Impossible de verifier le jour pour le couple annee/mois. |
| `5` | Jour invalide. |
| `6` | Date anterieure a la date automate. |
| `7` | Meme date mais heure anterieure a l'heure automate, ou heure/minute/seconde invalide. |
| `8` | Plusieurs triggers actifs en meme temps. |
| `20` | ID invalide. |
| `110` | C1-1 invalide. |
| `120` | C1-2 invalide. |
| `130` | C1-3 invalide. |
| `140` | C1-4 invalide. |
| `150` | C1-5 invalide. |
| `160` | C1-6 invalide. |
| `210` | C2-1 invalide. |
| `220` | C2-2 invalide. |
| `230` | C2-3 invalide. |
| `240` | C2-4 invalide. |
| `250` | C2-5 invalide. |
| `260` | C2-6 invalide. |
| `310` | C3-1 invalide. |
| `320` | C3-2 invalide. |
| `330` | C3-3 invalide. |
| `340` | C3-4 invalide. |
| `350` | C3-5 invalide. |
| `360` | C3-6 invalide. |
| `900` | Erreur interne simulateur/planificateur. |

### 6.2 Suppression `%MW1057`

| Code | Sens |
|---:|---|
| `0` | Succes. |
| `1` | Date/heure non nulle dans le buffer de suppression. |
| `8` | Plusieurs triggers actifs en meme temps. |
| `20` | ID invalide. |
| `21` | ID inexistant. |
| `100` | Champs C1 non nuls pendant suppression. |
| `200` | Champs C2 non nuls pendant suppression. |
| `300` | Champs C3 non nuls pendant suppression. |
| `900` | Erreur interne simulateur/planificateur. |

### 6.3 RAZ `%MW1069`

| Code | Sens |
|---:|---|
| `0` | Succes. |
| `8` | Plusieurs triggers actifs en meme temps. |

## 7. Mecanismes d'interaction

### 7.1 Ajout ou modification d'un ordre

1. Le Control Panel envoie une commande NATS sur `cascadya.routing.command`.
2. Le gateway IPC verifie que la cible correspond a `EDGE_AGENT_INSTANCE_ID`.
3. Le gateway construit le bloc `%MW1000-%MW1043`.
4. Les valeurs `UDINT` et `REAL` sont encodees sur deux mots avec ordre Modbus `mot bas puis mot haut`.
5. Le gateway relit `%MW1000-%MW1043` pour verifier le write Modbus.
6. Le gateway ecrit `%MW1044=1`.
7. Le simulateur detecte le trigger, valide ID/date/C1/C2/C3.
8. Le simulateur ajoute ou remplace l'ordre par ID, trie la file par date/heure, ecrit les slots `%MW8120+`.
9. Le simulateur calcule le CRC16 sur les `10 * 46 = 460` mots du planificateur.
10. Le simulateur ecrit `%MW8101`, remet `%MW8102=0`, ecrit `%MW1045`, puis remet `%MW1044=0`.
11. Le gateway attend le retour a `0` du trigger, lit `%MW1045` et repond au request/reply NATS.

En mode normal, la validation UI et la validation gateway bloquent les erreurs operateur avant l'ecriture Modbus. Pour les essais de securite PLC, un payload `upsert` peut porter simultanement `validation_mode=observe_only`, `allow_invalid_order_for_test=true` et `validation_bypass_reason=operator_requested_plc_security_test`: les alertes de validation restent visibles, mais le gateway ecrit quand meme `%MW1000-%MW1043`, pose `%MW1044`, puis laisse le SBC/simulateur produire le code officiel `%MW1045`. Ce mode est reversible, demande une action explicite dans l'UI, et ne supprime aucune regle de validation.

### 7.2 Suppression d'un ordre

1. Le gateway ecrit uniquement l'ID UDINT dans `%MW1000-%MW1001`, mot bas puis mot haut.
2. Le reste du bloc preparation doit etre `0`.
3. Le gateway pose `%MW1056=1`.
4. Le simulateur refuse la suppression si date, C1, C2 ou C3 ne sont pas a `0`.
5. Si l'ID existe, il est retire, la file est retriee, le CRC est recalcule.
6. Le simulateur ecrit `%MW1057`, puis remet `%MW1056=0`.

### 7.3 RAZ planificateur

1. Le gateway pose `%MW1068=1`.
2. Le simulateur vide les 10 slots `%MW8120-%MW8579`.
3. Le simulateur recalcule le CRC sur 460 mots a `0`.
4. Le simulateur ecrit `%MW1069=0`, `%MW8100=0`, `%MW8102=0`, puis remet `%MW1068=0`.

### 7.4 Lecture planificateur

1. Le gateway lit `%MW8100`, `%MW8101`, `%MW8102`.
2. Il lit les 10 slots a partir de `%MW8120`, stride `46`.
3. Il decode ID, date, C1, C2, C3, statut slot et CRC par slot.
4. Il recalcule aussi le CRC global sur 460 mots pour verifier `%MW8101`.
5. La page Orders affiche les ordres, le slot, le registre de base et le CRC.

## 8. Extension digital twin `%MW9000+`

Ces registres sont volontairement hors table Rev02 pour eviter le drift.

| Registre | Fonction | Format |
|---|---|---|
| `%MW9000` | Pression vapeur simulee | `INT x10`, ex. `53 = 5.3 bar`. |
| `%MW9001` | Demande usine simulee | `INT kW`. |
| `%MW9010-%MW9012` | IBC1 etat/load/target | `state`, `load_pct`, `target_pct`. |
| `%MW9020-%MW9022` | IBC2 etat/load/target | `state`, `load_pct`, `target_pct`. |
| `%MW9030-%MW9032` | IBC3 etat/load/target | `state`, `load_pct`, `target_pct`. |
| `%MW9070-%MW9074` | Runtime actif | strategie, order_id haut, order_id bas, pression cible x10, stages. |

## 9. Checklist de verification

### 9.1 Verification statique locale

- Compiler les scripts Python:

```bash
python3 -m py_compile \
  auth_prototype/provisioning_ansible/roles/edge-agent/files/src/agent/gateway_modbus_sbc.py \
  auth_prototype/provisioning_ansible/roles/edge-agent/files/src/agent/telemetry_publisher.py \
  auth_prototype/modbus_simulator/src/main_sim.py \
  auth_prototype/modbus_simulator/src/scheduler.py \
  auth_prototype/modbus_simulator/src/monitor.py
```

- Builder le frontend sur la VM control panel:

```bash
cd /opt/control-panel/control_plane/auth_prototype/frontend
npm run build
sudo systemctl restart control-panel-auth
```

### 9.2 Verification simulateur

- Deployer `modbus_simulator/src/` vers la VM simulateur.
- Redemarrer `modbus-serveur.service`.
- Lancer `python3 monitor.py`.
- Verifier que le monitor affiche:
  - horloge `%MW250-%MW255`;
  - watchdog `%MW256` qui evolue;
  - statuts `%MW1045/%MW1057/%MW1069`;
  - planificateur `%MW8100-%MW8102`;
  - slot 0 `%MW8120`;
  - runtime `%MW9000+` / `%MW9070+`.

### 9.3 Verification IPC gateway

- Deployer `gateway_modbus_sbc.py` et `telemetry_publisher.py` sur l'IPC.
- Redemarrer:

```bash
sudo systemctl restart gateway_modbus.service
sudo systemctl restart telemetry_publisher.service
```

- Verifier les logs:

```bash
sudo journalctl -u gateway_modbus.service -n 50 --no-pager -l
sudo journalctl -u telemetry_publisher.service -n 50 --no-pager -l
```

### 9.4 Test ordre valide

Payload attendu:

```json
{
  "action": "upsert",
  "asset_name": "cascadya-ipc-10-109",
  "id": 7001,
  "execute_at": "YYYY-MM-DD HH:MM:SS",
  "c1": [5, 40, 5.3, 0, 0, 0],
  "c2": [5, 2, 5.3, 0, 0, 0],
  "c3": [1, 0, 0, 0, 0, 0]
}
```

Attendus:

- reponse gateway `status=ok`, `status_code=0`;
- `%MW1045=0`;
- `read_plan` retourne `count=1`;
- premier ordre en `register_base=8120`;
- `slot_stride=46`;
- `planner_crc16_matches=true`;
- monitor affiche l'ordre en tete de file.

### 9.5 Test execution ordre

- Programmer un ordre a `+60s`.
- Attendre l'heure d'execution.
- Verifier:
  - l'ordre disparait du slot 0;
  - `%MW9070-%MW9074` expose la strategie active, l'ID et la pression cible;
  - `telemetry_publisher` publie `active_order_id`, `active_strategy`, `pressure_bar`, `plc_watchdog`.

### 9.6 Tests erreurs a presenter

- ID `0`: attendu `%MW1045=20`.
- C1-2 `51`: attendu `%MW1045=120`.
- C1-3 `19`: attendu `%MW1045=130`.
- Profil `6` avec C1-2 non nul: attendu `%MW1045=120`.
- Profil `3` avec C2-3 non nul: attendu `%MW1045=230`.
- Suppression ID inexistant: attendu `%MW1057=21`.
- Suppression avec C1 non nul: attendu `%MW1057=100`.
- Deux triggers simultanes: attendu statut `8`.

## 10. Definition of Done

- Les anciens registres de commande `%MW0-%MW16`, `%MW50-%MW63`, `%MW100+` ne sont plus utilises par gateway/scheduler.
- Les ordres sont ecrits en `%MW1000+` et lus en `%MW8120+`.
- Les ID `UDINT` sont encodes avec mots Modbus `mot bas puis mot haut`.
- Les REAL C1/C2 sont encodes IEEE-754 avec mots Modbus `mot bas puis mot haut`.
- Le CRC officiel `%MW8101` est publie par le simulateur et verifie par le gateway.
- La page Orders contient une section repliable de cartographie registre.
- La telemetrie runtime ne collisionne plus avec la table Rev02 et vit en `%MW9000+`.

## 11. Validation terrain du 2026-04-21

### 11.1 Validation simulateur Modbus

Commande executee sur la VM simulateur:

```bash
python3 - <<'PY'
from pymodbus.client.sync import ModbusTcpClient
import time

client = ModbusTcpClient("127.0.0.1", port=502)
assert client.connect(), "modbus connect failed"

print("%MW250-%MW256 =", client.read_holding_registers(250, 7).registers)
time.sleep(2)
print("%MW250-%MW256 after 2s =", client.read_holding_registers(250, 7).registers)
print("%MW8100-%MW8102 =", client.read_holding_registers(8100, 3).registers)
print("%MW8120-%MW8125 =", client.read_holding_registers(8120, 6).registers)
print("%MW9000-%MW9001 =", client.read_holding_registers(9000, 2).registers)
print("%MW9070-%MW9074 =", client.read_holding_registers(9070, 5).registers)

client.close()
PY
```

Resultat observe:

```text
%MW250-%MW256 = [2026, 4, 21, 8, 55, 25, 132]
%MW250-%MW256 after 2s = [2026, 4, 21, 8, 55, 27, 134]
%MW8100-%MW8102 = [0, 29069, 0]
%MW8120-%MW8125 = [0, 0, 0, 0, 0, 0]
%MW9000-%MW9001 = [0, 2236]
%MW9070-%MW9074 = [1, 0, 0, 53, 3]
```

Interpretation:

- le serveur Modbus repond sur `127.0.0.1:502`;
- l'horloge `%MW250-%MW255` evolue;
- le watchdog `%MW256` evolue aussi (`132 -> 134`);
- le planificateur est stable (`%MW8102=0`);
- le runtime digital twin est disponible en `%MW9000+` et `%MW9070+`.

### 11.2 Validation ajout + read_plan Rev02

Commande executee sur l'IPC avec le gateway:

```json
{
  "id": 9101,
  "execute_at": "2026-04-21 09:06:45",
  "c1": [5, 40, 5.3, 0, 0, 0],
  "c2": [5, 2, 5.3, 0, 0, 0],
  "c3": [1, 0, 0, 0, 0, 0]
}
```

Resultat observe:

```json
{
  "status": "ok",
  "action": "upsert",
  "order_id": 9101,
  "execute_at": "2026-04-21 09:06:45",
  "status_code": 0,
  "status_text": "ok",
  "register_base": 1000,
  "trigger_register": 1044,
  "status_register": 1045
}
```

Snapshot `read_plan` observe:

```json
{
  "planner_state": 0,
  "planner_crc16": 37460,
  "planner_crc16_calculated": 37460,
  "planner_crc16_matches": true,
  "planner_crc_state": 0,
  "count": 1,
  "planner_word_count": 460,
  "slot_stride": 46,
  "slot_words": 46,
  "orders": [
    {
      "id": 9101,
      "register_base": 8120,
      "mode_profile_code": 5,
      "mode_profile_label": "5.5.*",
      "power_limit_kw": 40.0,
      "elec_pressure_bar": 5.3,
      "met_activation": 5,
      "met_type": 2,
      "met_pressure_bar": 5.3,
      "secours_enabled": true,
      "order_status": 0
    }
  ]
}
```

Lecture brute du slot 0:

```text
MW8120_8165 = [0, 9101, 21, 4, 2026, 9, 6, 45, 5, 0, 16928, 0, 16553, 39322, 0, 0, 0, 0, 5, 0, 16384, 0, 16553, 39322, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

Interpretation:

- `%MW1000-%MW1043` est bien le buffer de preparation;
- `%MW1044/%MW1045` valide l'ajout avec statut `0`;
- `%MW8120` est bien le slot 0;
- le stride est `46`;
- le CRC physique `%MW8101` est identique au CRC recalcule par le gateway;
- les valeurs `REAL` sont decodees correctement: `40.0`, `5.3`, `2.0`, `5.3`.

### 11.3 Validation execution planificateur

Ordre rapide envoye depuis l'IPC:

```json
{
  "id": 9201,
  "execute_at": "2026-04-21 09:00:35",
  "c1": [5, 40, 5.3, 0, 0, 0],
  "c2": [5, 2, 5.3, 0, 0, 0],
  "c3": [1, 0, 0, 0, 0, 0]
}
```

Resultat observe apres execution:

```text
QUEUE_HEAD = [0, 0, 0, 0, 0, 0, 0, 0]
RUNTIME = [3, 0, 9201, 53, 1]
```

Interpretation:

- le slot `%MW8120` est vide apres execution;
- `%MW9070=3` signifie strategie active `C3`;
- `%MW9071-%MW9072 = [0, 9201]` signifie `order_id=9201`;
- `%MW9073=53` signifie pression cible `5.3 bar`;
- `%MW9074=1` signifie un stage actif au moment de la lecture.

Cette validation prouve le chemin complet:

```text
Control Panel / script IPC -> NATS/gateway -> Modbus %MW1000+ -> trigger %MW1044 -> scheduler -> plan %MW8120+ -> CRC %MW8101 -> execution -> runtime %MW9070+
```

### 11.4 Correctif de stabilite service Modbus

Un redemarrage rapide du service simulateur a produit un historique `OSError: [Errno 98] Address already in use`. Le repo local inclut maintenant:

```python
ModbusTcpServer.allow_reuse_address = True
```

dans `modbus_simulator/src/main_sim.py` avant `StartTcpServer(...)`.

Objectif: eviter qu'un restart systemd rapide echoue parce que le socket TCP `:502` n'est pas encore relache par le noyau.

Etat observe le 21/04/2026: apres plusieurs redemarrages rapides, le port `502` est reste temporairement visible en `FIN-WAIT-2` / `TIME-WAIT` sans process actif. Le service a ete relance proprement apres attente de 90 secondes, puis a expose:

```text
LISTEN 0.0.0.0:502 users:(("python3",pid=32405,fd=3))
```

Regle d'exploitation: si `OSError: [Errno 98] Address already in use` reapparait, stopper `modbus-serveur.service`, verifier `sudo ss -tanp | grep ':502'`, attendre l'expiration des etats TCP, puis relancer. Ce point n'affecte pas le contrat Modbus; c'est une contrainte de redemarrage socket.

### 11.5 Correctif timezone UI / IPC / simulateur

Symptome observe dans Orders:

```text
ACK upsert: error
%MW1045=7
Queue head vide
```

Interpretation: le SBC/simulateur a bien recu la commande, mais il a refuse l'ajout parce que l'heure d'execution etait deja passee par rapport a l'horloge automate.

Cause: l'UI envoie un `datetime-local` converti en ISO UTC (`...Z`). Le gateway IPC tournant sur une timezone differente pouvait convertir cette date vers la timezone locale de l'IPC avant d'ecrire les registres Rev02. Exemple: une heure UTC valide pour le simulateur devenait plusieurs heures plus tot cote IPC, donc le simulateur renvoyait le statut officiel `%MW1045=7`.

Correctif: dans `gateway_modbus_sbc.py`, les dates timezone-aware sont converties explicitement vers `timezone.utc` puis rendues naive avant l'ecriture Modbus. La reference temporelle du simulateur reste donc l'horloge `%MW250-%MW255`.

Regle a retenir: pour Rev02, l'heure ecrite en `%MW1002-%MW1007` doit etre dans le meme referentiel que l'horloge automate lue en `%MW250-%MW255`.

### 11.6 Correctif physique simulateur sans changer le contrat Rev02

Symptome observe dans le monitor web:

```text
Steam Header Pressure : 0.0 bar [%MW9000]
Factory Demand        : 441 kW  [%MW9001]
Active Runtime        : strategy=C2 target=5.3 bar stages=1
IBC2                  : RUNNING Load=4% Target=4%
```

Interpretation: la boucle physique tourne deja. Les preuves sont le watchdog `%MW256` qui evolue, la demande `%MW9001` qui change, le runtime `%MW9070-%MW9074` qui est publie, et la charge IBC2 qui rampe. Le probleme n'est donc pas un service systemd arrete.

Contrainte: les consignes profils, les bornes Rev02 et les registres ne doivent pas etre modifies pour corriger une demo. C1-2 reste donc dans `[0;50] kW` et `%MW1010-%MW1011` reste le champ officiel `REAL` de limitation puissance.

Correctif: seul le modele physique du simulateur est adapte. Dans `modbus_simulator/src/physics.py`, la demande usine simulee est recentree sur une plage demonstrable et la puissance chaudiere calculee par `boiler_model.py` est convertie en effet vapeur equivalent via `boiler_output_gain`. Ainsi, une consigne C1-2 conforme comme `40 kW` peut produire une evolution visible de `%MW9000`, sans changer ni le profil, ni les registres, ni la validation IPC/SBC.

## 12. Visualisation web dans Orders

La page Orders integre maintenant une reference permanente et un bouton de visualisation.

### 12.1 Guide registre integre

Dans `frontend/src/modules/orders/views/OrdersView.vue`, la section repliable `Table d'echange Rev02` contient:

- guide rapide en 4 etapes: preparer, declencher, acquitter, lire le plan;
- table preparation `%MW1000-%MW1043`;
- table planificateur `%MW8100-%MW8102`;
- table des 10 slots `%MW8120` a `%MW8534`;
- table des statuts `%MW1045`, `%MW1057`, `%MW1069`;
- preuves terrain `9101` et `9201`;
- extension digital twin `%MW9000+`;
- table de comparaison `Simulation safe -> Reel LCI`, par exemple `%MW9588 -> %MW388`, `%MW9708 -> %MW508`, `%MW9774 -> %MW574`.

### 12.2 Onglet monitor simulateur

Un bouton `Visualiser simulateur` est disponible dans le panneau d'execution Orders. Il ouvre la route frontend:

```text
/orders/monitor?asset=cascadya-ipc-10-109
```

Cette route est implementee dans:

```text
frontend/src/modules/orders/views/OrdersMonitorView.vue
```

La vue ne se connecte pas directement au simulateur Modbus. Elle utilise le chemin securise deja en place:

```text
Navigateur -> Control Panel /api/orders/dispatch -> Broker probe -> NATS -> gateway_modbus -> Modbus 192.168.50.2:502
```

Le gateway IPC expose l'action:

```json
{
  "action": "monitor_snapshot",
  "asset_name": "cascadya-ipc-10-109"
}
```

et retourne un snapshot JSON contenant:

- horloge `%MW250-%MW255`;
- watchdog `%MW256`;
- statuts `%MW1045/%MW1057/%MW1069`;
- etat/CRC planificateur `%MW8100-%MW8102`;
- queue head `%MW8120`;
- liste dynamique des ordres pending `orders[]`, decodee depuis les 10 slots `%MW8120 + slot*46`;
- pression procede simulee `%MW9588 -> %MW388` et demande sandbox `%MW9001`;
- runtime actif `%MW9070-%MW9074`;
- etat des IBC `%MW9010+`, `%MW9020+`, `%MW9030+`.

Objectif presentation: garder l'onglet Orders pour envoyer l'ordre et ouvrir un second onglet monitor pour observer l'evolution en temps reel pendant l'execution.

En mode `real`, les signaux terrain affiches par le monitor remplacent la zone sandbox `%MW9000+` pour la partie physique:

| Bloc JSON | Registres | Variables Rev02 | Utilite demo |
|---|---:|---|---|
| `plc_health` | `%MW257-%MW260` | `GE00_DEFAUT`, `GE00_NBDEFAUT`, `GE00_ALARME`, `GE00_NBALARME` | Montrer si l'automate declare un defaut ou une alarme. |
| `pressure_sensor` | `%MW388`, `%MW390.0`, `%MW392` | `PT01_MESURE`, `PT01_ERREUR`, `PT01_MESUREPRCT` | Montrer la pression vapeur et l'etat du capteur. |
| `pressure_regulation` | `%MW508-%MW516` | `ETAT_THERMO`, `MINI_TECHNIQUE`, `POS_LIMITEUR`, `RP08_AUTO`, `RP08_MANU`, `RP08_DESACTIVE`, `RP08_CHARGE`, `RP08_CONSIGNE`, `RP08_BOOST` | Montrer le mode RP08, la charge commandee, la consigne et les bits de regulation. |
| `heater_feedback` | `%MW574`, `%MW576.0` | `ZT16_MESURE`, `ZT16_ERREUR` | Montrer la recopie de charge thermoplongeur et son erreur capteur. |

Ces lectures n'ajoutent aucun ordre et n'ecrivent rien dans l'automate.

### 12.3 Lecture dynamique de la file dans le monitor web

Le monitor web ne se limite plus au `queue_head`. Il affiche une table `File planificateur dynamique` construite depuis le champ `orders[]` retourne par `monitor_snapshot`.

Correspondance visuelle:

| Badge | Source | Signification |
|---|---|---|
| `NEXT` | premier element de `orders[]`, normalement slot `0` / `%MW8120` | prochain ordre pending qui sera applique par le scheduler. |
| `PENDING` | autres elements de `orders[]` | ordres en attente dans les slots suivants `%MW8166`, `%MW8212`, etc. |
| `ACTIVE` | comparaison avec `%MW9070-%MW9074.active_order_id` | ordre deja applique au runtime. Il peut ne plus etre dans la queue si le scheduler l'a consomme. |

Le JSON brut reste disponible pour debug, mais il est replie par defaut afin de privilegier la lecture operative pendant une demonstration.

### 12.4 Etat deploye IPC et fermeture du drift documentaire

Etat reel observe le 21/04/2026 sur l'IPC `cascadya-ipc-10-109`:

| Domaine | Etat |
|---|---|
| Script commandes | `/data/cascadya/agent/gateway_modbus_sbc.py` installe depuis le repo et compile avec `py_compile`. |
| Script telemetrie | `/data/cascadya/agent/telemetry_publisher.py` installe depuis le repo et compile avec `py_compile`. |
| Services | `gateway_modbus.service` et `telemetry_publisher.service` actifs apres restart. |
| Mode par defaut | `simulation`, cible `192.168.50.2:502`. |
| Mode reel | cible `192.168.1.52:502`, active via `set_operation_mode` avec confirmation `LCI LIVE`. |
| Drop-ins reel | `operation-mode-lci.conf` present pour gateway et telemetry publisher. |
| Controle mapping | script runtime retourne `REGISTER_MAPPING_REV02_OK`. |

Mapping reel valide dans les scripts:

| Variable Rev02 | Registre attendu | Registre code | Statut |
|---|---:|---:|---|
| `GE00_DEFAUT` | `%MW257` | `%MW257` | OK |
| `GE00_NBDEFAUT` | `%MW258` | `%MW258` | OK |
| `GE00_ALARME` | `%MW259` | `%MW259` | OK |
| `GE00_NBALARME` | `%MW260` | `%MW260` | OK |
| `PT01_MESURE` | `%MW388` | `%MW388` | OK |
| `PT01_ERREUR` | `%MW390.0` | `%MW390.0` | OK |
| `PT01_MESUREPRCT` | `%MW392` | `%MW392` | OK |
| `ETAT_THERMO/RP08` | `%MW508-%MW516` | `%MW508-%MW516` | OK |
| `RP08_CHARGE` | `%MW512` | `%MW512` | OK |
| `RP08_CONSIGNE` | `%MW514` | `%MW514` | OK |
| `RP08_BOOST` | `%MW516.0` | `%MW516.0` | OK |
| `ZT16_MESURE` | `%MW574` | `%MW574` | OK |
| `ZT16_ERREUR` | `%MW576.0` | `%MW576.0` | OK |

Point important: aucune consigne de profil, aucun format de slot et aucun registre de commande Rev02 n'a ete modifie pour ajouter le mode reel. Les changements portent uniquement sur:

- la cible Modbus active selon le mode;
- la zone de lecture telemetry physique;
- la severite watchdog en mode reel;
- l'affichage Control Panel pour rendre visibles les signaux LCI.

Reste a valider sur site LCI: connectivite TCP vers `192.168.1.52:502`, lecture effective des valeurs REAL terrain et evolution watchdog `%MW256` sur automate physique.

### 12.5 Alignement du simulateur avec les registres procede Rev02

Le simulateur Modbus ne se limite plus aux extensions sandbox `%MW9000+`. Le fichier suivant ajoute un miroir procede Rev02 decale:

```text
modbus_simulator/src/rev02_process.py
```

Objectif: permettre de tester le meme parcours de lecture que sur l'automate LCI, meme quand le mode Simulation reste actif, sans jamais ecrire dans les adresses terrain reelles. Les registres de commande restent inchanges; seuls des registres de lecture procede sont alimentes dans une zone haute.

Regle de mapping:

```text
registre_simule = registre_reel + 9200
```

Exemples principaux:

| Variable Rev02 | Reel LCI | Simule digital twin | Format |
|---|---:|---:|---|
| `GE00_DEFAUT/NBDEFAUT/ALARME/NBALARME` | `%MW257-%MW260` | `%MW9457-%MW9460` | BOOL + INT |
| `PT01_MESURE` | `%MW388` | `%MW9588` | REAL Float32, Bar |
| `PT01_ERREUR` | `%MW390.0` | `%MW9590.0` | BOOL |
| `PT01_MESUREPRCT` | `%MW392` | `%MW9592` | REAL Float32, % |
| `ETAT_THERMO/RP08` | `%MW508-%MW516` | `%MW9708-%MW9716` | bits + REAL |
| `RP08_CHARGE` | `%MW512` | `%MW9712` | REAL Float32, % |
| `RP08_CONSIGNE` | `%MW514` | `%MW9714` | REAL Float32, Bar |
| `RP08_BOOST` | `%MW516.0` | `%MW9716.0` | BOOL |
| `ZT16_MESURE` | `%MW574` | `%MW9774` | REAL Float32, % |
| `ZT16_ERREUR` | `%MW576.0` | `%MW9776.0` | BOOL |

Registres procede maintenant alimentes par le simulateur:

| Bloc | Registres simules | Source simulation |
|---|---:|---|
| Modes bache eau alimentaire | `%MW9200-%MW9213` | Etat auto, vanne/pompe, seuils niveau bas/haut. |
| Condensats | `%MW9250-%MW9259` | Mode auto, retour pompe, commandes, alarmes coherentes avec niveau. |
| Compteurs thermoplongeur/pompe/eau | `%MW9288-%MW9338`, `%MW9476-%MW9494` | Compteurs et temps derives du runtime simulateur. |
| Conditions de regulation et securites | `%MW9350-%MW9401` | Bits normaux/alarme/defaut derives de pression et niveau. |
| Niveau eau chaudiere | `%MW9498-%MW9525`, `%MW9690-%MW9696` | Niveau dynamique avec inertie, consommation vapeur et pompe alimentaire. |
| Defauts/alarmes globaux | `%MW9457-%MW9460` | Defaut/alarme agreges pour le PLC health. |
| Pression vapeur | `%MW9588/%MW9590/%MW9592`, plus miroirs `%MW9598`, `%MW9608`, `%MW9618`, `%MW9628` | Pression issue de `SteamHeader`, decodee en `REAL Float32`. |
| Regulation RP08 | `%MW9708-%MW9716`, seuils `%MW9718-%MW9724` | Charge, consigne, boost et modes derives du cascade controller. |
| Temperatures | `%MW9744-%MW9771` | Temperatures eau/fumees/vapeur derivees de pression et charge. |
| Recopie thermoplongeur | `%MW9774/%MW9776/%MW9778-%MW9781` | Recopie charge `%`, erreur et seuils. |

Le monitor terminal `modbus_simulator/src/monitor.py` affiche maintenant ces blocs afin de faciliter une demonstration:

- `Rev02 PT01/RP08`: pression simulee `%MW9588 -> %MW388`, charge `%MW9712 -> %MW512`, consigne `%MW9714 -> %MW514`, boost `%MW9716.0 -> %MW516.0`;
- `Rev02 Levels/Temps`: niveau `%MW9498 -> %MW298`, niveau secondaire `%MW9518 -> %MW318`, temperatures `%MW9744/%MW9754/%MW9764`;
- `Rev02 PLC Health`: defaut/alarme `%MW9457-%MW9460 -> %MW257-%MW260`, erreur sonde `%MW9590.0 -> %MW390.0`, recopie `%MW9774 -> %MW574`.

Important: les adresses `%MW1000-%MW1043`, `%MW1044/%MW1056/%MW1068`, `%MW8100-%MW8102` et `%MW8120+` restent exclusivement gerees par `scheduler.py`.

### 12.6 Validation finale du miroir procede et du snapshot IPC

Validation realisee le 21/04/2026 apres redeploiement simulateur, gateway IPC et Control Panel.

Sur `simulateur-modbus`, le service Modbus ecoute correctement:

```text
LISTEN 0.0.0.0:502 users:(("python3",pid=32405,fd=3))
```

Lecture locale du simulateur:

```text
Clock %MW250-%MW256 = [2026, 4, 21, 15, 21, 1, 288]
REAL low %MW388-%MW392 = [0, 0, 0, 0, 0]
SIM high %MW9588-%MW9592 = [16537, 23385, 0, 0, 16852]
PT01 simulated pressure = 4.792 bar
REAL low %MW508-%MW516 = [0, 0, 0, 0, 0, 0, 0, 0, 0]
SIM high %MW9708-%MW9716 = [256, 256, 0, 0, 0, 0, 16553, 39322, 1]
REAL low %MW574-%MW576 = [0, 0, 0]
SIM high %MW9774-%MW9776 = [0, 0, 0]
```

Interpretation:

- les registres terrain bas `%MW388`, `%MW508`, `%MW574` restent a `0` dans le simulateur;
- les valeurs dynamiques existent dans la zone haute `%MW9588+`, `%MW9708+`, `%MW9774+`;
- le format `REAL Float32` est bien decodeable en lecture Modbus;
- le watchdog `%MW256` evolue, donc le simulateur publie bien son horloge et son pouls automate.

Snapshot IPC `monitor_snapshot` valide apres correction de propagation `pressure_maps_to`:

```json
{
  "pressure_bar": 5.919,
  "pressure_label": "PT01_MESURE simulated mirror",
  "pressure_register": 9588,
  "pressure_register_label": "%MW9588",
  "pressure_maps_to": "%MW388",
  "pressure_raw": 59,
  "demand_kw": 556,
  "demand_register": 9001,
  "demand_register_label": "%MW9001",
  "telemetry_profile": "digital_twin"
}
```

Conclusion de validation:

- la chaine `simulateur -> IPC gateway -> Control Panel monitor` lit bien la pression sur `%MW9588`;
- l'IHM peut afficher explicitement que `%MW9588` est le miroir simulation de `%MW388`;
- le profil de telemetrie actif est `digital_twin`;
- le contrat d'ecriture ordre Rev02 reste inchange et separe du miroir procede.

## 13. Evolution cible: LCI Rev02 comme premier Device Profile

Le contrat de ce PRD reste la source de verite pour le profil `lci_rev02`. Cependant, il ne doit pas devenir une limitation produit. Si Cascadya doit piloter plusieurs sites et plusieurs fournisseurs de chaudieres, LCI Rev02 doit etre traite comme le premier `Device Profile` d'une architecture HAL.

### 13.1 Principe

Le code metier conserve le vocabulaire applicatif:

- `upsert order`;
- `delete order`;
- `reset planner`;
- `read planner`;
- `read steam pressure`;
- `read watchdog`;
- `read heater feedback`.

Le profil materiel traduit ce vocabulaire vers les registres exacts du fournisseur.

Pour LCI Rev02:

| Variable canonique | Mapping LCI Rev02 |
|---|---|
| `ORDER_PREPARATION_BUFFER` | `%MW1000-%MW1043` |
| `ORDER_UPSERT_TRIGGER` | `%MW1044` |
| `ORDER_UPSERT_STATUS` | `%MW1045` |
| `ORDER_DELETE_TRIGGER` | `%MW1056` |
| `ORDER_DELETE_STATUS` | `%MW1057` |
| `ORDER_RESET_TRIGGER` | `%MW1068` |
| `ORDER_RESET_STATUS` | `%MW1069` |
| `PLANNER_HEADER` | `%MW8100-%MW8102` |
| `PLANNER_QUEUE` | `%MW8120 + slot*46`, 10 slots |
| `STEAM_PRESSURE` | reel `%MW388`, simulation `%MW9588` |
| `RP08_LOAD` | reel `%MW512`, simulation `%MW9712` |
| `HEATER_FEEDBACK` | reel `%MW574`, simulation `%MW9774` |

### 13.2 Strategie anti-rupture

La migration vers un HAL ne doit pas modifier les valeurs de ce PRD. Elle doit seulement deplacer leur definition:

```text
Avant: constante Python -> comportement
Apres: device_profiles/lci_rev02/simulation.json ou real.json -> loader HAL -> comportement identique
```

Premiere etape recommandee: creer deux profils JSON `lci_rev02/simulation.json` et `lci_rev02/real.json` qui reproduisent exactement ce document, puis faire tourner le gateway en mode comparaison:

```text
constantes actuelles == profil charge
```

Tant que cette egalite n'est pas prouvee, le code actuel reste la source d'execution. Le profil sert d'abord de documentation executable.

### 13.3 Regle de compatibilite

Un nouveau fournisseur ne doit pas forcer une regression du profil LCI. Les invariants suivants restent obligatoires:

- les tests `upsert/delete/reset/read_plan` LCI Rev02 doivent continuer a passer;
- le monitor LCI doit continuer a afficher `%MW9588 -> %MW388` en simulation;
- le mode Reel LCI doit continuer a cibler `192.168.1.52:502`;
- le profil par defaut reste `lci_rev02` tant qu'aucun autre profil n'est explicitement selectionne;
- aucun profil fournisseur ne peut ecrire dans un registre qui n'est pas marque `access: write`.
