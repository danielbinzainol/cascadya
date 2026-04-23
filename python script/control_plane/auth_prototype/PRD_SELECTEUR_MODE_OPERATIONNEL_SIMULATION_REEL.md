# PRD - Selecteur de Mode Operationnel Simulation vs Reel

## 1. Contexte et vision

Le Control Panel Cascadya doit piloter deux environnements avec le meme code metier:

- un jumeau numerique Modbus pour les tests, demonstrations et validations;
- une usine physique LCI pour la production.

La strategie retenue est l'Iso-Production: les commandes metier, les profils, les statuts et les registres Rev02 de commande restent strictement identiques entre simulation et reel. Le basculement ne doit pas modifier le contrat `%MW1000+`, `%MW8100+` ou les regles C1/C2/C3.

Ce qui change est uniquement le contexte d'execution: destination reseau, zones de telemetrie runtime et niveau de securite watchdog.

## 2. Objectifs

- Rendre explicite dans l'UI si l'operateur pilote le jumeau numerique ou l'usine physique.
- Eviter toute confusion lors des demonstrations et du deploiement LCI.
- Garantir que les registres de commande Rev02 restent identiques dans les deux modes.
- Bloquer l'envoi d'ordres reels si le watchdog automate est fige.
- Centraliser la configuration mode dans le gateway/backend, pas dans le navigateur.

## 3. Modes operationnels

### 3.1 Mode Simulation

Badge UI:

```text
ENVIRONMENT: DIGITAL TWIN (SAFE)
```

Caracteristiques:

- cible Modbus: simulateur Python, par exemple `192.168.50.2:502` ou `127.0.0.1:502` selon deploiement;
- telemetrie runtime: zone sandbox `%MW9000+`;
- pression: `%MW9000`, format `INT x10`;
- demande usine: `%MW9001`, format `INT kW`;
- IBC: `%MW9010+`, `%MW9020+`, `%MW9030+`;
- runtime actif: `%MW9070-%MW9074`;
- miroir procede Rev02: zone haute decalee selon `registre_simule = registre_reel + 9200`;
- watchdog `%MW256`: emule logiciellement;
- politique watchdog: tolerant, `WATCHDOG_STRICT=false`.

### 3.2 Mode Reel

Badge UI:

```text
LIVE: PHYSICAL PLANT (LCI)
```

Caracteristiques:

- cible Modbus: automate industriel physique LCI fourni pour les tests endpoint, `192.168.1.52:502`;
- telemetrie runtime: vraies adresses terrain LCI;
- pression vapeur chaudiere: `%MW388`, variable Rev02 `PT01_MESURE`, format `REAL Float32` sur 2 mots, unite `Bar`;
- equivalent de la demande simulation `%MW9001`: pas d'adresse "factory demand kW" directe dans la Rev02; le monitor reel expose `%MW512`, variable `RP08_CHARGE`, format `REAL Float32` sur 2 mots, unite `%`, comme charge thermoplongeur;
- watchdog `%MW256`: doit etre incremente par l'automate physique;
- politique watchdog: stricte, `WATCHDOG_STRICT=true`;
- en cas de watchdog fige: blocage d'envoi des ordres et alerte critique.

## 4. Contrat fixe Iso-Production

Ces registres ne changent jamais entre Simulation et Reel:

| Zone | Registres | Role |
|---|---|---|
| Buffer preparation | `%MW1000-%MW1043` | ID, date/heure, consignes C1/C2/C3 et reserves. |
| Trigger upsert | `%MW1044` | Ajout/modification ordre. |
| Status upsert | `%MW1045` | Statut officiel operation ajout/modification. |
| Trigger delete | `%MW1056` | Suppression ordre par ID. |
| Status delete | `%MW1057` | Statut officiel suppression. |
| Trigger reset | `%MW1068` | RAZ planificateur. |
| Status reset | `%MW1069` | Statut officiel RAZ. |
| Header planificateur | `%MW8100-%MW8102` | Etat, CRC, etat calcul CRC. |
| Slots planificateur | `%MW8120 + slot*46` | 10 slots maximum, 46 mots par slot. |

Les profils restent egalement inchanges:

- `2.5.*`
- `3.0.0`
- `4.0.0`
- `5.5.*`
- `6.0.0`

La borne C1-2 reste celle de la Rev02 projet: `[0;50] kW`.

## 5. Configuration backend attendue

Le mode actif doit etre resolu cote backend/gateway via configuration, pas seulement via l'UI.

Variables proposees:

```env
OPERATION_MODE=simulation
OPERATION_MODE_STATE_FILE=/data/cascadya/agent/operation_mode.json
OPERATION_MODE_REAL_CONFIRMATION=LCI LIVE
MODBUS_SIM_HOST=192.168.50.2
MODBUS_SIM_PORT=502
MODBUS_SIM_PROCESS_OFFSET=9200
MODBUS_REAL_HOST=192.168.1.52
MODBUS_REAL_PORT=502
MODBUS_REAL_PRESSURE_BASE=388
MODBUS_REAL_PRESSURE_ERROR=390
MODBUS_REAL_PRESSURE_PERCENT=392
MODBUS_REAL_PRESSURE_REGULATION_BASE=508
MODBUS_REAL_DEMAND_BASE=512
MODBUS_REAL_PRESSURE_SETPOINT=514
MODBUS_REAL_PRESSURE_BOOST=516
MODBUS_REAL_HEATER_FEEDBACK_BASE=574
MODBUS_REAL_HEATER_FEEDBACK_ERROR=576
WATCHDOG_STRICT_SIMULATION=false
WATCHDOG_STRICT_REAL=true
WATCHDOG_FREEZE_THRESHOLD_SEC=30
```

Le gateway expose au Control Panel un endpoint ou une reponse de statut permettant d'afficher le mode actif:

```json
{
  "action": "operation_mode_status",
  "mode": "simulation",
  "target_host": "192.168.50.2",
  "target_port": 502,
  "telemetry_profile": "digital_twin",
  "watchdog_strict": false,
  "fixed_rev02_contract": {
    "preparation": [1000, 1043],
    "triggers": [1044, 1056, 1068],
    "statuses": [1045, 1057, 1069],
    "queue_base": 8120,
    "queue_max_orders": 10
  }
}
```

## 6. UX frontend Orders

### 6.1 Selecteur visible

La page Orders affiche un toggle en haut de page:

```text
[ Simulation / Digital Twin ] [ Reel / Physical Plant ]
```

En mode Simulation:

- theme froid/neutre;
- badge visible `ENVIRONMENT: DIGITAL TWIN (SAFE)`;
- texte d'aide: `Les ordres sont envoyes au simulateur Modbus. Aucun automate physique n'est pilote.`

En mode Reel:

- theme chaud/alerte;
- bordures marquees;
- badge visible `LIVE: PHYSICAL PLANT (LCI)`;
- texte d'aide: `Les ordres sont envoyes a l'automate physique LCI.`

### 6.2 Double confirmation pour le reel

Le passage Simulation -> Reel exige une double confirmation:

1. confirmation modale:

```text
Attention: vous allez piloter l'automate physique LCI.
Confirmer le passage en mode Reel ?
```

2. saisie explicite:

```text
Taper LCI LIVE pour confirmer.
```

Le retour Reel -> Simulation ne demande pas de double confirmation.

### 6.3 Verrouillage si watchdog critique

En mode Reel, si `%MW256` ne change pas pendant la fenetre configuree:

- bouton `Upsert order` desactive;
- bouton `Delete` desactive;
- bouton `Reset queue` desactive sauf role admin ou mode procedure speciale;
- badge `WATCHDOG CRITICAL`;
- message: `Automate LCI non vivant: envoi d'ordres bloque.`

## 7. Telemetrie selon mode

### 7.1 Simulation

Le monitor lit:

| Signal | Registre | Format |
|---|---:|---|
| Pression | `%MW9000` | `INT x10` |
| Demande usine | `%MW9001` | `INT kW` |
| IBC1 | `%MW9010-%MW9012` | state/load/target |
| IBC2 | `%MW9020-%MW9022` | state/load/target |
| IBC3 | `%MW9030-%MW9032` | state/load/target |
| Runtime actif | `%MW9070-%MW9074` | strategy, order_id UDINT mot bas puis mot haut, target x10, stages |

Le monitor lit aussi un miroir procede Rev02 decale. Ce miroir sert a expliquer les signaux reels sans risquer de toucher les adresses terrain:

| Signal Rev02 | Reel LCI | Simulation safe | Format |
|---|---:|---:|---|
| Sante automate | `%MW257-%MW260` | `%MW9457-%MW9460` | BOOL + compteurs |
| Pression vapeur `PT01_MESURE` | `%MW388` | `%MW9588` | REAL Float32 |
| Erreur pression / pourcentage | `%MW390/%MW392` | `%MW9590/%MW9592` | BOOL + REAL |
| Regulation RP08 | `%MW508-%MW516` | `%MW9708-%MW9716` | bits + REAL |
| Charge thermoplongeur | `%MW512` | `%MW9712` | REAL Float32 % |
| Consigne pression | `%MW514` | `%MW9714` | REAL Float32 Bar |
| Recopie charge `ZT16_MESURE` | `%MW574` | `%MW9774` | REAL Float32 % |
| Erreur recopie | `%MW576.0` | `%MW9776.0` | BOOL |

### 7.2 Reel

Le monitor lit les adresses terrain LCI:

| Signal | Registre cible | Format attendu |
|---|---:|---|
| Pression vapeur chaudiere | `%MW388` / `PT01_MESURE` | `REAL Float32`, 2 mots, unite `Bar` |
| Erreur sonde pression | `%MW390.0` / `PT01_ERREUR` | `BOOL`, 0=non, 1=oui |
| Sante automate | `%MW257-%MW260` / `GE00_DEFAUT`, `GE00_NBDEFAUT`, `GE00_ALARME`, `GE00_NBALARME` | defaut/alarme + compteurs |
| Charge thermoplongeur | `%MW512` / `RP08_CHARGE` | `REAL Float32`, 2 mots, unite `%` |
| Consigne pression regulation | `%MW514` / `RP08_CONSIGNE` | `REAL Float32`, 2 mots, unite `Bar` |
| Etat/mode regulation pression | `%MW508-%MW510` / `ETAT_THERMO`, `MINI_TECHNIQUE`, `POS_LIMITEUR`, `RP08_AUTO`, `RP08_MANU`, `RP08_DESACTIVE` | bits d'etat et mode RP08 |
| Boost thermoplongeur | `%MW516.0` / `RP08_BOOST` | `BOOL` |
| Recopie charge thermoplongeur | `%MW574` / `ZT16_MESURE` | `REAL Float32`, 2 mots, unite `%` |
| Erreur recopie charge | `%MW576.0` / `ZT16_ERREUR` | `BOOL`, 0=non, 1=oui |
| Watchdog | `%MW256` | `INT`, increment automate |

Note importante: `%MW9001` en simulation represente une demande usine artificielle en `kW`. La Rev02 LCI ne fournit pas d'equivalent direct en `kW`; pour le mode reel, l'IHM affiche donc `%MW512 RP08_CHARGE` en `%` avec un libelle specifique, tout en conservant la cle JSON historique `demand_kw` pour compatibilite.

Pour la demo LCI, le monitor Control Panel expose maintenant:

- `plc_health`: defaut/alarme automate via `%MW257-%MW260`;
- `pressure_sensor`: mesure `%MW388`, erreur `%MW390.0`, pourcentage optionnel `%MW392`;
- `pressure_regulation`: etat thermoplongeur `%MW508.0`, modes `%MW509-%MW510`, charge `%MW512`, consigne `%MW514`, boost `%MW516.0`;
- `heater_feedback`: recopie charge `%MW574` et erreur `%MW576.0`.

### 7.3 Etat reel installe et verifie le 21/04/2026

Etat observe sur l'IPC `cascadya-ipc-10-109`:

| Element | Etat reel |
|---|---|
| Gateway commandes | `/data/cascadya/agent/gateway_modbus_sbc.py` installe et compile avec `py_compile`. |
| Publisher telemetrie | `/data/cascadya/agent/telemetry_publisher.py` installe et compile avec `py_compile`. |
| Services systemd | `gateway_modbus.service` et `telemetry_publisher.service` actifs apres restart. |
| Cible Reel LCI | `MODBUS_REAL_HOST=192.168.1.52`, `MODBUS_REAL_PORT=502`. |
| Drop-in gateway | `/etc/systemd/system/gateway_modbus.service.d/operation-mode-lci.conf`. |
| Drop-in telemetrie | `/etc/systemd/system/telemetry_publisher.service.d/operation-mode-lci.conf`. |
| Mapping Rev02 reel | Controle runtime OK: `REGISTER_MAPPING_REV02_OK`. |

Variables systemd reel confirmees:

| Variable | Valeur | Registre Rev02 |
|---|---:|---:|
| `MODBUS_SIM_PROCESS_OFFSET` | `9200` | Simulation safe = Reel + 9200 |
| `MODBUS_REAL_PRESSURE_BASE` | `388` | `%MW388` |
| `MODBUS_REAL_PRESSURE_ERROR` | `390` | `%MW390.0` |
| `MODBUS_REAL_PRESSURE_PERCENT` | `392` | `%MW392` |
| `MODBUS_REAL_PRESSURE_REGULATION_BASE` | `508` | `%MW508-%MW516` |
| `MODBUS_REAL_DEMAND_BASE` | `512` | `%MW512` |
| `MODBUS_REAL_PRESSURE_SETPOINT` | `514` | `%MW514` |
| `MODBUS_REAL_PRESSURE_BOOST` | `516` | `%MW516.0` |
| `MODBUS_REAL_HEATER_FEEDBACK_BASE` | `574` | `%MW574` |
| `MODBUS_REAL_HEATER_FEEDBACK_ERROR` | `576` | `%MW576.0` |

Comportement attendu du bouton UI:

- clic vers `Simulation`: bascule automatiquement gateway + telemetry vers le simulateur `192.168.50.2:502`;
- clic vers `Reel`: exige la confirmation `LCI LIVE`, puis bascule gateway + telemetry vers `192.168.1.52:502`;
- les zones d'ecriture et le planificateur restent strictement identiques dans les deux modes;
- seule la cible Modbus, la lecture telemetry et la severite watchdog changent.

Limite actuelle: l'acces reseau a l'automate physique `192.168.1.52:502` reste a prouver depuis l'IPC pour les tests endpoint. La conformite des registres cote scripts est, elle, deja alignee avec la table Rev02.

### 7.4 Validation simulation safe apres redeploiement

Validation realisee le 21/04/2026 apres:

- build frontend Control Panel reussi;
- redemarrage `control-panel-auth.service`;
- installation de `gateway_modbus_sbc.py` et `telemetry_publisher.py` sur l'IPC;
- redemarrage `gateway_modbus.service` et `telemetry_publisher.service`;
- redemarrage du simulateur Modbus sur `192.168.50.2:502`.

Etat `operation_mode_status` observe sur l'IPC:

```text
mode = simulation
target_host = 192.168.50.2
target_port = 502
telemetry_profile = digital_twin
watchdog_strict = false
rev02_process_mapping.offset = 9200
```

Validation locale simulateur:

| Bloc | Registres reels bas | Registres simulation safe | Resultat |
|---|---|---|---|
| Pression PT01 | `%MW388-%MW392 = [0,0,0,0,0]` | `%MW9588-%MW9592` non nul | OK, pas d'ecriture dans la zone terrain. |
| Regulation RP08 | `%MW508-%MW516 = [0,0,0,0,0,0,0,0,0]` | `%MW9708-%MW9716` non nul | OK, mapping decale actif. |
| Recopie ZT16 | `%MW574-%MW576 = [0,0,0]` | `%MW9774-%MW9776` lisible | OK, zone simulation separee. |

Validation snapshot IPC:

```json
{
  "pressure_register_label": "%MW9588",
  "pressure_maps_to": "%MW388",
  "telemetry_profile": "digital_twin"
}
```

Conclusion: la bascule en mode Simulation utilise bien le jumeau numerique, avec une zone procede decalee. L'operateur peut presenter les equivalents reels LCI sans que le simulateur n'ecrive dans les adresses terrain basses.

## 8. Machine d'etats

```text
SIMULATION_SAFE
  -> user demande Reel
  -> confirmation 1
  -> confirmation 2 "LCI LIVE"
  -> verification watchdog
  -> REAL_ARMED

REAL_ARMED
  -> watchdog ok
  -> commandes autorisees

REAL_ARMED
  -> watchdog fige
  -> REAL_BLOCKED

REAL_BLOCKED
  -> watchdog redevient ok + acquittement operateur
  -> REAL_ARMED

REAL_ARMED ou REAL_BLOCKED
  -> user demande Simulation
  -> SIMULATION_SAFE
```

## 9. Criteres d'acceptation

- Le mode actif est visible en permanence dans Orders.
- Le mode Reel ne peut pas etre active sans double confirmation.
- Les registres `%MW1000+`, `%MW1044+`, `%MW8100+`, `%MW8120+` restent identiques dans les deux modes.
- En Simulation, le monitor utilise `%MW9000+` pour les alias runtime historiques et `reel + 9200` pour le miroir procede Rev02.
- En Reel, le monitor utilise la zone terrain LCI et decode les valeurs REAL.
- En Reel, si `%MW256` est fige, les commandes sont bloquees.
- Les logs indiquent le mode actif pour chaque commande envoyee.
- Le read_plan affiche toujours les memes slots Rev02 quel que soit le mode.

## 10. Risques et garde-fous

- Risque: mauvais host Modbus en mode Reel.
  - Garde-fou: afficher `modbus_target` dans l'UI et journaliser chaque commande.

- Risque: confusion entre telemetry sandbox et telemetry terrain.
  - Garde-fou: badge telemetry profile, mapping explicite et decalage memoire `reel + 9200`.

- Risque: watchdog emule accepte en Reel.
  - Garde-fou: `WATCHDOG_STRICT_REAL=true`, non modifiable depuis le navigateur.

- Risque: utilisateur bascule en Reel par erreur.
  - Garde-fou: double confirmation et theme visuel d'alerte.

## 11. Plan d'implementation propose

1. Ajouter une configuration `OPERATION_MODE` au gateway IPC. Fait.
2. Factoriser le client Modbus selon mode: simulation target vs real target. Fait.
3. Factoriser la telemetrie selon profil: `%MW9000+` + miroir `reel + 9200` en simulation vs `%MW388/%MW512` reel. Fait.
4. Ajouter une reponse `operation_mode` dans `monitor_snapshot`. Fait.
5. Ajouter le toggle UI dans Orders. Fait.
6. Ajouter la double confirmation pour Reel. Fait.
7. Ajouter le blocage commande si `watchdog_strict=true` et `%MW256` fige. Fait cote gateway.
8. Ajouter tests: Simulation accepte sans double confirmation, Reel exige confirmation, Reel bloque si watchdog fige. A verifier sur VM.

## 12. Implementation actuelle dans le repo

Fichiers responsables:

| Fichier | Role |
|---|---|
| `provisioning_ansible/roles/edge-agent/files/src/agent/gateway_modbus_sbc.py` | Source de verite du mode, switch a chaud, blocage watchdog strict, `operation_mode_status`, `set_operation_mode`, `monitor_snapshot`. |
| `provisioning_ansible/roles/edge-agent/files/src/agent/telemetry_publisher.py` | Lit le meme fichier d'etat et reconnecte sa lecture telemetry sur la cible active. |
| `provisioning_ansible/roles/edge-agent/templates/gateway_modbus.service.j2` | Injecte les variables de mode dans systemd. |
| `provisioning_ansible/roles/edge-agent/templates/telemetry_publisher.service.j2` | Injecte les variables de mode dans telemetry publisher. |
| `provisioning_ansible/roles/edge-agent/defaults/main.yml` | Valeurs par defaut Ansible, dont `edge_agent_modbus_real_host: 192.168.1.52`. |
| `frontend/src/modules/orders/views/OrdersView.vue` | Carte mode operationnel, lecture mode et bascule Simulation/Reel. |
| `frontend/src/modules/orders/views/OrdersMonitorView.vue` | Affiche le badge mode actif dans le monitor web. |

Actions NATS ajoutees sur `cascadya.routing.command`:

| Action | Payload minimal | Effet |
|---|---|---|
| `operation_mode_status` | `{"action":"operation_mode_status","asset_name":"cascadya-ipc-10-109"}` | Retourne mode, cible Modbus, mapping telemetry, watchdog strict et contrat Rev02 fixe. |
| `set_operation_mode` simulation | `{"action":"set_operation_mode","asset_name":"...","mode":"simulation"}` | Reconnecte gateway + telemetry vers le simulateur. |
| `set_operation_mode` reel | `{"action":"set_operation_mode","asset_name":"...","mode":"real","confirmation":"LCI LIVE"}` | Reconnecte gateway + telemetry vers l'automate physique, active watchdog strict. |

Le fichier `operation_mode.json` sert de pont entre les deux services Python. Le gateway l'ecrit lors d'un changement de mode; `telemetry_publisher.py` le relit dans sa boucle et reconnecte son client Modbus si la cible change. Au demarrage, le gateway reprend toujours la valeur systemd/Ansible `OPERATION_MODE`, afin d'eviter qu'un ancien fichier runtime laisse la VM en mode Reel par accident apres reboot.

## 13. Evolution cible: Device Profile / HAL multi-fournisseurs

### 13.1 Vision

Le mode Simulation/Reel actuellement implemente repond au cas LCI Rev02. Pour transformer Cascadya en produit deployable chez plusieurs clients et sur plusieurs marques de chaudieres, il faut introduire une couche d'abstraction materielle:

```text
Control Panel / Cloud
  -> langage metier universel
  -> HAL Device Profile
  -> driver Modbus fournisseur
  -> routeur Simulation ou Reel
  -> automate ou digital twin
```

Dans cette cible, le Control Panel et les commandes NATS ne parlent plus directement en adresses Modbus. Ils parlent en variables canoniques:

- `STEAM_PRESSURE`
- `PLC_WATCHDOG`
- `PLANNER_STATE`
- `ORDER_PREPARATION_BUFFER`
- `RP08_LOAD`
- `HEATER_FEEDBACK`

Le HAL traduit ces variables vers les registres du profil actif.

### 13.2 Principe Device Profile

Un `device_profile` est un fichier de configuration versionne qui decrit:

- le fournisseur ou le site: `LCI`, `Bosch`, `Viessmann`, `Siemens`, etc.;
- la revision de table d'echange;
- la cible Modbus reelle;
- la cible Modbus simulateur;
- les registres de commande;
- les registres de telemetrie;
- les formats de donnees;
- les offsets ou adresses dediees de simulation;
- les regles de securite watchdog;
- les capacites du materiel.

Exemple conceptuel:

```json
{
  "profile_id": "lci_rev02",
  "vendor": "LCI",
  "version": "Rev02",
  "endianness": "big",
  "word_order": "low_word_first",
  "float_word_order": "low_word_first",
  "u32_word_order": "low_word_first",
  "transport": {
    "real": {"host": "192.168.1.52", "port": 502},
    "simulation": {"host": "192.168.50.2", "port": 502}
  },
  "simulation_strategy": {
    "process_offset": 9200,
    "rule": "sim_register = real_register + process_offset"
  },
  "registers": {
    "STEAM_PRESSURE": {
      "real_address": 388,
      "simulation_address": 9588,
      "format": "REAL32_BE_WORD_SWAP",
      "unit": "bar",
      "access": "read"
    },
    "ORDER_PREPARATION_BUFFER": {
      "base": 1000,
      "words": 44,
      "access": "write"
    },
    "PLANNER_QUEUE": {
      "base": 8120,
      "slot_count": 10,
      "slot_stride": 46,
      "access": "read"
    }
  }
}
```

### 13.3 Ce qui reste fixe pour eviter de tout casser

La migration vers les profils ne doit pas changer immediatement:

- les actions NATS existantes: `upsert`, `delete`, `reset`, `read_plan`, `monitor_snapshot`;
- les payloads metier du Control Panel;
- les validations UI des profils Rev02 tant que `lci_rev02` est actif;
- le comportement actuel du bouton Simulation/Reel;
- le fichier runtime `operation_mode.json`, qui peut etre etendu mais pas supprime d'un coup.

Le profil LCI Rev02 devient simplement le premier profil charge par defaut:

```text
DEVICE_PROFILE_ID=lci_rev02
DEVICE_PROFILE_SIMULATION_PATH=/data/cascadya/agent/device_profiles/lci_rev02/simulation.json
DEVICE_PROFILE_REAL_PATH=/data/cascadya/agent/device_profiles/lci_rev02/real.json
```

### 13.4 Ce qui devient configurable

Les constantes actuellement dans `gateway_modbus_sbc.py`, `telemetry_publisher.py` et `rev02_process.py` doivent progressivement sortir du code vers le profil:

| Famille | Aujourd'hui | Cible HAL |
|---|---|---|
| Cible Modbus simulation | variables systemd `MODBUS_HOST/MODBUS_PORT` | `profile.transport.simulation` |
| Cible Modbus reel | variables systemd `MODBUS_REAL_HOST/MODBUS_REAL_PORT` | `profile.transport.real` |
| Pression vapeur | constantes `%MW388`, `%MW9588` | `registers.STEAM_PRESSURE` |
| Watchdog | `%MW256` | `registers.PLC_WATCHDOG` |
| Planificateur | `%MW8100`, `%MW8120`, stride `46` | `registers.PLANNER_HEADER`, `registers.PLANNER_QUEUE` |
| Ordre preparation | `%MW1000-%MW1043` | `registers.ORDER_PREPARATION_BUFFER` |
| Triggers | `%MW1044`, `%MW1056`, `%MW1068` | `registers.ORDER_TRIGGERS` |
| Formats REAL | fonctions Python fixes | `format`, `endianness`, `scale` |
| Simulation safe | offset `9200` | `simulation_strategy` par profil |

### 13.5 Contraintes de securite OT

Le HAL ne doit jamais transformer une erreur de profil en ecriture dangereuse.

Garde-fous obligatoires:

- un profil doit etre valide au demarrage via schema strict;
- tout registre `write` doit etre explicitement marque comme ecriture autorisee;
- les registres de telemetrie `read` ne doivent pas pouvoir devenir `write` par defaut;
- en mode Simulation, le profil doit interdire l'ecriture dans les registres terrain bas sauf si le profil declare explicitement un simulateur qui imite exactement la table terrain;
- en mode Reel, le watchdog strict doit etre active par defaut;
- le changement de profil en mode Reel doit exiger confirmation operateur et journalisation.

### 13.6 Selection de profil dans l'UI

La page Orders doit evoluer vers deux selecteurs distincts:

```text
Device profile: [LCI Rev02]
Mode:           [Simulation / Reel]
```

Le selecteur `Device profile` indique le modele de table d'echange charge.
Le selecteur `Mode` indique la cible d'execution pour ce profil.

Exemples:

| Device profile | Mode | Cible |
|---|---|---|
| `LCI Rev02` | Simulation | `192.168.50.2:502`, process mirror `%MW9200+` |
| `LCI Rev02` | Reel | `192.168.1.52:502`, registres LCI natifs |
| `Bosch V1` | Simulation | simulateur Bosch avec mapping Bosch |
| `Bosch V1` | Reel | automate Bosch site client |

### 13.7 Plan de migration sans rupture

Phase 0 - Etat actuel fige:

- conserver LCI Rev02 en constantes Python;
- garder les validations actuelles;
- ne pas changer le comportement en production lab.

Phase 1 - Introduire des profils lecture seule:

- creer `device_profiles/lci_rev02/simulation.json`;
- creer `device_profiles/lci_rev02/real.json`;
- y copier les adresses deja validees;
- ajouter un loader Python qui lit le profil mais ne pilote encore rien;
- exposer le profil actif dans `operation_mode_status`.

Phase 2 - Double-run de validation:

- le code continue d'utiliser les constantes existantes;
- en parallele, il compare les constantes avec le profil charge;
- si divergence, le gateway logge une alerte et refuse le demarrage en mode Reel.

Phase 3 - Basculer la telemetrie vers le profil:

- remplacer progressivement les lectures `%MW388`, `%MW512`, `%MW574` par des lookup de profil;
- conserver les cles JSON existantes pour l'UI;
- verifier que `monitor_snapshot` retourne exactement les memes valeurs qu'avant.

Phase 4 - Basculer le planificateur vers le profil:

- extraire `%MW1000`, `%MW1044`, `%MW8100`, `%MW8120`, stride `46` et slot count `10`;
- garder `lci_rev02` comme profil par defaut;
- lancer les tests `upsert/delete/reset/read_plan` sans changement UI.

Phase 5 - Ajouter un deuxieme profil fournisseur:

- commencer par un profil simulation uniquement;
- pas d'ecriture automate reelle tant que le profil n'a pas passe les tests de non-regression;
- ajouter seulement ensuite le mode Reel pour ce fournisseur.

### 13.8 Definition of Done de l'evolution HAL

- `lci_rev02` fonctionne exactement comme aujourd'hui;
- un profil invalide empeche le demarrage en mode Reel;
- le Control Panel affiche le profil actif;
- le monitor affiche les adresses reels/simulation depuis le profil;
- un deuxieme profil peut etre charge sans modifier `gateway_modbus_sbc.py`;
- les tests existants Rev02 restent verts;
- les commandes dangereuses restent bloquees si watchdog Reel fige.
