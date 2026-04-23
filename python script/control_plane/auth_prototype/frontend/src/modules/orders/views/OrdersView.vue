<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { dispatchOrderCommand, fetchLiveOrders } from "@/api/orders";
import { ApiError } from "@/api/client";
import MetricCard from "@/components/ui/MetricCard.vue";
import PanelCard from "@/components/ui/PanelCard.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { useSessionStore } from "@/stores/session";
import type {
  ApiBrokerOrderPayload,
  ApiOrdersDispatchPayload,
  ApiOrdersFeedPayload,
  BadgeTone,
  DashboardMetric,
} from "@/types/controlPlane";

const session = useSessionStore();
const router = useRouter();
const COMMAND_SUBJECT = "cascadya.routing.command";
const PING_SUBJECT = "cascadya.routing.ping";
const EXECUTION_LOG_LIMIT = 80;
const FIFO_DISPLAY_LIMIT = 10;

const refreshOptions = [
  { label: "Manuel", value: 0 },
  { label: "1 s", value: 1000 },
  { label: "2 s", value: 2000 },
  { label: "5 s", value: 5000 },
  { label: "10 s", value: 10000 },
  { label: "30 s", value: 30000 },
];

const displayLimitOptions = [FIFO_DISPLAY_LIMIT];
const profileOptions = [
  { label: "2.5.*", value: 2 },
  { label: "3.0.0", value: 3 },
  { label: "4.0.0", value: 4 },
  { label: "5.5.*", value: 5 },
  { label: "6.0.0", value: 6 },
];
const metTypeOptions = [
  { label: "0", value: 0 },
  { label: "2", value: 2 },
];
const secoursOptions = [
  { label: "0", value: 0 },
  { label: "1", value: 1 },
];
const errorTestScenarios = [
  {
    key: "invalid_c1_profile",
    label: "C1-1 profil invalide",
    expected: "Gateway bloque si actif; sinon PLC %MW1045=110",
    description: "Force C1-1 a 9 au lieu de 2, 3, 4, 5 ou 6.",
  },
  {
    key: "invalid_c1_power",
    label: "C1-2 puissance > 50 kW",
    expected: "Gateway bloque si actif; sinon PLC %MW1045=120",
    description: "Force C1-2 a 51 kW, au-dessus de la limite Rev02.",
  },
  {
    key: "invalid_c1_pressure",
    label: "C1-3 pression > 18 bar",
    expected: "Gateway bloque si actif; sinon PLC %MW1045=130",
    description: "Force C1-3 a 18.5 bar, au-dessus de la limite Rev02.",
  },
  {
    key: "invalid_c2_activation",
    label: "C2-1 activation incoherente",
    expected: "Gateway bloque si actif; sinon PLC %MW1045=210",
    description: "Profil 5.5.* mais activation MET forcee a 0 au lieu de 5.",
  },
  {
    key: "invalid_c2_type",
    label: "C2-2 type MET invalide",
    expected: "Gateway bloque si actif; sinon PLC %MW1045=220",
    description: "Force C2-2 a 7 au lieu de 0 ou 2.",
  },
  {
    key: "invalid_c2_pressure",
    label: "C2-3 pression > 18 bar",
    expected: "Gateway bloque si actif; sinon PLC %MW1045=230",
    description: "Force C2-3 a 18.5 bar.",
  },
  {
    key: "invalid_c3_secours",
    label: "C3-1 secours invalide",
    expected: "Gateway bloque si actif; sinon PLC %MW1045=310",
    description: "Force C3-1 a 2 au lieu de 0 ou 1.",
  },
  {
    key: "invalid_c3_reserved",
    label: "C3 reserve non nul",
    expected: "Gateway bloque si actif; sinon PLC %MW1045=320",
    description: "Force C3-2 a 1 alors que les mots reserves doivent rester a 0.",
  },
  {
    key: "past_execute_at",
    label: "Execution dans le passe",
    expected: "%MW1045=7 ou gateway_error",
    description: "Force execute_at a maintenant - 60 s pour verifier le rejet temporel.",
  },
  {
    key: "missing_order_id",
    label: "Order ID manquant",
    expected: "gateway_error missing_order_id",
    description: "Supprime le champ id du payload.",
  },
  {
    key: "wrong_target",
    label: "Cible IPC incorrecte",
    expected: "gateway_error target_mismatch",
    description: "Force asset_name a une cible volontairement differente.",
  },
] as const;

interface OrderControlFormState {
  targetAsset: string;
  action: "upsert" | "delete" | "reset" | "read_plan" | "register_check";
  side: "buy" | "sell";
  orderId: string;
  executeAt: string;
  c1ProfileCode: number;
  c1PowerLimitKw: string;
  c1ElecPressureBar: string;
  c2Activation: number;
  c2MetType: number;
  c2MetPressureBar: string;
  c3Secours: number;
  c3Word2: string;
  c3Word3: string;
}

interface WatchdogFormState {
  value: string;
}

interface WatchdogProbeState {
  status: string;
  requestValue: number | null;
  returnedValue: number | null;
  roundTripMs: number | null;
  testedAt: string | null;
  message: string | null;
}

interface ExecutionLogEntry {
  id: number;
  loggedAt: string;
  message: string;
  tone: BadgeTone;
}

interface OperationModeStatus {
  mode: "simulation" | "real";
  label: string;
  target_host: string;
  target_port: number;
  modbus_connected: boolean;
  telemetry_profile: string;
  telemetry_registers: Record<string, unknown>;
  watchdog_strict: boolean;
  watchdog_freeze_threshold_sec: number;
  fixed_rev02_contract?: Record<string, unknown>;
}

interface PlannerProfileRule {
  c2Activation: number;
  c2MetTypeAllowed: number[];
  c2MetPressureZeroOnly: boolean;
  c3SecoursAllowed: number[];
}

interface RegisterReferenceRow {
  range: string;
  meaning: string;
  format: string;
  owner: string;
  status: string;
}

interface RegisterReferenceGroup {
  title: string;
  badge: string;
  tone: BadgeTone;
  description: string;
  rows: RegisterReferenceRow[];
}

interface RegisterGuideStep {
  title: string;
  register: string;
  description: string;
  expected: string;
  tone: BadgeTone;
}

interface PlannerReadOrder {
  id: number | null;
  executeAt: string;
  registerBase: number | null;
  slotIndex: number | null;
  profileCode: number | null;
  profileLabel: string;
  powerLimitKw: number | null;
  elecPressureBar: number | null;
  metType: number | null;
  metPressureBar: number | null;
  secoursEnabled: boolean | null;
  crc16: number | null;
  c1: number[];
  c2: number[];
  c3: number[];
  rawWords: number[];
  orderStatus: number | null;
}

interface LastSentPlannerVerification {
  orderId: number | null;
  executeAt: string;
  c1: number[];
  c2: number[];
  c3: number[];
  words: number[];
  crc16: number;
  sentAt: string;
}

interface PlannerVerificationRow {
  label: string;
  registers: string;
  sent: string;
  received: string;
  matched: boolean | null;
  tone: BadgeTone;
}

interface PlannerVerificationWordRow {
  register: string;
  label: string;
  sent: number | null;
  received: number | null;
  matched: boolean | null;
}

interface PlannerRegisterCheckRow {
  register: number;
  registerLabel: string;
  slotIndex: number;
  slotOffset: number;
  field: string;
  value: number;
}

interface PlannerRegisterCheckSlot {
  slotIndex: number;
  baseRegister: number;
  orderId: number;
  nonZeroCount: number;
  rows: PlannerRegisterCheckRow[];
}

type ErrorTestScenarioKey = (typeof errorTestScenarios)[number]["key"];

const PROFILE_RULES: Record<number, PlannerProfileRule> = {
  2: {
    c2Activation: 5,
    c2MetTypeAllowed: [0, 2],
    c2MetPressureZeroOnly: false,
    c3SecoursAllowed: [0, 1],
  },
  3: {
    c2Activation: 0,
    c2MetTypeAllowed: [0],
    c2MetPressureZeroOnly: true,
    c3SecoursAllowed: [0],
  },
  4: {
    c2Activation: 0,
    c2MetTypeAllowed: [0],
    c2MetPressureZeroOnly: true,
    c3SecoursAllowed: [0],
  },
  5: {
    c2Activation: 5,
    c2MetTypeAllowed: [0, 2],
    c2MetPressureZeroOnly: false,
    c3SecoursAllowed: [0, 1],
  },
  6: {
    c2Activation: 0,
    c2MetTypeAllowed: [0],
    c2MetPressureZeroOnly: true,
    c3SecoursAllowed: [0],
  },
};

const MAX_POWER_LIMIT_KW = 50;
const MAX_PRESSURE_BAR = 18;

const QUEUE_SLOT_WORD_LABELS = [
  "Order ID mot bas",
  "Order ID mot haut",
  "Execution jour",
  "Execution mois",
  "Execution annee",
  "Execution heure",
  "Execution minute",
  "Execution seconde",
  "C1-1 profil",
  "C1 reserve/padding",
  "C1-2 puissance REAL mot bas",
  "C1-2 puissance REAL mot haut",
  "C1-3 pression REAL mot bas",
  "C1-3 pression REAL mot haut",
  "C1-4 reserve",
  "C1-5 reserve",
  "C1-6 reserve",
  "C2 reserve/padding",
  "C2-1 activation",
  "C2 reserve/padding",
  "C2-2 type REAL mot bas",
  "C2-2 type REAL mot haut",
  "C2-3 pression REAL mot bas",
  "C2-3 pression REAL mot haut",
  "C2-4 reserve",
  "C2-5 reserve",
  "C2-6 reserve",
  "C3 reserve/padding",
  "C3-1 secours",
  "C3-2 reserve",
  "C3-3 reserve",
  "C3-4 reserve",
  "C3-5 reserve",
  "C3-6 reserve",
  "Reserve slot 34",
  "Reserve slot 35",
  "Reserve slot 36",
  "Reserve slot 37",
  "Reserve slot 38",
  "Reserve slot 39",
  "Reserve slot 40",
  "Reserve slot 41",
  "Reserve slot 42",
  "Reserve slot 43",
  "Statut ordre",
  "Padding slot",
];

const registerGuideSteps: RegisterGuideStep[] = [
  {
    title: "1. Preparer",
    register: "%MW1000-%MW1043",
    description: "Le gateway ecrit ID, date, C1, C2, C3, reserves et champs REAL en mot bas puis mot haut.",
    expected: "Readback identique avant trigger",
    tone: "running",
  },
  {
    title: "2. Declencher",
    register: "%MW1044 / %MW1056 / %MW1068",
    description: "Le gateway pose un seul trigger a 1 selon action: upsert, delete ou reset.",
    expected: "Le SBC remet le trigger a 0",
    tone: "active",
  },
  {
    title: "3. Acquitter",
    register: "%MW1045 / %MW1057 / %MW1069",
    description: "Le SBC renvoie le statut operationnel officiel, par exemple 0=OK, 8=multi-trigger, 20=ID invalide.",
    expected: "status_code=0 si operation OK",
    tone: "healthy",
  },
  {
    title: "4. Lire le plan",
    register: "%MW8100-%MW8102 / %MW8120+",
    description: "Le gateway lit l'etat, le CRC, puis les 10 slots de 46 mots du planificateur.",
    expected: "CRC registre = CRC calcule",
    tone: "pass",
  },
];

const registerReferenceGroups: RegisterReferenceGroup[] = [
  {
    title: "Rev02 cible officielle - preparation des ordres",
    badge: "Excel Rev02",
    tone: "healthy",
    description:
      "Adresses attendues par la table d'echange Rev02 du 2026-04-15 pour l'ordre en preparation et les operations Ajout/Suppression/RAZ.",
    rows: [
      {
        range: "%MW1000-%MW1001",
        meaning: "ID unique BDD de l'ordre en preparation",
        format: "UDINT sur 2 mots, mot bas puis mot haut",
        owner: "SteamSwitch ecrit, SBC lit/ecrit",
        status: "Aligne: gateway ecrit et simulateur lit l'UDINT Rev02 en low_word_first.",
      },
      {
        range: "%MW1002-%MW1007",
        meaning: "Date/heure d'execution JOUR, MOIS, ANNEE, HEURE, MINUTE, SECONDE",
        format: "6 x INT, annee AAAA",
        owner: "SteamSwitch ecrit, SBC lit/ecrit",
        status: "Aligne: ordre encode en jour/mois/annee/heure/min/sec Rev02.",
      },
      {
        range: "%MW1008, %MW1010, %MW1012, %MW1014-%MW1016",
        meaning: "Consigne C1 ATT1..ATT6",
        format: "ATT1 INT, ATT2/ATT3 REAL sur 2 mots, ATT4..ATT6 INT",
        owner: "SteamSwitch ecrit, SBC lit/ecrit",
        status: "Aligne: ATT2/ATT3 sont encodes en REAL 32 bits, mot bas puis mot haut.",
      },
      {
        range: "%MW1018, %MW1020, %MW1022, %MW1024-%MW1026",
        meaning: "Consigne C2 ATT1..ATT6",
        format: "ATT1 INT, ATT2/ATT3 REAL sur 2 mots, ATT4..ATT6 INT",
        owner: "SteamSwitch ecrit, SBC lit/ecrit",
        status: "Aligne: ATT2/ATT3 sont encodes en REAL 32 bits, mot bas puis mot haut.",
      },
      {
        range: "%MW1028-%MW1033",
        meaning: "Consigne C3 ATT1..ATT6",
        format: "6 x INT",
        owner: "SteamSwitch ecrit, SBC lit/ecrit",
        status: "Aligne: C3 transporte ATT1..ATT6, les champs non exploites restent a 0.",
      },
      {
        range: "%MW1034-%MW1043",
        meaning: "RESERVES[0..9] de l'ordre en preparation",
        format: "10 x INT",
        owner: "Reserve protocole",
        status: "Aligne: reserves forcees a 0 par le gateway et le simulateur.",
      },
      {
        range: "%MW1044 bit 0 / %MW1045",
        meaning: "Trigger ajout/modification et statut d'operation",
        format: "BOOL + INT",
        owner: "SteamSwitch declenche, SBC acquitte",
        status: "Aligne: trigger bit0 pose par gateway, acquitte a 0 par simulateur.",
      },
      {
        range: "%MW1056 bit 0 / %MW1057",
        meaning: "Trigger suppression et statut d'operation",
        format: "BOOL + INT",
        owner: "SteamSwitch declenche, SBC acquitte",
        status: "Aligne: suppression par ID seulement, champs fonctionnels attendus a 0.",
      },
      {
        range: "%MW1068 bit 0 / %MW1069",
        meaning: "Trigger RAZ planificateur et statut d'operation",
        format: "BOOL + INT",
        owner: "SteamSwitch declenche, SBC acquitte",
        status: "Aligne: RAZ vide le planificateur et recalcule le CRC.",
      },
    ],
  },
  {
    title: "Rev02 cible officielle - lecture planificateur",
    badge: "Plan %MW8100+",
    tone: "healthy",
    description:
      "Zone de visualisation du planificateur dans la table Rev02. Les slots sont espaces de 46 mots et contiennent une structure ordre complete avec reserves et statut.",
    rows: [
      {
        range: "%MW8100",
        meaning: "Etat planificateur",
        format: "INT, 0=OK, 1=NOK/plein",
        owner: "SBC publie, SteamSwitch lit",
        status: "Aligne: publie par le simulateur, lu par read_plan.",
      },
      {
        range: "%MW8101",
        meaning: "CRC du planificateur courant",
        format: "INT",
        owner: "SBC publie, SteamSwitch lit",
        status: "Aligne: CRC publie en registre physique et recalcule cote gateway/UI.",
      },
      {
        range: "%MW8102",
        meaning: "Etat calcul CRC",
        format: "INT, 0=termine, 1=en cours",
        owner: "SBC publie, SteamSwitch lit",
        status: "Aligne: 1 pendant recalcul, 0 quand la copie planificateur est stable.",
      },
      {
        range: "%MW8120-%MW8164",
        meaning: "Slot planificateur 0",
        format: "Ordre complet, base slot 0",
        owner: "SBC publie, SteamSwitch lit",
        status: "Aligne: slot 0 complet sur 46 mots.",
      },
      {
        range: "%MW8120 + slot * 46",
        meaning: "Slots planificateur 0..9",
        format: "10 slots, stride 46, dernier depart observe %MW8534",
        owner: "SBC publie, SteamSwitch lit",
        status: "Aligne: 10 slots officiels, stride 46.",
      },
      {
        range: "Offsets ordre 0,2,3,4,5,6,7,8,10,12,18,20,22,28..44",
        meaning: "Structure interne d'un ordre selon onglet NE PAS TOUCHER 1",
        format: "ID UDINT low_word_first, date INT, C1/C2 avec REAL low_word_first, C3/reserves/statut INT",
        owner: "Structure de reference Rev02",
        status: "Aligne: structure 44 mots utiles + statut + padding par slot.",
      },
    ],
  },
  {
    title: "Slots officiels du planificateur",
    badge: "10 slots",
    tone: "healthy",
    description:
      "Adresses de depart exactes des 10 slots Rev02. Chaque slot occupe 46 mots: 44 mots ordre, 1 statut, 1 padding/reserve.",
    rows: [
      {
        range: "%MW8120-%MW8165",
        meaning: "Slot 0 planificateur",
        format: "46 mots, statut offset +44",
        owner: "SBC publie, gateway/UI lisent",
        status: "Valide terrain: ordre 9101 observe en register_base=8120.",
      },
      {
        range: "%MW8166-%MW8211",
        meaning: "Slot 1 planificateur",
        format: "46 mots, base = 8120 + 1*46",
        owner: "SBC publie, gateway/UI lisent",
        status: "Pret pour deuxieme ordre trie par date/heure.",
      },
      {
        range: "%MW8212-%MW8257",
        meaning: "Slot 2 planificateur",
        format: "46 mots, base = 8120 + 2*46",
        owner: "SBC publie, gateway/UI lisent",
        status: "Structure identique au slot 0.",
      },
      {
        range: "%MW8258-%MW8303",
        meaning: "Slot 3 planificateur",
        format: "46 mots, base = 8120 + 3*46",
        owner: "SBC publie, gateway/UI lisent",
        status: "Structure identique au slot 0.",
      },
      {
        range: "%MW8304-%MW8349",
        meaning: "Slot 4 planificateur",
        format: "46 mots, base = 8120 + 4*46",
        owner: "SBC publie, gateway/UI lisent",
        status: "Structure identique au slot 0.",
      },
      {
        range: "%MW8350-%MW8395",
        meaning: "Slot 5 planificateur",
        format: "46 mots, base = 8120 + 5*46",
        owner: "SBC publie, gateway/UI lisent",
        status: "Structure identique au slot 0.",
      },
      {
        range: "%MW8396-%MW8441",
        meaning: "Slot 6 planificateur",
        format: "46 mots, base = 8120 + 6*46",
        owner: "SBC publie, gateway/UI lisent",
        status: "Structure identique au slot 0.",
      },
      {
        range: "%MW8442-%MW8487",
        meaning: "Slot 7 planificateur",
        format: "46 mots, base = 8120 + 7*46",
        owner: "SBC publie, gateway/UI lisent",
        status: "Structure identique au slot 0.",
      },
      {
        range: "%MW8488-%MW8533",
        meaning: "Slot 8 planificateur",
        format: "46 mots, base = 8120 + 8*46",
        owner: "SBC publie, gateway/UI lisent",
        status: "Structure identique au slot 0.",
      },
      {
        range: "%MW8534-%MW8579",
        meaning: "Slot 9 planificateur",
        format: "46 mots, base = 8120 + 9*46",
        owner: "SBC publie, gateway/UI lisent",
        status: "Dernier slot officiel; planificateur plein si les 10 slots sont occupes.",
      },
    ],
  },
  {
    title: "Codes statuts operationnels",
    badge: "Statuts",
    tone: "warning",
    description:
      "Codes a utiliser pendant les tests pour prouver que le SBC controle vraiment les operations, au lieu de seulement accepter le write Modbus.",
    rows: [
      {
        range: "%MW1045",
        meaning: "Statut ajout/modification",
        format: "0=OK, 1=plein, 2..7=date/heure, 8=multi-trigger, 20=ID, 110..360=C1/C2/C3, 900=erreur interne",
        owner: "SBC/simulateur ecrit, gateway lit",
        status: "Valide terrain: upsert 9101/9201 retourne status_code=0.",
      },
      {
        range: "%MW1057",
        meaning: "Statut suppression",
        format: "0=OK, 1=date non nulle, 8=multi-trigger, 20=ID invalide, 21=ID absent, 100/200/300=C1/C2/C3 non nuls",
        owner: "SBC/simulateur ecrit, gateway lit",
        status: "Pret pour tests delete par ID.",
      },
      {
        range: "%MW1069",
        meaning: "Statut RAZ planificateur",
        format: "0=OK, 8=multi-trigger",
        owner: "SBC/simulateur ecrit, gateway lit",
        status: "Valide terrain: reset avant upsert retourne OK.",
      },
      {
        range: "%MW8100 / %MW8102",
        meaning: "Etat planificateur et etat CRC",
        format: "%MW8100: 0=OK,1=plein; %MW8102: 0=stable,1=calcul en cours",
        owner: "SBC/simulateur ecrit, gateway lit",
        status: "Valide terrain: [0, 37460, 0] apres upsert 9101.",
      },
    ],
  },
  {
    title: "Preuves terrain Rev02",
    badge: "Valide 2026-04-21",
    tone: "pass",
    description:
      "Resultats observes sur IPC et simulateur apres migration. Cette carte sert de reference rapide pour savoir ce qui a deja ete prouve bout a bout.",
    rows: [
      {
        range: "Upsert 9101",
        meaning: "Commande acceptee via %MW1000+ puis %MW1044",
        format: "status=ok, status_code=0",
        owner: "IPC gateway + simulateur",
        status: "Prouve: ordre visible dans read_plan avec register_base=8120.",
      },
      {
        range: "CRC plan 9101",
        meaning: "CRC physique compare au CRC recalc",
        format: "%MW8101=37460 et planner_crc16_calculated=37460",
        owner: "SBC publie, gateway verifie",
        status: "Prouve: planner_crc16_matches=true.",
      },
      {
        range: "Execution 9201",
        meaning: "Ordre execute puis retire de la queue",
        format: "QUEUE_HEAD=[0,0,0,0,0,0,0,0]",
        owner: "Scheduler simulateur",
        status: "Prouve: runtime devient [3,0,9201,53,1].",
      },
      {
        range: "%MW250-%MW256",
        meaning: "Horloge et watchdog Rev02",
        format: "[2026,4,21,8,55,25,132] -> [2026,4,21,8,55,27,134]",
        owner: "Simulateur publie, gateway/telemetry lisent",
        status: "Prouve: seconde et watchdog avancent.",
      },
    ],
  },
  {
    title: "Extension digital twin sans collision Excel",
    badge: "%MW9000+",
    tone: "running",
    description:
      "Registres historiques conserves pour le simulateur physique et la telemetrie NATS. Le miroir procede Rev02 utilise une autre zone haute, afin d'eviter toute collision avec les variables usine Excel.",
    rows: [
      {
        range: "%MW250-%MW256",
        meaning: "Horloge automate GE00 + watchdog GE00_WATCHDOG",
        format: "ANNEE, MOIS, JOUR, HEURE, MINUTE, SECONDE, compteur INT",
        owner: "SBC/simulateur publie, gateway et telemetry lisent",
        status: "Aligne Rev02; le gateway ne force plus un watchdog en ecriture.",
      },
      {
        range: "%MW9000",
        meaning: "Pression vapeur header du digital twin",
        format: "INT x10, ex. 53 = 5.3 bar",
        owner: "Simulateur publie, telemetry_publisher lit",
        status: "Extension runtime; deplace depuis %MW400 pour eviter le drift Rev02.",
      },
      {
        range: "%MW9001",
        meaning: "Demande usine simulee",
        format: "INT kW",
        owner: "Simulateur publie/lit pour override manuel, telemetry_publisher lit",
        status: "Extension runtime; deplace depuis %MW500.",
      },
      {
        range: "%MW9010-%MW9032",
        meaning: "Etat, charge et target des IBC1/IBC2/IBC3",
        format: "3 mots par chaudiere, stride 10",
        owner: "Simulateur publie, telemetry_publisher lit",
        status: "Extension runtime stable pour les dashboards.",
      },
      {
        range: "%MW9070-%MW9074",
        meaning: "Runtime actif: strategie, order_id UDINT low_word_first, pression cible x10, nb stages",
        format: "5 mots INT",
        owner: "Simulateur publie, telemetry_publisher lit",
        status: "Extension runtime; deplace depuis %MW700 pour liberer les plages Rev02.",
      },
    ],
  },
  {
    title: "Pare-feu memoire Simulation -> Reel",
    badge: "offset +9200",
    tone: "warning",
    description:
      "Table de comparaison pour presenter la defense en profondeur OT: en simulation, les variables procede Rev02 sont lues dans une zone decalee. En reel, le gateway lit les vraies adresses LCI.",
    rows: [
      {
        range: "%MW9457-%MW9460 -> %MW257-%MW260",
        meaning: "Sante automate GE00_DEFAUT/NBDEFAUT/ALARME/NBALARME",
        format: "BOOL + compteurs INT",
        owner: "Simulateur publie en zone haute, gateway mappe vers la semantique Rev02",
        status: "Barriere: une ecriture accidentelle simulation ne touche pas GE00 reel.",
      },
      {
        range: "%MW9588 -> %MW388",
        meaning: "PT01_MESURE, pression vapeur chaudiere",
        format: "REAL Float32, 2 mots, Bar",
        owner: "Simulateur publie, mode Simulation lit %MW9588; mode Reel lit %MW388",
        status: "Mapping central pour comparer pression twin vs pression LCI.",
      },
      {
        range: "%MW9590/%MW9592 -> %MW390/%MW392",
        meaning: "PT01_ERREUR et PT01_MESUREPRCT",
        format: "BOOL + REAL Float32 %",
        owner: "Simulateur publie, gateway affiche les labels sim -> reel",
        status: "Permet de tester l'UI capteur sans toucher la zone capteur reelle.",
      },
      {
        range: "%MW9708-%MW9716 -> %MW508-%MW516",
        meaning: "RP08: etat thermo, mode auto/manu/desactive, charge, consigne, boost",
        format: "bits d'etat + REAL charge/consigne",
        owner: "Simulateur publie, gateway decode comme le bloc LCI",
        status: "Le comportement procede est visible sans ecrire dans RP08 reel.",
      },
      {
        range: "%MW9774/%MW9776 -> %MW574/%MW576",
        meaning: "ZT16_MESURE et ZT16_ERREUR, recopie charge thermoplongeur",
        format: "REAL Float32 % + BOOL",
        owner: "Simulateur publie, telemetry et monitor lisent la zone simulee",
        status: "Recopie de charge demonstrable en labo avec separation memoire.",
      },
    ],
  },
];

const demoOrders: ApiBrokerOrderPayload[] = [
  {
    sequence: 214,
    observed_at: "2026-04-02T09:18:44.000000+00:00",
    subject: "cascadya.routing.command",
    reply_subject: "_INBOX.demo.214",
    size_bytes: 182,
    payload_is_json: true,
    payload: {
      id: 41294,
      action: "upsert",
      side: "buy",
      asset_name: "cascadya-ipc-10-109",
      execute_at: "2026-04-02T09:18:50+00:00",
      c1: [5, 40, 5.3, 0, 0, 0],
      c2: [5, 2, 5.3, 0, 0, 0],
      c3: [1, 0, 0, 0, 0, 0],
    },
    summary: {
      action: "upsert",
      order_id: 41294,
      direction: "buy",
      execute_at: "2026-04-02T09:18:50+00:00",
      target: "cascadya-ipc-10-109",
    },
  },
  {
    sequence: 213,
    observed_at: "2026-04-02T09:18:28.000000+00:00",
    subject: "cascadya.routing.command",
    reply_subject: "_INBOX.demo.213",
    size_bytes: 169,
    payload_is_json: true,
    payload: {
      id: 41293,
      action: "upsert",
      side: "sell",
      asset_name: "cascadya-ipc-10-109",
      execute_at: "2026-04-02T09:18:34+00:00",
      c1: [6, 0, 0, 0, 0, 0],
      c2: [0, 0, 0, 0, 0, 0],
      c3: [0, 0, 0, 0, 0, 0],
    },
    summary: {
      action: "upsert",
      order_id: 41293,
      direction: "sell",
      execute_at: "2026-04-02T09:18:34+00:00",
      target: "cascadya-ipc-10-109",
    },
  },
  {
    sequence: 212,
    observed_at: "2026-04-02T09:18:04.000000+00:00",
    subject: "cascadya.routing.command",
    reply_subject: null,
    size_bytes: 74,
    payload_is_json: true,
    payload: {
      id: 41291,
      action: "delete",
      asset_name: "cascadya-ipc-10-109",
    },
    summary: {
      action: "delete",
      order_id: 41291,
      direction: null,
      execute_at: null,
      target: "cascadya-ipc-10-109",
    },
  },
];

const loading = ref(false);
const errorMessage = ref<string | null>(null);
const backendFeed = ref<ApiOrdersFeedPayload | null>(null);
const dispatchResult = ref<ApiOrdersDispatchPayload | null>(null);
const dispatchNotice = ref<string | null>(null);
const dispatchErrorMessage = ref<string | null>(null);
const sendingCommand = ref(false);
const sendingWatchdogPing = ref(false);
const operationModeStatus = ref<OperationModeStatus | null>(null);
const operationModeLoading = ref(false);
const operationModeError = ref<string | null>(null);
const switchingOperationMode = ref<"simulation" | "real" | null>(null);
const refreshIntervalMs = ref(5000);
const displayLimit = ref(FIFO_DISPLAY_LIMIT);
const selectedSequence = ref<number | null>(null);
const fifoClearBoundarySequence = ref<number | null>(null);
const controlsForm = ref<OrderControlFormState>({
  targetAsset: "cascadya-ipc-10-109",
  action: "upsert",
  side: "buy",
  orderId: "50001",
  executeAt: new Date(Date.now() + 60_000).toISOString().slice(0, 16),
  c1ProfileCode: 5,
  c1PowerLimitKw: "40",
  c1ElecPressureBar: "5.3",
  c2Activation: 5,
  c2MetType: 2,
  c2MetPressureBar: "5.3",
  c3Secours: 0,
  c3Word2: "0",
  c3Word3: "0",
});
const watchdogForm = ref<WatchdogFormState>({
  value: "99",
});
const watchdogResult = ref<WatchdogProbeState | null>(null);
const executionLog = ref<ExecutionLogEntry[]>([]);
const lastSentPlannerVerification = ref<LastSentPlannerVerification | null>(null);
const rev02RestrictionsEnabled = ref(true);
const manualPayloadText = ref("");
const manualPayloadError = ref<string | null>(null);
const errorScenarioKey = ref<ErrorTestScenarioKey>("invalid_c1_profile");
const selectedErrorScenario = computed(
  () => errorTestScenarios.find((scenario) => scenario.key === errorScenarioKey.value) ?? errorTestScenarios[0],
);
let pollHandle: number | null = null;
let executionLogSequence = 0;

function toErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : "Une erreur inconnue est survenue.";
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "n/a";
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(parsed);
}

function humanizeBytes(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "n/a";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KiB`;
  }
  return `${(value / (1024 * 1024)).toFixed(2)} MiB`;
}

function payloadPrettyPrint(payload: unknown) {
  if (typeof payload === "string") {
    return payload;
  }
  return JSON.stringify(payload, null, 2);
}

function toRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function normalizeOperationModeStatus(payload: Record<string, unknown>): OperationModeStatus {
  const mode = payload.mode === "real" ? "real" : "simulation";
  return {
    mode,
    label:
      typeof payload.label === "string" && payload.label
        ? payload.label
        : mode === "real"
          ? "LIVE: PHYSICAL PLANT (LCI)"
          : "ENVIRONMENT: DIGITAL TWIN (SAFE)",
    target_host: typeof payload.target_host === "string" ? payload.target_host : "n/a",
    target_port: typeof payload.target_port === "number" ? payload.target_port : 0,
    modbus_connected: payload.modbus_connected === true,
    telemetry_profile: typeof payload.telemetry_profile === "string" ? payload.telemetry_profile : "n/a",
    telemetry_registers: toRecord(payload.telemetry_registers),
    watchdog_strict: payload.watchdog_strict === true,
    watchdog_freeze_threshold_sec:
      typeof payload.watchdog_freeze_threshold_sec === "number" ? payload.watchdog_freeze_threshold_sec : 30,
    fixed_rev02_contract: toRecord(payload.fixed_rev02_contract),
  };
}

function toInt(value: string, fallback = 0) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toFloatValue(value: string, fallback = 0) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? Math.max(0, parsed) : fallback;
}

function toIsoDateTime(value: string) {
  if (!value) {
    return new Date().toISOString();
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString();
}

function toDateTimeLocalValue(date: Date) {
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 16);
}

function profileLabel(profileCode: number) {
  return profileOptions.find((option) => option.value === profileCode)?.label ?? `unknown(${profileCode})`;
}

function u32ToWords(value: number) {
  const normalized = Math.max(0, Math.trunc(value)) >>> 0;
  const highWord = (normalized >>> 16) & 0xffff;
  const lowWord = normalized & 0xffff;
  return [lowWord, highWord];
}

function wordsToU32(firstWord: number | null | undefined, secondWord: number | null | undefined) {
  const low = typeof firstWord === "number" && Number.isFinite(firstWord) ? firstWord & 0xffff : 0;
  const high = typeof secondWord === "number" && Number.isFinite(secondWord) ? secondWord & 0xffff : 0;
  return high * 65536 + low;
}

function floatToWords(value: number) {
  const buffer = new ArrayBuffer(4);
  const view = new DataView(buffer);
  view.setFloat32(0, value, false);
  const highWord = view.getUint16(0, false);
  const lowWord = view.getUint16(2, false);
  return [lowWord, highWord];
}

function buildPlannerWords(state: OrderControlFormState) {
  const c1 = [
    state.c1ProfileCode,
    toFloatValue(state.c1PowerLimitKw, 0),
    toFloatValue(state.c1ElecPressureBar, 0),
    0,
    0,
    0,
  ];
  const c2 = [
    state.c2Activation,
    Math.max(0, state.c2MetType),
    toFloatValue(state.c2MetPressureBar, 0),
    0,
    0,
    0,
  ];
  const c3 = [
    state.c3Secours,
    Math.max(0, toInt(state.c3Word2, 0)),
    Math.max(0, toInt(state.c3Word3, 0)),
    0,
    0,
    0,
  ];

  const executeAt = new Date(state.executeAt || Date.now());
  const slotWords = Array.from({ length: 46 }, () => 0);
  slotWords.splice(0, 2, ...u32ToWords(toInt(state.orderId, 0)));
  slotWords[2] = executeAt.getUTCDate();
  slotWords[3] = executeAt.getUTCMonth() + 1;
  slotWords[4] = executeAt.getUTCFullYear();
  slotWords[5] = executeAt.getUTCHours();
  slotWords[6] = executeAt.getUTCMinutes();
  slotWords[7] = executeAt.getUTCSeconds();
  slotWords[8] = c1[0];
  slotWords.splice(10, 2, ...floatToWords(c1[1]));
  slotWords.splice(12, 2, ...floatToWords(c1[2]));
  slotWords[14] = c1[3];
  slotWords[15] = c1[4];
  slotWords[16] = c1[5];
  slotWords[18] = c2[0];
  slotWords.splice(20, 2, ...floatToWords(c2[1]));
  slotWords.splice(22, 2, ...floatToWords(c2[2]));
  slotWords[24] = c2[3];
  slotWords[25] = c2[4];
  slotWords[26] = c2[5];
  c3.forEach((value, index) => {
    slotWords[28 + index] = value;
  });

  return { c1, c2, c3, words: slotWords };
}

function normalizeNumberArray(value: unknown, length: number) {
  const raw = Array.isArray(value) ? value : [];
  return Array.from({ length }, (_, index) => {
    const numeric = Number(raw[index] ?? 0);
    return Number.isFinite(numeric) ? numeric : 0;
  });
}

function normalizeOptionalNumberArray(value: unknown, maxLength: number) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.slice(0, maxLength).map((item) => {
    const numeric = Number(item);
    return Number.isFinite(numeric) ? numeric : 0;
  });
}

function pad2(value: number) {
  return String(value).padStart(2, "0");
}

function formatPlannerUtcDateTime(value: unknown) {
  if (typeof value !== "string" || value.length === 0) {
    return "n/a";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return [
    `${parsed.getUTCFullYear()}-${pad2(parsed.getUTCMonth() + 1)}-${pad2(parsed.getUTCDate())}`,
    `${pad2(parsed.getUTCHours())}:${pad2(parsed.getUTCMinutes())}:${pad2(parsed.getUTCSeconds())}`,
  ].join(" ");
}

function formatRegisterNumber(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "n/a";
  }
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function formatRegisterArray(values: number[]) {
  return values.length > 0 ? values.map((value) => formatRegisterNumber(value)).join(", ") : "n/a";
}

function registerRange(base: number | null, startOffset: number, endOffset = startOffset) {
  if (base === null) {
    return "%MW?";
  }
  const start = base + startOffset;
  const end = base + endOffset;
  return start === end ? `%MW${start}` : `%MW${start}-%MW${end}`;
}

function approxEqual(left: number | null | undefined, right: number | null | undefined, epsilon = 0.001) {
  if (typeof left !== "number" || typeof right !== "number") {
    return false;
  }
  return Math.abs(left - right) <= epsilon;
}

function arrayApproxEquals(left: number[], right: number[], epsilon = 0.001) {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((value, index) => approxEqual(value, right[index], epsilon));
}

function rawWordsMatch(expected: number[], received: number[]) {
  return expected.length === received.length && expected.every((word, index) => (word & 0xffff) === (received[index] & 0xffff));
}

function verificationTone(matched: boolean | null): BadgeTone {
  if (matched === true) {
    return "healthy";
  }
  if (matched === false) {
    return "warning";
  }
  return "neutral";
}

function buildVerificationRow(
  label: string,
  registers: string,
  sent: string,
  received: string,
  matched: boolean | null,
): PlannerVerificationRow {
  return {
    label,
    registers,
    sent,
    received,
    matched,
    tone: verificationTone(matched),
  };
}

function buildPlannerWordsFromCommandPayload(payload: Record<string, unknown>) {
  const c1 = normalizeNumberArray(payload.c1, 6);
  const c2 = normalizeNumberArray(payload.c2, 6);
  const c3 = normalizeNumberArray(payload.c3, 6);
  const executeAt = new Date(typeof payload.execute_at === "string" ? payload.execute_at : Date.now());
  const slotWords = Array.from({ length: 46 }, () => 0);

  slotWords.splice(0, 2, ...u32ToWords(typeof payload.id === "number" ? payload.id : Number(payload.id ?? 0)));
  slotWords[2] = executeAt.getUTCDate();
  slotWords[3] = executeAt.getUTCMonth() + 1;
  slotWords[4] = executeAt.getUTCFullYear();
  slotWords[5] = executeAt.getUTCHours();
  slotWords[6] = executeAt.getUTCMinutes();
  slotWords[7] = executeAt.getUTCSeconds();
  slotWords[8] = c1[0];
  slotWords.splice(10, 2, ...floatToWords(c1[1]));
  slotWords.splice(12, 2, ...floatToWords(c1[2]));
  slotWords[14] = c1[3];
  slotWords[15] = c1[4];
  slotWords[16] = c1[5];
  slotWords[18] = c2[0];
  slotWords.splice(20, 2, ...floatToWords(c2[1]));
  slotWords.splice(22, 2, ...floatToWords(c2[2]));
  slotWords[24] = c2[3];
  slotWords[25] = c2[4];
  slotWords[26] = c2[5];
  c3.forEach((value, index) => {
    slotWords[28 + index] = value;
  });

  return { c1, c2, c3, words: slotWords };
}

function buildPlannerVerificationSnapshot(payload: Record<string, unknown>): LastSentPlannerVerification | null {
  if (payload.action !== "upsert") {
    return null;
  }

  const planner = buildPlannerWordsFromCommandPayload(payload);
  const rawOrderId = typeof payload.id === "number" ? payload.id : Number(payload.id ?? 0);

  return {
    orderId: Number.isFinite(rawOrderId) ? rawOrderId : null,
    executeAt: formatPlannerUtcDateTime(payload.execute_at),
    c1: planner.c1,
    c2: planner.c2,
    c3: planner.c3,
    words: planner.words,
    crc16: plannerCrc16(planner.words),
    sentAt: new Date().toISOString(),
  };
}

function plannerCrc16(words: number[]) {
  let crc = 0xffff;
  for (const rawWord of words) {
    const word = rawWord & 0xffff;
    const bytes = [(word >> 8) & 0xff, word & 0xff];
    for (const byte of bytes) {
      crc ^= byte;
      for (let index = 0; index < 8; index += 1) {
        crc = crc & 1 ? (crc >> 1) ^ 0xa001 : crc >> 1;
      }
    }
  }
  return crc & 0xffff;
}

function buildCommandPayload(state: OrderControlFormState) {
  const basePayload: Record<string, unknown> = {
    action: state.action,
    asset_name: state.targetAsset.trim() || null,
  };

  if (state.action === "reset" || state.action === "read_plan" || state.action === "register_check") {
    return basePayload;
  }

  basePayload.id = toInt(state.orderId, 50001);

  if (state.action === "delete") {
    return basePayload;
  }

  const planner = buildPlannerWords(state);
  basePayload.side = state.side;
  basePayload.execute_at = toIsoDateTime(state.executeAt);
  basePayload.c1 = planner.c1;
  basePayload.c2 = planner.c2;
  basePayload.c3 = planner.c3;
  return basePayload;
}

function withRev02ValidationMode(payload: Record<string, unknown>, validationMessage: string | null = null) {
  const nextPayload = { ...payload };
  if (!rev02RestrictionsEnabled.value && nextPayload.action === "upsert") {
    nextPayload.validation_mode = "observe_only";
    nextPayload.allow_invalid_order_for_test = true;
    nextPayload.validation_bypass_reason = "operator_requested_plc_security_test";
    if (validationMessage) {
      nextPayload.client_validation_warning = validationMessage;
    }
  }
  return nextPayload;
}

function nextDefaultOrderId() {
  return String(Math.floor(Date.now() / 1000));
}

function appendExecutionLog(message: string, tone: BadgeTone = "neutral") {
  executionLogSequence += 1;
  executionLog.value = [
    {
      id: executionLogSequence,
      loggedAt: new Date().toISOString(),
      message,
      tone,
    },
    ...executionLog.value,
  ].slice(0, EXECUTION_LOG_LIMIT);
}

function clearExecutionLog() {
  executionLog.value = [];
  executionLogSequence = 0;
}

function clearFifoLog() {
  if (rawOrders.value.length === 0) {
    return;
  }

  fifoClearBoundarySequence.value = Math.max(...rawOrders.value.map((order) => order.sequence));
  selectedSequence.value = null;
  appendExecutionLog(`FIFO log cleared locally up to #${fifoClearBoundarySequence.value}`, "neutral");
}

function resetNextOrderId() {
  controlsForm.value.orderId = nextDefaultOrderId();
}

function setExecuteOffset(offsetMs: number) {
  controlsForm.value.executeAt = toDateTimeLocalValue(new Date(Date.now() + offsetMs));
  appendExecutionLog(`Planner time preset loaded: +${Math.round(offsetMs / 1000)}s`, "neutral");
}

function buildBaselineErrorPayload(): Record<string, unknown> {
  return {
    action: "upsert",
    asset_name: controlsForm.value.targetAsset.trim() || "cascadya-ipc-10-109",
    id: toInt(controlsForm.value.orderId, Math.floor(Date.now() / 1000)),
    side: controlsForm.value.side,
    execute_at: new Date(Date.now() + 60_000).toISOString(),
    c1: [5, 40, 5.3, 0, 0, 0],
    c2: [5, 2, 5.3, 0, 0, 0],
    c3: [0, 0, 0, 0, 0, 0],
  };
}

function mutablePlannerArray(payload: Record<string, unknown>, key: "c1" | "c2" | "c3") {
  const normalized = normalizeNumberArray(payload[key], 6);
  payload[key] = normalized;
  return normalized;
}

function buildErrorScenarioPayload(key: ErrorTestScenarioKey) {
  const payload = buildBaselineErrorPayload();
  const c1 = mutablePlannerArray(payload, "c1");
  const c2 = mutablePlannerArray(payload, "c2");
  const c3 = mutablePlannerArray(payload, "c3");

  switch (key) {
    case "invalid_c1_profile":
      c1[0] = 9;
      break;
    case "invalid_c1_power":
      c1[1] = 51;
      break;
    case "invalid_c1_pressure":
      c1[2] = 18.5;
      break;
    case "invalid_c2_activation":
      c2[0] = 0;
      break;
    case "invalid_c2_type":
      c2[1] = 7;
      break;
    case "invalid_c2_pressure":
      c2[2] = 18.5;
      break;
    case "invalid_c3_secours":
      c3[0] = 2;
      break;
    case "invalid_c3_reserved":
      c3[1] = 1;
      break;
    case "past_execute_at":
      payload.execute_at = new Date(Date.now() - 60_000).toISOString();
      break;
    case "missing_order_id":
      delete payload.id;
      break;
    case "wrong_target":
      payload.asset_name = "wrong-ipc-target";
      break;
  }

  return payload;
}

function loadCurrentPayloadForManualEdit() {
  manualPayloadError.value = null;
  manualPayloadText.value = payloadPrettyPrint(
    withRev02ValidationMode(commandPayloadPreview.value, commandValidation.value.message),
  );
  appendExecutionLog("Manual payload loaded from current planner form.", "neutral");
}

function loadErrorScenarioPayload() {
  manualPayloadError.value = null;
  manualPayloadText.value = payloadPrettyPrint(
    withRev02ValidationMode(buildErrorScenarioPayload(errorScenarioKey.value), selectedErrorScenario.value.description),
  );
  appendExecutionLog(`Loaded error test payload: ${selectedErrorScenario.value.label}`, "warning");
}

function toggleRev02Restrictions() {
  if (
    rev02RestrictionsEnabled.value &&
    !window.confirm(
      "Attention: les payloads invalides seront envoyes au PLC pour test de securite. Les alertes resteront visibles. Continuer ?",
    )
  ) {
    appendExecutionLog("Rev02 restrictions standby cancelled by operator.", "neutral");
    return;
  }

  rev02RestrictionsEnabled.value = !rev02RestrictionsEnabled.value;
  appendExecutionLog(
    rev02RestrictionsEnabled.value
      ? "Rev02 restrictions reactivated: invalid orders are blocked before Modbus write."
      : "Rev02 restrictions standby: invalid upserts are sent to PLC for security tests.",
    rev02RestrictionsEnabled.value ? "healthy" : "critical",
  );
}

function openModbusMonitorTab() {
  const routeTarget = router.resolve({
    name: "orders-monitor",
    query: {
      asset: controlsForm.value.targetAsset.trim() || "cascadya-ipc-10-109",
    },
  });
  window.open(routeTarget.href, "_blank", "noopener,noreferrer");
  appendExecutionLog("Opened Modbus simulator monitor in a new tab.", "running");
}

function loadExecutionProfile(profileCode: 2 | 3 | 4 | 5 | 6) {
  controlsForm.value.c1ProfileCode = profileCode;

  if (profileCode === 2) {
    controlsForm.value.c1PowerLimitKw = "40";
    controlsForm.value.c1ElecPressureBar = "5.3";
    controlsForm.value.c2Activation = 5;
    controlsForm.value.c2MetType = 2;
    controlsForm.value.c2MetPressureBar = "5.3";
    controlsForm.value.c3Secours = 1;
    controlsForm.value.c3Word2 = "0";
    controlsForm.value.c3Word3 = "0";
    appendExecutionLog("Loaded rev.2 profile 2.5.*", "healthy");
    return;
  }

  if (profileCode === 5) {
    controlsForm.value.c1PowerLimitKw = "50";
    controlsForm.value.c1ElecPressureBar = "5.5";
    controlsForm.value.c2Activation = 5;
    controlsForm.value.c2MetType = 0;
    controlsForm.value.c2MetPressureBar = "5.5";
    controlsForm.value.c3Secours = 0;
    controlsForm.value.c3Word2 = "0";
    controlsForm.value.c3Word3 = "0";
    appendExecutionLog("Loaded rev.2 profile 5.5.*", "running");
    return;
  }

  if (profileCode === 6) {
    controlsForm.value.c1PowerLimitKw = "0";
    controlsForm.value.c1ElecPressureBar = "0";
    controlsForm.value.c2Activation = 0;
    controlsForm.value.c2MetType = 0;
    controlsForm.value.c2MetPressureBar = "0";
    controlsForm.value.c3Secours = 0;
    controlsForm.value.c3Word2 = "0";
    controlsForm.value.c3Word3 = "0";
    appendExecutionLog("Loaded rev.2 profile 6.0.0", "warning");
    return;
  }

  controlsForm.value.c1PowerLimitKw = "50";
  controlsForm.value.c1ElecPressureBar = "5.3";
  controlsForm.value.c2Activation = 0;
  controlsForm.value.c2MetType = 0;
  controlsForm.value.c2MetPressureBar = "0";
  controlsForm.value.c3Secours = 0;
  controlsForm.value.c3Word2 = "0";
  controlsForm.value.c3Word3 = "0";
  appendExecutionLog(`Loaded rev.2 profile ${profileLabel(profileCode)}`, "neutral");
}

function normalizedReplyStatus(payload: Record<string, unknown> | null | undefined) {
  const rawStatus = payload?.status;
  return typeof rawStatus === "string" ? rawStatus.toLowerCase() : null;
}

function summarizeReplyPayload(action: string, payload: Record<string, unknown> | null | undefined) {
  const status = normalizedReplyStatus(payload);
  const parts = [`ACK ${action}${status ? `: ${status}` : ""}`];

  const statusCode = payload?.status_code;
  if (typeof statusCode === "number" && Number.isFinite(statusCode)) {
    parts.push(`code=${statusCode}`);
  }

  const statusText = payload?.status_text;
  if (typeof statusText === "string" && statusText.length > 0) {
    parts.push(statusText);
  }

  const message = payload?.message;
  if (typeof message === "string" && message.length > 0) {
    parts.push(message);
  }

  return parts.join(" ");
}

function extractReplyValue(payload: Record<string, unknown> | null | undefined) {
  const rawValue = payload?.valeur_retour;
  return typeof rawValue === "number" && Number.isFinite(rawValue) ? rawValue : null;
}

function summarizeCommandPayload(payload: Record<string, unknown>) {
  const action = String(payload.action ?? "command");
  const orderId = payload.id != null ? ` id=${payload.id}` : "";
  const target = payload.asset_name ? ` target=${payload.asset_name}` : "";
  return `${action}${orderId}${target}`;
}

function buildDispatchErrorResult(
  action: string,
  requestPayload: Record<string, unknown>,
  message: string,
): ApiOrdersDispatchPayload {
  return {
    status: "error",
    request_id: `local-error-${Date.now()}`,
    subject: COMMAND_SUBJECT,
    tested_at: new Date().toISOString(),
    round_trip_ms: null,
    request_payload: requestPayload,
    reply_payload: {
      status: "error",
      action,
      message,
    },
  };
}

function orderTone(order: ApiBrokerOrderPayload): BadgeTone {
  const direction = String(order.summary.direction ?? "").toLowerCase();
  if (direction === "buy") {
    return "healthy";
  }
  if (direction === "sell") {
    return "warning";
  }

  const action = String(order.summary.action ?? "").toLowerCase();
  if (action === "delete") {
    return "warning";
  }
  if (action === "reset") {
    return "critical";
  }
  if (action === "upsert" || action === "add" || action === "modify") {
    return "running";
  }
  return "neutral";
}

const canDispatchCommands = computed(() => session.hasPermission("inventory:scan"));
const operationModeTone = computed<BadgeTone>(() => {
  if (!operationModeStatus.value) {
    return "waiting";
  }
  return operationModeStatus.value.mode === "real" ? "critical" : "healthy";
});
const operationModeSummary = computed(() => {
  const status = operationModeStatus.value;
  if (!status) {
    return "Mode non charge";
  }
  const watchdog = status.watchdog_strict ? "watchdog strict" : "watchdog tolerant";
  return `${status.target_host}:${status.target_port} | ${status.telemetry_profile} | ${watchdog}`;
});

const commandPayloadPreview = computed<Record<string, unknown>>(() => buildCommandPayload(controlsForm.value));
const displayedCommandPayload = computed(() => dispatchResult.value?.request_payload ?? commandPayloadPreview.value);
const displayedCommandAction = computed(() => {
  const action = displayedCommandPayload.value.action;
  return typeof action === "string" ? action : controlsForm.value.action;
});

const commandValidation = computed(() => {
  const state = controlsForm.value;
  const target = state.targetAsset.trim();

  if (!target) {
    return { ok: false, message: "La cible IPC est obligatoire pour toutes les commandes." };
  }

  if (state.action === "reset" || state.action === "read_plan" || state.action === "register_check") {
    return { ok: true, message: null };
  }

  const orderId = toInt(state.orderId, 0);
  if (orderId <= 0) {
    return { ok: false, message: "L'Order ID doit etre strictement positif." };
  }

  if (state.action === "delete") {
    return { ok: true, message: null };
  }

  if (!state.executeAt) {
    return { ok: false, message: "La date/heure d'execution est obligatoire pour un upsert." };
  }

  const rule = PROFILE_RULES[state.c1ProfileCode];
  if (!rule) {
    return { ok: false, message: "C1-1 doit etre un profil valide (2, 3, 4, 5 ou 6)." };
  }

  const c1PowerLimit = Number.parseFloat(state.c1PowerLimitKw);
  if (!Number.isFinite(c1PowerLimit) || c1PowerLimit < 0 || c1PowerLimit > MAX_POWER_LIMIT_KW) {
    return { ok: false, message: `C1-2 doit rester dans [0;${MAX_POWER_LIMIT_KW}] kW.` };
  }
  if (state.c1ProfileCode === 6 && c1PowerLimit !== 0) {
    return { ok: false, message: "C1-2 doit etre egal a 0 pour le profil 6.0.0." };
  }

  const c1PressureBar = Number.parseFloat(state.c1ElecPressureBar);
  if (!Number.isFinite(c1PressureBar) || c1PressureBar < 0 || c1PressureBar > MAX_PRESSURE_BAR) {
    return { ok: false, message: `C1-3 doit rester dans [0;${MAX_PRESSURE_BAR}] bar.` };
  }
  if (state.c1ProfileCode === 6 && c1PressureBar !== 0) {
    return { ok: false, message: "C1-3 doit etre egal a 0 pour le profil 6.0.0." };
  }

  if (state.c2Activation !== rule.c2Activation) {
    return {
      ok: false,
      message: `C2-1 doit etre egal a ${rule.c2Activation} pour le profil ${profileLabel(state.c1ProfileCode)}.`,
    };
  }

  if (!rule.c2MetTypeAllowed.includes(state.c2MetType)) {
    return {
      ok: false,
      message: `C2-2 autorise ${rule.c2MetTypeAllowed.join(" ou ")} pour le profil ${profileLabel(state.c1ProfileCode)}.`,
    };
  }

  const c2PressureBar = Number.parseFloat(state.c2MetPressureBar);
  if (!Number.isFinite(c2PressureBar) || c2PressureBar < 0 || c2PressureBar > MAX_PRESSURE_BAR) {
    return { ok: false, message: `C2-3 doit rester dans [0;${MAX_PRESSURE_BAR}] bar.` };
  }
  if (rule.c2MetPressureZeroOnly && c2PressureBar !== 0) {
    return {
      ok: false,
      message: `C2-3 doit etre egal a 0 pour le profil ${profileLabel(state.c1ProfileCode)}.`,
    };
  }

  if (!rule.c3SecoursAllowed.includes(state.c3Secours)) {
    return {
      ok: false,
      message: `C3-1 autorise ${rule.c3SecoursAllowed.join(" ou ")} pour le profil ${profileLabel(state.c1ProfileCode)}.`,
    };
  }

  if (toInt(state.c3Word2, 1) !== 0 || toInt(state.c3Word3, 1) !== 0) {
    return { ok: false, message: "C3-2 et C3-3 doivent rester a 0 dans la revision 2." };
  }

  return { ok: true, message: null };
});

const plannerPreview = computed(() => {
  if (controlsForm.value.action !== "upsert") {
    return null;
  }
  const planner = buildPlannerWords(controlsForm.value);
  return {
    ...planner,
    crc16: plannerCrc16(planner.words),
    profileLabel: profileLabel(controlsForm.value.c1ProfileCode),
  };
});

const plannerReadReply = computed(() => {
  const reply = dispatchResult.value?.reply_payload;
  if (!reply || normalizedReplyStatus(reply) !== "ok" || reply.action !== "read_plan") {
    return null;
  }

  const ordersPayload = Array.isArray(reply.orders) ? reply.orders : [];
  const ordersList = ordersPayload
    .filter((value): value is Record<string, unknown> => value !== null && typeof value === "object")
    .map((value): PlannerReadOrder => {
      const c1 = normalizeOptionalNumberArray(value.c1, 6);
      const c2 = normalizeOptionalNumberArray(value.c2, 6);
      const c3 = normalizeOptionalNumberArray(value.c3, 6);
      const profileCode = typeof value.mode_profile_code === "number" ? value.mode_profile_code : c1[0] ?? null;

      return {
        id: typeof value.id === "number" ? value.id : null,
        executeAt:
          typeof value.execute_at === "string"
            ? value.execute_at.includes("T")
              ? formatPlannerUtcDateTime(value.execute_at)
              : value.execute_at
            : "n/a",
        registerBase: typeof value.register_base === "number" ? value.register_base : null,
        slotIndex: typeof value.slot_index === "number" ? value.slot_index : null,
        profileCode,
        profileLabel:
          typeof value.mode_profile_label === "string"
            ? value.mode_profile_label
            : typeof profileCode === "number"
              ? profileLabel(profileCode)
              : "n/a",
        powerLimitKw: typeof value.power_limit_kw === "number" ? value.power_limit_kw : c1[1] ?? null,
        elecPressureBar:
          typeof value.elec_pressure_bar === "number"
            ? value.elec_pressure_bar
            : typeof c1[2] === "number"
              ? Number(c1[2].toFixed(1))
              : null,
        metType: typeof value.met_type === "number" ? value.met_type : typeof c2[1] === "number" ? Math.round(c2[1]) : null,
        metPressureBar:
          typeof value.met_pressure_bar === "number"
            ? value.met_pressure_bar
            : typeof c2[2] === "number"
              ? Number(c2[2].toFixed(1))
              : null,
        secoursEnabled: typeof value.secours_enabled === "boolean" ? value.secours_enabled : typeof c3[0] === "number" ? c3[0] === 1 : null,
        crc16: typeof value.crc16 === "number" ? value.crc16 : null,
        c1,
        c2,
        c3,
        rawWords: normalizeOptionalNumberArray(value.raw_words, 46),
        orderStatus: typeof value.order_status === "number" ? value.order_status : null,
      };
    });

  return {
    count: typeof reply.count === "number" ? reply.count : ordersList.length,
    plannerCrc16: typeof reply.planner_crc16 === "number" ? reply.planner_crc16 : null,
    plannerWordCount: typeof reply.planner_word_count === "number" ? reply.planner_word_count : null,
    orders: ordersList,
  };
});

const plannerRegisterVerification = computed(() => {
  const sent = lastSentPlannerVerification.value;
  const read = plannerReadReply.value;
  const matchedOrder = sent && read ? read.orders.find((order) => order.id === sent.orderId) ?? null : read?.orders[0] ?? null;
  const rawMatched =
    sent && matchedOrder && matchedOrder.rawWords.length > 0 ? rawWordsMatch(sent.words, matchedOrder.rawWords) : null;
  const base = matchedOrder?.registerBase ?? 8120;
  const wordRows: PlannerVerificationWordRow[] = Array.from({ length: 46 }, (_, index) => {
    const sentWord = sent?.words[index] ?? null;
    const received = matchedOrder?.rawWords[index] ?? null;
    return {
      register: registerRange(base, index),
      label: QUEUE_SLOT_WORD_LABELS[index] ?? `Mot ${index}`,
      sent: sentWord === null ? null : sentWord & 0xffff,
      received,
      matched: sentWord === null || received === null ? null : (sentWord & 0xffff) === (received & 0xffff),
    };
  });
  const matchedWords = wordRows.filter((row) => row.matched === true).length;
  const knownWords = wordRows.filter((row) => row.matched !== null).length;
  const rows = [
    buildVerificationRow(
      "Order ID",
      registerRange(base, 0, 1),
      formatRegisterNumber(sent?.orderId),
      formatRegisterNumber(matchedOrder?.id),
      sent && matchedOrder ? sent.orderId === matchedOrder.id : null,
    ),
    buildVerificationRow(
      "Execution",
      registerRange(base, 2, 7),
      sent?.executeAt ?? "n/a",
      matchedOrder?.executeAt ?? "n/a",
      sent && matchedOrder ? sent.executeAt === matchedOrder.executeAt : null,
    ),
    buildVerificationRow(
      "C1 complet",
      `${registerRange(base, 8)} + ${registerRange(base, 10, 16)}`,
      sent ? formatRegisterArray(sent.c1) : "n/a",
      matchedOrder ? formatRegisterArray(matchedOrder.c1) : "n/a",
      sent && matchedOrder ? arrayApproxEquals(sent.c1, matchedOrder.c1) : null,
    ),
    buildVerificationRow(
      "C2 complet",
      `${registerRange(base, 18)} + ${registerRange(base, 20, 26)}`,
      sent ? formatRegisterArray(sent.c2) : "n/a",
      matchedOrder ? formatRegisterArray(matchedOrder.c2) : "n/a",
      sent && matchedOrder ? arrayApproxEquals(sent.c2, matchedOrder.c2) : null,
    ),
    buildVerificationRow(
      "C3 complet",
      registerRange(base, 28, 33),
      sent ? formatRegisterArray(sent.c3) : "n/a",
      matchedOrder ? formatRegisterArray(matchedOrder.c3) : "n/a",
      sent && matchedOrder ? arrayApproxEquals(sent.c3, matchedOrder.c3) : null,
    ),
    buildVerificationRow(
      "CRC16 slot",
      registerRange(base, 0, 45),
      formatRegisterNumber(sent?.crc16),
      formatRegisterNumber(matchedOrder?.crc16),
      sent && matchedOrder ? sent.crc16 === matchedOrder.crc16 : null,
    ),
    buildVerificationRow(
      "Lot brut 46 mots",
      registerRange(base, 0, 45),
      sent ? `${sent.words.length} mots` : "n/a",
      matchedOrder?.rawWords.length ? `${matchedOrder.rawWords.length} mots` : "raw_words absent",
      rawMatched,
    ),
  ];
  const knownRows = rows.filter((row) => row.matched !== null);
  const matchedRows = knownRows.filter((row) => row.matched === true).length;

  return {
    sent,
    matchedOrder,
    rows,
    wordRows,
    matchedRows,
    knownRows: knownRows.length,
    matchedWords,
    knownWords,
    statusTone: (sent && matchedOrder && knownRows.length > 0 && matchedRows === knownRows.length ? "healthy" : "neutral") as BadgeTone,
  };
});

const plannerRegisterCheckReply = computed(() => {
  const reply = dispatchResult.value?.reply_payload;
  if (!reply || normalizedReplyStatus(reply) !== "ok") {
    return null;
  }

  const check = toRecord(reply.planner_register_check);
  const rowsPayload = Array.isArray(check.rows) ? check.rows : [];
  const rows = rowsPayload
    .filter((value): value is Record<string, unknown> => value !== null && typeof value === "object")
    .map((value): PlannerRegisterCheckRow => {
      const register = typeof value.register === "number" ? value.register : 0;
      return {
        register,
        registerLabel: typeof value.register_label === "string" ? value.register_label : register > 0 ? `%MW${register}` : "%MW?",
        slotIndex: typeof value.slot_index === "number" ? value.slot_index : 0,
        slotOffset: typeof value.slot_offset === "number" ? value.slot_offset : 0,
        field: typeof value.field === "string" ? value.field : "UNKNOWN",
        value: typeof value.value === "number" ? value.value : 0,
      };
    })
    .filter((row) => row.register >= 8120 && row.register <= 8578);

  if (rows.length === 0) {
    return null;
  }

  const slots = Array.from({ length: 10 }, (_, slotIndex): PlannerRegisterCheckSlot => {
    const slotRows = rows.filter((row) => row.slotIndex === slotIndex);
    const hi = slotRows.find((row) => row.slotOffset === 0)?.value ?? 0;
    const lo = slotRows.find((row) => row.slotOffset === 1)?.value ?? 0;
    return {
      slotIndex,
      baseRegister: 8120 + slotIndex * 46,
      orderId: wordsToU32(hi, lo),
      nonZeroCount: slotRows.filter((row) => row.value !== 0).length,
      rows: slotRows,
    };
  });

  return {
    rangeStart: typeof reply.range_start === "number" ? reply.range_start : Number(check.range_start ?? 8120),
    rangeEnd: typeof reply.range_end === "number" ? reply.range_end : Number(check.range_end ?? 8578),
    wordCount: typeof reply.word_count === "number" ? reply.word_count : rows.length,
    rows,
    slots,
  };
});

const demoFeed = computed<ApiOrdersFeedPayload>(() => ({
  status: "ok",
  subject: "cascadya.routing.command",
  connected: true,
  started_at: "2026-04-02T09:00:00.000000+00:00",
  last_message_at: demoOrders[0]?.observed_at ?? null,
  total_seen: 214,
  retained: Math.min(demoOrders.length, displayLimit.value),
  max_items: 200,
  warnings: ["Mode demo : flux Orders simule localement."],
  orders: demoOrders.slice(0, displayLimit.value),
}));

const feed = computed(() => (session.demoModeEnabled ? demoFeed.value : backendFeed.value));
const rawOrders = computed(() => feed.value?.orders ?? []);
const filteredOrders = computed(() => {
  const clearBoundary = fifoClearBoundarySequence.value;
  if (clearBoundary === null) {
    return rawOrders.value;
  }
  return rawOrders.value.filter((order) => order.sequence > clearBoundary);
});
const orders = computed(() => filteredOrders.value.slice(0, FIFO_DISPLAY_LIMIT));
const hiddenFifoCount = computed(() => Math.max(0, rawOrders.value.length - orders.value.length));

const metrics = computed<DashboardMetric[]>(() => {
  const currentFeed = feed.value;
  return [
    {
      title: "Ordres vus",
      value: String(currentFeed?.total_seen ?? 0),
      subtitle: "Messages observes sur le broker",
      tone: currentFeed && currentFeed.total_seen > 0 ? "healthy" : "neutral",
    },
    {
      title: "FIFO retenu",
      value: `${orders.value.length} / ${FIFO_DISPLAY_LIMIT}`,
      subtitle: "Affichage ecran limite; le broker peut retenir plus",
      tone: orders.value.length > 0 ? "running" : "neutral",
    },
    {
      title: "Tap broker",
      value: currentFeed?.connected ? "connecte" : "deconnecte",
      subtitle: currentFeed?.subject ?? "Sujet n/a",
      tone: currentFeed?.connected ? "healthy" : "warning",
    },
    {
      title: "Dernier ordre",
      value: formatDateTime(currentFeed?.last_message_at),
      subtitle: `Refresh ${refreshIntervalMs.value === 0 ? "manuel" : `${refreshIntervalMs.value / 1000}s`}`,
      tone: currentFeed?.last_message_at ? "neutral" : "waiting",
    },
  ];
});

const executionMetrics = computed<DashboardMetric[]>(() => {
  const brokerConnected = Boolean(feed.value?.connected);
  const watchdogStatus = watchdogResult.value?.status ?? null;
  const watchdogIntegrity =
    watchdogResult.value !== null &&
    watchdogStatus === "ok" &&
    watchdogResult.value.returnedValue !== null;
  const dispatchStatus = normalizedReplyStatus(dispatchResult.value?.reply_payload);

  return [
    {
      title: "Broker NATS",
      value: brokerConnected ? "connecte" : "deconnecte",
      subtitle: feed.value?.subject ?? COMMAND_SUBJECT,
      tone: brokerConnected ? "healthy" : "warning",
    },
    {
      title: "Modbus edge",
      value: watchdogResult.value
        ? watchdogIntegrity
          ? "ok"
          : "erreur"
        : dispatchStatus === "ok"
          ? "ack"
          : "inconnu",
      subtitle: watchdogResult.value
        ? "Etat derive du watchdog ping"
        : "Etat derive du dernier request/reply",
      tone: watchdogResult.value
        ? watchdogIntegrity
          ? "healthy"
          : "critical"
        : dispatchStatus === "ok"
          ? "running"
          : "waiting",
    },
    {
      title: "Watchdog RTT",
      value: watchdogResult.value?.roundTripMs != null ? `${watchdogResult.value.roundTripMs} ms` : "---",
      subtitle: `Probe ${PING_SUBJECT}`,
      tone:
        watchdogResult.value?.roundTripMs != null
          ? watchdogIntegrity
            ? "healthy"
            : "warning"
          : "waiting",
    },
    {
      title: "Watchdog read",
      value: watchdogResult.value
        ? watchdogIntegrity
          ? "alive"
          : "failed"
        : "waiting",
      subtitle: watchdogResult.value
        ? `%MW256 lu: ${watchdogResult.value.returnedValue ?? "n/a"}`
        : "Lecture read-only GE00_WATCHDOG",
      tone: watchdogResult.value
        ? watchdogIntegrity
          ? "healthy"
          : "critical"
        : "waiting",
    },
  ];
});

const selectedOrder = computed(() => {
  const currentOrders = orders.value;
  if (currentOrders.length === 0) {
    return null;
  }
  if (selectedSequence.value === null) {
    return currentOrders[0];
  }
  return currentOrders.find((order) => order.sequence === selectedSequence.value) ?? currentOrders[0];
});

async function loadOrders() {
  if (session.demoModeEnabled) {
    errorMessage.value = null;
    return;
  }

  loading.value = true;
  try {
    backendFeed.value = await fetchLiveOrders({ limit: Math.min(displayLimit.value, FIFO_DISPLAY_LIMIT) });
    errorMessage.value = null;
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

async function loadOperationModeStatus() {
  operationModeError.value = null;

  if (session.demoModeEnabled) {
    operationModeStatus.value = normalizeOperationModeStatus({
      status: "ok",
      mode: "simulation",
      label: "ENVIRONMENT: DIGITAL TWIN (SAFE)",
      target_host: "192.168.50.2",
      target_port: 502,
      modbus_connected: true,
      telemetry_profile: "digital_twin",
      watchdog_strict: false,
      watchdog_freeze_threshold_sec: 30,
      telemetry_registers: {
        pressure_bar: { base: 9000, words: 1, type: "UINT16_DECIBAR" },
        demand_kw: { base: 9001, words: 1, type: "UINT16_KW" },
      },
    });
    return;
  }

  if (!canDispatchCommands.value) {
    operationModeError.value = "Le role courant doit avoir inventory:scan pour lire le mode operationnel.";
    return;
  }

  operationModeLoading.value = true;
  try {
    const result = await dispatchOrderCommand({
      subject: COMMAND_SUBJECT,
      timeout_seconds: 5,
      command_payload: {
        action: "operation_mode_status",
        asset_name: controlsForm.value.targetAsset.trim() || "cascadya-ipc-10-109",
      },
    });
    const replyStatus = normalizedReplyStatus(result.reply_payload);
    if (replyStatus !== "ok") {
      throw new Error(typeof result.reply_payload.message === "string" ? result.reply_payload.message : "mode_status_error");
    }
    operationModeStatus.value = normalizeOperationModeStatus(result.reply_payload);
  } catch (error) {
    operationModeError.value = toErrorMessage(error);
  } finally {
    operationModeLoading.value = false;
  }
}

async function switchOperationMode(mode: "simulation" | "real") {
  operationModeError.value = null;

  if (!canDispatchCommands.value) {
    operationModeError.value = "Le role courant doit avoir inventory:scan pour changer de mode.";
    return;
  }

  let confirmation: string | null = null;
  if (mode === "real") {
    const accepted = window.confirm(
      "Attention: le mode REEL cible l'automate physique LCI. Les registres Rev02 restent identiques, mais les ordres peuvent piloter le site physique. Continuer ?",
    );
    if (!accepted) {
      appendExecutionLog("Switch real mode cancelled before confirmation.", "warning");
      return;
    }
    confirmation = window.prompt("Pour confirmer le mode REEL, taper exactement: LCI LIVE");
    if (confirmation !== "LCI LIVE") {
      operationModeError.value = "Confirmation incorrecte: le mode reel n'a pas ete active.";
      appendExecutionLog("Switch real mode refused: confirmation mismatch.", "critical");
      return;
    }
  }

  switchingOperationMode.value = mode;
  appendExecutionLog(`SEND set_operation_mode mode=${mode}`, mode === "real" ? "critical" : "running");
  try {
    const result = await dispatchOrderCommand({
      subject: COMMAND_SUBJECT,
      timeout_seconds: 10,
      command_payload: {
        action: "set_operation_mode",
        asset_name: controlsForm.value.targetAsset.trim() || "cascadya-ipc-10-109",
        mode,
        ...(confirmation ? { confirmation } : {}),
      },
    });
    const replyStatus = normalizedReplyStatus(result.reply_payload);
    if (replyStatus !== "ok") {
      throw new Error(typeof result.reply_payload.message === "string" ? result.reply_payload.message : "set_operation_mode_error");
    }
    operationModeStatus.value = normalizeOperationModeStatus(result.reply_payload);
    appendExecutionLog(`ACK set_operation_mode: ok mode=${operationModeStatus.value.mode}`, "healthy");
  } catch (error) {
    operationModeError.value = toErrorMessage(error);
    appendExecutionLog(`ACK set_operation_mode: ERROR (${operationModeError.value})`, "critical");
  } finally {
    switchingOperationMode.value = null;
  }
}

async function handleSendCommand(actionOverride?: OrderControlFormState["action"]) {
  dispatchNotice.value = null;
  dispatchErrorMessage.value = null;

  if (!canDispatchCommands.value) {
    dispatchErrorMessage.value = "Le role courant doit avoir inventory:scan pour envoyer une commande.";
    return;
  }

  if (actionOverride) {
    controlsForm.value.action = actionOverride;
  }

  if (!commandValidation.value.ok) {
    if (rev02RestrictionsEnabled.value) {
      dispatchErrorMessage.value = commandValidation.value.message;
      appendExecutionLog(`Planner validation failed: ${commandValidation.value.message}`, "critical");
      return;
    }

    dispatchErrorMessage.value =
      `Restrictions Rev02 en veille: ${commandValidation.value.message} L'ordre sera quand meme envoye au PLC.`;
    appendExecutionLog(`Planner validation bypassed for PLC test: ${commandValidation.value.message}`, "critical");
  }

  const payloadPreview = withRev02ValidationMode({ ...commandPayloadPreview.value }, commandValidation.value.message);
  const verificationSnapshot = buildPlannerVerificationSnapshot(payloadPreview);
  if (verificationSnapshot) {
    lastSentPlannerVerification.value = verificationSnapshot;
  } else if (payloadPreview.action === "reset" || payloadPreview.action === "delete") {
    lastSentPlannerVerification.value = null;
  }
  appendExecutionLog(`SEND ${summarizeCommandPayload(payloadPreview)}`, "running");

  if (session.demoModeEnabled) {
    const demoPlannerOrders = demoOrders
      .map((order) => order.payload)
      .filter(
        (payload): payload is Record<string, unknown> & { action: string } =>
          payload !== null &&
          typeof payload === "object" &&
          "action" in payload &&
          payload.action === "upsert",
      )
      .map((payload, index) => {
        const c1 = Array.isArray(payload.c1) ? payload.c1.map((value) => Number(value)).concat([0, 0, 0]).slice(0, 6) : [0, 0, 0, 0, 0, 0];
        const c2 = Array.isArray(payload.c2) ? payload.c2.map((value) => Number(value)).concat([0, 0, 0]).slice(0, 6) : [0, 0, 0, 0, 0, 0];
        const c3 = Array.isArray(payload.c3) ? payload.c3.map((value) => Number(value)).concat([0, 0, 0]).slice(0, 6) : [0, 0, 0, 0, 0, 0];
        const words = Array.from({ length: 46 }, () => 0);
        const executeAt = new Date(typeof payload.execute_at === "string" ? payload.execute_at : Date.now());
        words.splice(0, 2, ...u32ToWords(typeof payload.id === "number" ? payload.id : 0));
        words[2] = executeAt.getUTCDate();
        words[3] = executeAt.getUTCMonth() + 1;
        words[4] = executeAt.getUTCFullYear();
        words[5] = executeAt.getUTCHours();
        words[6] = executeAt.getUTCMinutes();
        words[7] = executeAt.getUTCSeconds();
        words[8] = c1[0];
        words.splice(10, 2, ...floatToWords(c1[1]));
        words.splice(12, 2, ...floatToWords(c1[2]));
        words[18] = c2[0];
        words.splice(20, 2, ...floatToWords(c2[1]));
        words.splice(22, 2, ...floatToWords(c2[2]));
        c3.forEach((value, c3Index) => {
          words[28 + c3Index] = value;
        });
        return {
          id: typeof payload.id === "number" ? payload.id : null,
          execute_at: typeof payload.execute_at === "string" ? payload.execute_at : null,
          register_base: 8120 + index * 46,
          slot_index: index,
          mode_profile_code: c1[0],
          mode_profile_label: profileLabel(c1[0]),
          power_limit_kw: c1[1],
          elec_pressure_bar: c1[2],
          met_type: c2[1],
          met_pressure_bar: c2[2],
          secours_enabled: c3[0] === 1,
          crc16: plannerCrc16(words),
          c1,
          c2,
          c3,
          raw_words: words,
        };
      });

    const demoPlannerWords = demoPlannerOrders.flatMap((order) => {
      const words = Array.from({ length: 46 }, () => 0);
      const executeAt = new Date(order.execute_at ?? Date.now());
      words.splice(0, 2, ...u32ToWords(order.id ?? 0));
      words[2] = executeAt.getUTCDate();
      words[3] = executeAt.getUTCMonth() + 1;
      words[4] = executeAt.getUTCFullYear();
      words[5] = executeAt.getUTCHours();
      words[6] = executeAt.getUTCMinutes();
      words[7] = executeAt.getUTCSeconds();
      words[8] = order.c1[0];
      words.splice(10, 2, ...floatToWords(order.c1[1]));
      words.splice(12, 2, ...floatToWords(order.c1[2]));
      words[18] = order.c2[0];
      words.splice(20, 2, ...floatToWords(order.c2[1]));
      words.splice(22, 2, ...floatToWords(order.c2[2]));
      order.c3.forEach((value, c3Index) => {
        words[28 + c3Index] = value;
      });
      return words;
    });
    dispatchResult.value = {
      status: "ok",
      request_id: `demo-${Date.now()}`,
      subject: COMMAND_SUBJECT,
      tested_at: new Date().toISOString(),
      round_trip_ms: 34.2,
      request_payload: payloadPreview,
      reply_payload:
        controlsForm.value.action === "read_plan"
          ? {
              status: "ok",
              action: "read_plan",
              count: demoPlannerOrders.length,
              planner_crc16: plannerCrc16(demoPlannerWords),
              planner_word_count: demoPlannerWords.length,
              orders: demoPlannerOrders,
            }
          : {
              status: "ok",
              action: controlsForm.value.action,
              order_id: payloadPreview.id ?? null,
              status_code: 0,
              status_text: "ok",
            },
    };
    dispatchNotice.value = "Mode demo : commande simulee localement.";
    appendExecutionLog(`ACK ${controlsForm.value.action}: ok`, "healthy");
    if (controlsForm.value.action === "upsert") {
      resetNextOrderId();
    }
    return;
  }

  sendingCommand.value = true;
  try {
    dispatchResult.value = await dispatchOrderCommand({
      subject: COMMAND_SUBJECT,
      timeout_seconds: 10,
      command_payload: payloadPreview,
    });
    dispatchNotice.value = "Commande envoyee au broker. La reponse request/reply a ete recue.";
    const replyStatus = normalizedReplyStatus(dispatchResult.value.reply_payload);
    appendExecutionLog(
      summarizeReplyPayload(controlsForm.value.action, dispatchResult.value.reply_payload),
      replyStatus === "ok" ? "healthy" : "warning",
    );
    if (controlsForm.value.action === "upsert" && replyStatus === "ok") {
      resetNextOrderId();
    }
    await loadOrders();
  } catch (error) {
    dispatchErrorMessage.value = toErrorMessage(error);
    dispatchResult.value = buildDispatchErrorResult(controlsForm.value.action, payloadPreview, dispatchErrorMessage.value);
    appendExecutionLog(`ACK ${controlsForm.value.action}: ERROR (${dispatchErrorMessage.value})`, "critical");
  } finally {
    sendingCommand.value = false;
  }
}

async function handleSendManualPayload() {
  dispatchNotice.value = null;
  dispatchErrorMessage.value = null;
  manualPayloadError.value = null;

  if (!canDispatchCommands.value) {
    manualPayloadError.value = "Le role courant doit avoir inventory:scan pour envoyer un payload manuel.";
    return;
  }

  let payload: Record<string, unknown>;
  try {
    const parsed = JSON.parse(manualPayloadText.value);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Le payload manuel doit etre un objet JSON.");
    }
    payload = withRev02ValidationMode(parsed as Record<string, unknown>, "Payload manuel envoye en mode banc d'essai.");
  } catch (error) {
    manualPayloadError.value = toErrorMessage(error);
    appendExecutionLog(`Manual payload JSON invalid: ${manualPayloadError.value}`, "critical");
    return;
  }

  const action = typeof payload.action === "string" ? payload.action : "manual";
  const verificationSnapshot = buildPlannerVerificationSnapshot(payload);
  if (verificationSnapshot) {
    lastSentPlannerVerification.value = verificationSnapshot;
  } else if (action === "reset" || action === "delete") {
    lastSentPlannerVerification.value = null;
  }

  if (!rev02RestrictionsEnabled.value && payload.action === "upsert") {
    appendExecutionLog("Manual payload sent with Rev02 gateway restrictions in standby.", "critical");
  }
  appendExecutionLog(`SEND manual ${summarizeCommandPayload(payload)}`, "warning");

  if (session.demoModeEnabled) {
    dispatchResult.value = {
      status: "ok",
      request_id: `manual-demo-${Date.now()}`,
      subject: COMMAND_SUBJECT,
      tested_at: new Date().toISOString(),
      round_trip_ms: 28.6,
      request_payload: payload,
      reply_payload: {
        status: "ok",
        action,
        message: "manual_payload_demo_only",
      },
    };
    dispatchNotice.value = "Mode demo : payload manuel simule localement.";
    appendExecutionLog(`ACK manual ${action}: ok`, "healthy");
    return;
  }

  sendingCommand.value = true;
  try {
    dispatchResult.value = await dispatchOrderCommand({
      subject: COMMAND_SUBJECT,
      timeout_seconds: 15,
      command_payload: payload,
    });
    dispatchNotice.value = "Payload manuel envoye au broker. La reponse request/reply a ete recue.";
    const replyStatus = normalizedReplyStatus(dispatchResult.value.reply_payload);
    appendExecutionLog(
      summarizeReplyPayload(action, dispatchResult.value.reply_payload),
      replyStatus === "ok" ? "healthy" : "warning",
    );
    if (action === "upsert" && replyStatus === "ok") {
      resetNextOrderId();
    }
    await loadOrders();
  } catch (error) {
    dispatchErrorMessage.value = toErrorMessage(error);
    manualPayloadError.value = dispatchErrorMessage.value;
    dispatchResult.value = buildDispatchErrorResult(action, payload, dispatchErrorMessage.value);
    appendExecutionLog(`ACK manual ${action}: ERROR (${dispatchErrorMessage.value})`, "critical");
  } finally {
    sendingCommand.value = false;
  }
}

async function handleWatchdogPing() {
  dispatchErrorMessage.value = null;

  if (!canDispatchCommands.value) {
    dispatchErrorMessage.value = "Le role courant doit avoir inventory:scan pour envoyer un watchdog ping.";
    return;
  }

  const requestValue = toInt(watchdogForm.value.value, 99);
  appendExecutionLog(`SEND watchdog ping value=${requestValue}`, "running");

  if (session.demoModeEnabled) {
    watchdogResult.value = {
      status: "ok",
      requestValue,
      returnedValue: requestValue,
      roundTripMs: 22.4,
      testedAt: new Date().toISOString(),
      message: null,
    };
    appendExecutionLog(`ACK watchdog read value=${requestValue}`, "healthy");
    return;
  }

  sendingWatchdogPing.value = true;
  try {
    const result = await dispatchOrderCommand({
      subject: PING_SUBJECT,
      timeout_seconds: 5,
      command_payload: {
        compteur: requestValue,
      },
    });
    const replyStatus = normalizedReplyStatus(result.reply_payload);
    const returnedValue = extractReplyValue(result.reply_payload);
    const message = typeof result.reply_payload.message === "string" ? result.reply_payload.message : null;
    watchdogResult.value = {
      status: replyStatus ?? "error",
      requestValue,
      returnedValue,
      roundTripMs: result.round_trip_ms,
      testedAt: result.tested_at,
      message,
    };
    appendExecutionLog(
      replyStatus === "ok"
        ? `ACK watchdog read value=${returnedValue ?? "n/a"}`
        : `ACK watchdog failed received=${returnedValue ?? "n/a"}`,
      replyStatus === "ok" ? "healthy" : "warning",
    );
  } catch (error) {
    const message = toErrorMessage(error);
    watchdogResult.value = {
      status: "error",
      requestValue,
      returnedValue: null,
      roundTripMs: null,
      testedAt: new Date().toISOString(),
      message,
    };
    appendExecutionLog(`ACK watchdog: ERROR (${message})`, "critical");
  } finally {
    sendingWatchdogPing.value = false;
  }
}

function handleSchedulerSubmit() {
  void handleSendCommand(controlsForm.value.action);
}

function stopPolling() {
  if (pollHandle !== null) {
    window.clearInterval(pollHandle);
    pollHandle = null;
  }
}

function restartPolling() {
  stopPolling();
  if (session.demoModeEnabled || refreshIntervalMs.value <= 0) {
    return;
  }
  pollHandle = window.setInterval(() => {
    void loadOrders();
  }, refreshIntervalMs.value);
}

watch(
  () => [displayLimit.value, refreshIntervalMs.value, session.demoModeEnabled],
  () => {
    void loadOrders();
    restartPolling();
  },
  { immediate: true },
);

watch(
  orders,
  (currentOrders) => {
    if (currentOrders.length === 0) {
      selectedSequence.value = null;
      return;
    }
    const stillExists = currentOrders.some((order) => order.sequence === selectedSequence.value);
    if (!stillExists) {
      selectedSequence.value = currentOrders[0].sequence;
    }
  },
  { immediate: true },
);

resetNextOrderId();
setExecuteOffset(60_000);
appendExecutionLog("Execution panel ready.", "neutral");
void loadOperationModeStatus();

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<template>
  <section class="stack-card">
    <header class="page-heading orders-heading">
      <div>
        <p class="muted-2 uppercase">Broker observability</p>
        <h1>Orders</h1>
        <p class="helper-text">
          Surveillance du flux d'ordres C-market qui traverse le broker avant d'atteindre les IPC.
        </p>
      </div>

      <div class="controls-shell">
        <label class="field">
          <span>Refresh</span>
          <select v-model.number="refreshIntervalMs">
            <option v-for="option in refreshOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>Afficher</span>
          <select v-model.number="displayLimit">
            <option v-for="option in displayLimitOptions" :key="option" :value="option">
              {{ option }} derniers ordres
            </option>
          </select>
        </label>

        <button class="button-secondary" type="button" :disabled="loading" @click="loadOrders">
          {{ loading ? "Chargement..." : "Rafraichir" }}
        </button>
      </div>
    </header>

    <section class="metric-grid">
      <MetricCard
        v-for="metric in metrics"
        :key="metric.title"
        :title="metric.title"
        :value="metric.value"
        :subtitle="metric.subtitle"
        :tone="metric.tone"
      />
    </section>

    <section
      class="surface-card section-shell operation-mode-card"
      :data-mode="operationModeStatus?.mode ?? 'unknown'"
    >
      <div class="section-header">
        <div>
          <p class="muted-2 uppercase">Iso-production</p>
          <h2>Mode operationnel</h2>
          <p class="helper-text">
            Les registres Rev02 de commande restent fixes. Le mode change uniquement la cible Modbus, la lecture
            telemetry et la politique watchdog.
          </p>
        </div>
        <StatusBadge
          :label="operationModeStatus?.label ?? 'mode non charge'"
          :tone="operationModeTone"
          compact
        />
      </div>

      <div class="operation-mode-grid">
        <article class="operation-mode-tile">
          <p class="muted-2 uppercase">Cible active</p>
          <strong>{{ operationModeStatus ? `${operationModeStatus.target_host}:${operationModeStatus.target_port}` : "n/a" }}</strong>
          <span>{{ operationModeSummary }}</span>
        </article>
        <article class="operation-mode-tile">
          <p class="muted-2 uppercase">Securite</p>
          <strong>
            {{
              operationModeStatus
                ? operationModeStatus.watchdog_strict
                  ? "WATCHDOG STRICT"
                  : "WATCHDOG TOLERANT"
                : "n/a"
            }}
          </strong>
          <span>Blocage commandes si %MW256 fige en mode reel.</span>
        </article>
        <article class="operation-mode-tile">
          <p class="muted-2 uppercase">Contrat intouchable</p>
          <strong>%MW1000+ / %MW8100+</strong>
          <span>Preparation, triggers, statuts et slots restent identiques simulation/reel.</span>
        </article>
      </div>

      <div class="action-row">
        <button class="button-secondary" type="button" :disabled="operationModeLoading" @click="loadOperationModeStatus">
          {{ operationModeLoading ? "Lecture..." : "Lire mode" }}
        </button>
        <button
          class="button-secondary"
          type="button"
          :disabled="switchingOperationMode !== null || operationModeStatus?.mode === 'simulation'"
          @click="switchOperationMode('simulation')"
        >
          {{ switchingOperationMode === "simulation" ? "Bascule..." : "Mode Simulation" }}
        </button>
        <button
          class="button-secondary button-danger"
          type="button"
          :disabled="switchingOperationMode !== null || operationModeStatus?.mode === 'real'"
          @click="switchOperationMode('real')"
        >
          {{ switchingOperationMode === "real" ? "Bascule..." : "Mode Reel LCI" }}
        </button>
      </div>

      <p v-if="operationModeError" class="error-copy">{{ operationModeError }}</p>
    </section>

    <section v-if="errorMessage" class="notice-shell notice-error">
      {{ errorMessage }}
    </section>

    <section v-else-if="feed?.warnings?.length" class="notice-shell notice-warning">
      {{ feed.warnings.join(" | ") }}
    </section>

    <section class="surface-card section-shell">
      <div class="section-header">
        <div>
          <p class="muted-2 uppercase">Visualisation</p>
          <h2>Flux observe sur le broker</h2>
        </div>
        <StatusBadge :label="feed?.subject ?? COMMAND_SUBJECT" tone="neutral" compact />
      </div>

      <div class="orders-layout">
        <PanelCard
          title="FIFO log"
          :status="feed?.connected ? 'broker tap online' : 'broker tap offline'"
          :status-tone="feed?.connected ? 'healthy' : 'warning'"
          :accent-tone="feed?.connected ? 'healthy' : 'warning'"
        >
          <div class="fifo-toolbar">
            <p class="helper-text">
              {{
                hiddenFifoCount > 0
                  ? `${hiddenFifoCount} message(s) masque(s); seuls les nouveaux evenements seront affiches.`
                  : `Affichage FIFO limite aux ${FIFO_DISPLAY_LIMIT} derniers messages.`
              }}
            </p>
            <button class="button-secondary button-compact" type="button" :disabled="rawOrders.length === 0" @click="clearFifoLog">
              Clear FIFO
            </button>
          </div>
          <div class="table-shell">
            <table class="orders-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Observe le</th>
                  <th>Action</th>
                  <th>Sens</th>
                  <th>Order ID</th>
                  <th>Cible</th>
                  <th>Reply</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="order in orders"
                  :key="order.sequence"
                  :class="{ 'row-selected': selectedOrder?.sequence === order.sequence }"
                  @click="selectedSequence = order.sequence"
                >
                  <td class="mono">#{{ order.sequence }}</td>
                  <td>{{ formatDateTime(order.observed_at) }}</td>
                  <td>
                    <StatusBadge
                      :label="order.summary.action ?? 'message'"
                      :tone="orderTone(order)"
                      compact
                    />
                  </td>
                  <td>{{ order.summary.direction ?? "n/a" }}</td>
                  <td class="mono">{{ order.summary.order_id ?? "n/a" }}</td>
                  <td>{{ order.summary.target ?? "broadcast" }}</td>
                  <td class="mono">{{ order.reply_subject ?? "none" }}</td>
                </tr>
                <tr v-if="orders.length === 0">
                  <td colspan="7" class="muted-copy">Aucun ordre observe pour le moment sur le broker.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </PanelCard>

        <PanelCard
          title="Ordre selectionne"
          :status="selectedOrder?.summary.direction ?? selectedOrder?.summary.action ?? 'idle'"
          :status-tone="selectedOrder ? orderTone(selectedOrder) : 'neutral'"
          :accent-tone="selectedOrder ? orderTone(selectedOrder) : 'neutral'"
        >
          <template v-if="selectedOrder">
            <div class="detail-grid">
              <p><strong>Sujet :</strong> <span class="mono">{{ selectedOrder.subject }}</span></p>
              <p><strong>Observe le :</strong> {{ formatDateTime(selectedOrder.observed_at) }}</p>
              <p><strong>Order ID :</strong> <span class="mono">{{ selectedOrder.summary.order_id ?? "n/a" }}</span></p>
              <p><strong>Execution :</strong> {{ selectedOrder.summary.execute_at ?? "n/a" }}</p>
              <p><strong>Cible :</strong> {{ selectedOrder.summary.target ?? "broadcast" }}</p>
              <p><strong>Taille :</strong> {{ humanizeBytes(selectedOrder.size_bytes) }}</p>
            </div>

            <div class="payload-shell">
              <div class="payload-header">
                <h3>Payload brut</h3>
                <StatusBadge
                  :label="selectedOrder.payload_is_json ? 'json' : 'raw'"
                  :tone="selectedOrder.payload_is_json ? 'healthy' : 'neutral'"
                  compact
                />
              </div>
              <pre class="payload-preview">{{ payloadPrettyPrint(selectedOrder.payload) }}</pre>
            </div>
          </template>

          <p v-else class="helper-text">
            Le panneau de detail s'active des qu'un ordre apparait dans le FIFO.
          </p>
        </PanelCard>
      </div>
    </section>

    <section class="surface-card section-shell">
      <div class="section-header">
        <div>
          <p class="muted-2 uppercase">Execution</p>
          <h2>Piloter le PLC depuis le control panel</h2>
          <p class="helper-text">
            Outils d'execution web pour watchdog ping, profils scheduler, envoi de commandes et journal d'execution,
            tout en reutilisant le broker probe deja en place.
          </p>
        </div>
        <StatusBadge :label="COMMAND_SUBJECT" tone="running" compact />
      </div>

      <p class="notice-shell notice-warning">
        Le flux rev.2 est maintenant cible par <code>asset_name</code> et valide cote gateway. Cette vue aligne les
        mots C1/C2/C3, la lecture du planificateur et le CRC de previsualisation sur la meme table d'echange.
      </p>

      <section class="metric-grid execution-metric-grid">
        <MetricCard
          v-for="metric in executionMetrics"
          :key="`execution-${metric.title}`"
          :title="metric.title"
          :value="metric.value"
          :subtitle="metric.subtitle"
          :tone="metric.tone"
        />
      </section>

      <div class="execution-utility-grid">
        <PanelCard
          title="Watchdog PLC (%MW256)"
          :status="watchdogResult?.status ?? 'idle'"
          :status-tone="watchdogResult?.status === 'ok' ? 'healthy' : watchdogResult ? 'warning' : 'waiting'"
          :accent-tone="watchdogResult?.status === 'ok' ? 'healthy' : watchdogResult ? 'warning' : 'waiting'"
        >
          <div class="watchdog-form">
            <label class="field">
              <span>Marqueur de requete (Rev02 lit %MW256)</span>
              <input v-model="watchdogForm.value" type="number" min="0" />
            </label>
            <div class="action-row">
              <button class="button-secondary" type="button" :disabled="sendingWatchdogPing" @click="handleWatchdogPing">
                {{ sendingWatchdogPing ? "Lecture..." : "Read watchdog" }}
              </button>
            </div>
          </div>

          <div class="watchdog-grid">
            <article class="watchdog-tile">
              <p class="muted-2 uppercase">Returned value</p>
              <strong>{{ watchdogResult?.returnedValue ?? "---" }}</strong>
            </article>
            <article class="watchdog-tile">
              <p class="muted-2 uppercase">Lecture Rev02</p>
              <strong>
                {{
                  watchdogResult
                    ? watchdogResult.status === "ok" && watchdogResult.returnedValue !== null
                      ? "ALIVE"
                      : "FAILED"
                    : "WAITING"
                }}
              </strong>
            </article>
          </div>

          <p v-if="watchdogResult?.message" class="helper-text error-copy">{{ watchdogResult.message }}</p>
        </PanelCard>

        <PanelCard title="Quick tools" status="rev.2 exchange table" status-tone="running" accent-tone="running">
          <div class="quick-tools">
            <div class="quick-row">
              <button class="button-secondary" type="button" @click="setExecuteOffset(60_000)">+60s</button>
              <button class="button-secondary" type="button" @click="setExecuteOffset(300_000)">+5min</button>
              <button class="button-secondary" type="button" @click="resetNextOrderId()">Reset ID</button>
            </div>

            <div class="quick-row">
              <button class="button-secondary" type="button" @click="loadExecutionProfile(2)">
                Profil 2.5.*
              </button>
              <button class="button-secondary" type="button" @click="loadExecutionProfile(3)">
                Profil 3.0.0
              </button>
              <button class="button-secondary" type="button" @click="loadExecutionProfile(4)">
                Profil 4.0.0
              </button>
            </div>

            <div class="quick-row">
              <button class="button-secondary" type="button" @click="loadExecutionProfile(5)">
                Profil 5.5.*
              </button>
              <button class="button-secondary" type="button" @click="loadExecutionProfile(6)">
                Profil 6.0.0
              </button>
            </div>

            <p class="helper-text">
              Presets rapides pour les profils de test les plus utiles, avec contraintes rev.2 appliquees des la
              previsualisation.
            </p>
          </div>
        </PanelCard>
      </div>

      <details class="register-reference-shell">
        <summary>
          <div>
            <p class="muted-2 uppercase">Table d'echange Rev02</p>
            <h2>Cartographie active des registres IPC / simulateur</h2>
            <p class="helper-text">
              Section repliable pour presenter les categories Rev02, les offsets concrets et les registres runtime du
              jumeau numerique.
            </p>
          </div>
          <StatusBadge label="Rev02 actif" tone="healthy" compact />
        </summary>

        <p class="notice-shell notice-warning">
          Audit du fichier <code>Table d'echange concept - Rev 02 du 2026 04 15.xlsm</code> : la preparation des
          ordres est maintenant en <code>%MW1000+</code>, les triggers/status en <code>%MW1044+</code> et le
          planificateur en <code>%MW8100+</code>. Les signaux propres au digital twin sont isoles en
          <code>%MW9000+</code>, et les variables procede Rev02 simulees sont decalees avec la regle
          <code>sim = reel + 9200</code> pour eviter toute collision avec les variables usine Excel.
        </p>

        <div class="register-guide-strip">
          <article v-for="step in registerGuideSteps" :key="step.title" class="register-guide-step" :data-tone="step.tone">
            <div class="payload-header">
              <h3>{{ step.title }}</h3>
              <StatusBadge :label="step.register" :tone="step.tone" compact />
            </div>
            <p class="helper-text">{{ step.description }}</p>
            <p class="mono register-guide-expected">{{ step.expected }}</p>
          </article>
        </div>

        <div class="register-reference-grid">
          <article v-for="group in registerReferenceGroups" :key="group.title" class="register-reference-card">
            <div class="payload-header">
              <div>
                <p class="muted-2 uppercase">{{ group.badge }}</p>
                <h3>{{ group.title }}</h3>
              </div>
              <StatusBadge :label="group.badge" :tone="group.tone" compact />
            </div>
            <p class="helper-text">{{ group.description }}</p>

            <div class="table-shell register-table-shell">
              <table class="orders-table register-reference-table">
                <thead>
                  <tr>
                    <th>Registre / plage</th>
                    <th>Correspondance</th>
                    <th>Format</th>
                    <th>Proprietaire</th>
                    <th>Etat IPC / simulateur</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in group.rows" :key="`${group.title}-${row.range}`">
                    <td class="mono">{{ row.range }}</td>
                    <td>{{ row.meaning }}</td>
                    <td>{{ row.format }}</td>
                    <td>{{ row.owner }}</td>
                    <td>{{ row.status }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </div>
      </details>

      <div class="controls-layout">
        <PanelCard title="Planificateur" status="write path" status-tone="running" accent-tone="running">
          <form class="control-form" @submit.prevent="handleSchedulerSubmit">
            <label class="field">
              <span>Target asset</span>
              <input v-model="controlsForm.targetAsset" type="text" placeholder="cascadya-ipc-10-109" />
            </label>

            <label class="field">
              <span>Action</span>
              <select v-model="controlsForm.action">
                <option value="upsert">upsert</option>
                <option value="delete">delete</option>
                <option value="reset">reset</option>
                <option value="read_plan">read_plan</option>
                <option value="register_check">register_check</option>
              </select>
            </label>

            <label class="field">
              <span>Market side</span>
              <select v-model="controlsForm.side" :disabled="controlsForm.action !== 'upsert'">
                <option value="buy">buy</option>
                <option value="sell">sell</option>
              </select>
            </label>

            <label class="field">
              <span>Order ID</span>
              <input
                v-model="controlsForm.orderId"
                type="number"
                min="1"
                :disabled="controlsForm.action === 'reset' || controlsForm.action === 'read_plan' || controlsForm.action === 'register_check'"
              />
            </label>

            <label class="field field-wide">
              <span>Execute at</span>
              <input
                v-model="controlsForm.executeAt"
                type="datetime-local"
                :disabled="controlsForm.action !== 'upsert'"
              />
            </label>

            <div v-if="controlsForm.action === 'upsert'" class="consigne-grid field-wide">
              <article class="consigne-card">
                <h3>C1</h3>
                <label class="field">
                  <span>C1-1 Profil</span>
                  <select v-model.number="controlsForm.c1ProfileCode">
                    <option v-for="option in profileOptions" :key="`c1-${option.value}`" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <label class="field">
                  <span>C1-2 Limitation puissance (kW)</span>
                  <input v-model="controlsForm.c1PowerLimitKw" type="number" min="0" max="50" step="0.1" />
                </label>
                <label class="field">
                  <span>C1-3 Consigne ELEC (bar)</span>
                  <input v-model="controlsForm.c1ElecPressureBar" type="number" min="0" max="18" step="0.1" />
                </label>
              </article>

              <article class="consigne-card">
                <h3>C2</h3>
                <label class="field">
                  <span>C2-1 Activation</span>
                  <input v-model.number="controlsForm.c2Activation" type="number" min="0" max="5" />
                </label>
                <label class="field">
                  <span>C2-2 Type MET</span>
                  <select v-model.number="controlsForm.c2MetType">
                    <option v-for="option in metTypeOptions" :key="`c2-type-${option.value}`" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <label class="field">
                  <span>C2-3 Consigne MET (bar)</span>
                  <input v-model="controlsForm.c2MetPressureBar" type="number" min="0" max="18" step="0.1" />
                </label>
              </article>

              <article class="consigne-card">
                <h3>C3</h3>
                <label class="field">
                  <span>C3-1 Secours</span>
                  <select v-model.number="controlsForm.c3Secours">
                    <option v-for="option in secoursOptions" :key="`c3-${option.value}`" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <label class="field">
                  <span>C3-2</span>
                  <input v-model="controlsForm.c3Word2" type="number" min="0" max="0" />
                </label>
                <label class="field">
                  <span>C3-3</span>
                  <input v-model="controlsForm.c3Word3" type="number" min="0" max="0" />
                </label>
              </article>
            </div>

            <div v-if="controlsForm.action === 'upsert'" class="planner-preview-grid field-wide">
              <article class="planner-preview-card">
                <p class="muted-2 uppercase">Rev.2 preview</p>
                <h3>{{ plannerPreview?.profileLabel ?? "n/a" }}</h3>
                <p class="helper-text">
                  CRC16 preview:
                  <strong class="mono">{{ plannerPreview?.crc16 ?? "n/a" }}</strong>
                </p>
                <p class="helper-text">
                  C1={{ plannerPreview?.c1.join(", ") ?? "n/a" }} |
                  C2={{ plannerPreview?.c2.join(", ") ?? "n/a" }} |
                  C3={{ plannerPreview?.c3.join(", ") ?? "n/a" }}
                </p>
              </article>
              <article class="planner-preview-card">
                <p class="muted-2 uppercase">Validation locale</p>
                <h3 :class="commandValidation.ok ? 'success-copy' : rev02RestrictionsEnabled ? 'error-copy' : 'warning-copy'">
                  {{
                    commandValidation.ok
                      ? "Payload conforme"
                      : rev02RestrictionsEnabled
                        ? "Correction requise"
                        : "Alerte non bloquante"
                  }}
                </h3>
                <p class="helper-text">
                  {{
                    commandValidation.ok
                      ? "La previsualisation respecte les bornes et obligations de la revision 2."
                      : rev02RestrictionsEnabled
                        ? commandValidation.message
                        : `${commandValidation.message} L'envoi restera possible pour observer le code PLC.`
                  }}
                </p>
              </article>
            </div>

            <div class="error-test-shell field-wide">
              <div class="payload-header">
                <div>
                  <p class="muted-2 uppercase">Banc d'essai erreurs Rev02</p>
                  <h3>Payload manuel avant envoi</h3>
                </div>
                <div class="badge-row">
                  <StatusBadge label="manual override" tone="warning" compact />
                  <StatusBadge
                    :label="rev02RestrictionsEnabled ? 'restrictions actives' : 'restrictions en veille'"
                    :tone="rev02RestrictionsEnabled ? 'healthy' : 'critical'"
                    compact
                  />
                </div>
              </div>
              <p class="helper-text">
                Cette zone sert a provoquer volontairement des erreurs de validation ou a modifier le JSON juste avant
                l'envoi. Les profils normaux et les registres Rev02 ne sont pas modifies.
              </p>

              <div class="safety-standby-panel" :data-active="rev02RestrictionsEnabled ? 'yes' : 'no'">
                <div>
                  <p class="muted-2 uppercase">Mode restrictions Rev02</p>
                  <h3>{{ rev02RestrictionsEnabled ? "Enforcement actif" : "Standby banc d'essai PLC" }}</h3>
                  <p class="helper-text">
                    {{
                      rev02RestrictionsEnabled
                        ? "Le Control Panel et le gateway bloquent les payloads non conformes avant ecriture Modbus."
                        : "Les alertes restent affichees, mais les upserts invalides portent validation_mode=observe_only et atteignent le trigger PLC."
                    }}
                  </p>
                </div>
                <button
                  class="button-secondary"
                  :class="rev02RestrictionsEnabled ? 'button-danger' : 'button-warning'"
                  type="button"
                  @click="toggleRev02Restrictions"
                >
                  {{ rev02RestrictionsEnabled ? "Desactiver restrictions" : "Reactiver restrictions" }}
                </button>
              </div>

              <div class="manual-test-grid">
                <label class="field">
                  <span>Scenario erreur</span>
                  <select v-model="errorScenarioKey">
                    <option v-for="scenario in errorTestScenarios" :key="scenario.key" :value="scenario.key">
                      {{ scenario.label }}
                    </option>
                  </select>
                </label>
                <article class="manual-scenario-card">
                  <p class="muted-2 uppercase">Resultat attendu</p>
                  <strong>{{ selectedErrorScenario.expected }}</strong>
                  <p class="helper-text">
                    {{ selectedErrorScenario.description }}
                  </p>
                </article>
              </div>

              <div class="action-row action-row-compact">
                <button class="button-secondary" type="button" @click="loadCurrentPayloadForManualEdit">
                  Charger payload actuel
                </button>
                <button class="button-secondary button-warning" type="button" @click="loadErrorScenarioPayload">
                  Charger scenario erreur
                </button>
                <button
                  class="button-secondary button-danger"
                  type="button"
                  :disabled="sendingCommand || !canDispatchCommands || manualPayloadText.trim().length === 0"
                  @click="handleSendManualPayload"
                >
                  {{ sendingCommand ? "Envoi manuel..." : "Envoyer JSON manuel" }}
                </button>
              </div>

              <label class="field">
                <span>Payload JSON editable</span>
                <textarea
                  v-model="manualPayloadText"
                  class="manual-payload-editor"
                  rows="12"
                  spellcheck="false"
                  placeholder='{"action":"upsert","asset_name":"cascadya-ipc-10-109",...}'
                ></textarea>
              </label>
              <p v-if="manualPayloadError" class="helper-text error-copy">{{ manualPayloadError }}</p>
              <p class="helper-text warning-copy">
                Note: ces tests passent volontairement autour de la validation locale du formulaire pour laisser le
                gateway repondre avec son erreur reelle.
              </p>
            </div>

            <div class="action-row">
              <button
                class="button-secondary"
                type="button"
                :disabled="sendingCommand || !canDispatchCommands"
                @click="handleSendCommand('upsert')"
              >
                {{ sendingCommand && controlsForm.action === "upsert" ? "Envoi..." : "Upsert order" }}
              </button>
              <button
                class="button-secondary button-warning"
                type="button"
                :disabled="sendingCommand || !canDispatchCommands"
                @click="handleSendCommand('delete')"
              >
                {{ sendingCommand && controlsForm.action === "delete" ? "Suppression..." : "Delete by ID" }}
              </button>
              <button
                class="button-secondary button-danger"
                type="button"
                :disabled="sendingCommand || !canDispatchCommands"
                @click="handleSendCommand('reset')"
              >
                {{ sendingCommand && controlsForm.action === "reset" ? "Reset..." : "Reset queue" }}
              </button>
              <button
                class="button-secondary"
                type="button"
                :disabled="sendingCommand || !canDispatchCommands"
                @click="handleSendCommand('read_plan')"
              >
                {{ sendingCommand && controlsForm.action === "read_plan" ? "Lecture..." : "Read plan" }}
              </button>
              <button
                class="button-secondary"
                type="button"
                :disabled="sendingCommand || !canDispatchCommands"
                @click="handleSendCommand('register_check')"
              >
                {{ sendingCommand && controlsForm.action === "register_check" ? "Lecture..." : "Register check %MW8120-%MW8578" }}
              </button>
              <button
                class="button-secondary button-monitor"
                type="button"
                :disabled="!canDispatchCommands"
                @click="openModbusMonitorTab"
              >
                Visualiser simulateur
              </button>
              <p v-if="!canDispatchCommands" class="helper-text">
                Le role courant doit avoir <code>inventory:scan</code> pour declencher ce write path.
              </p>
            </div>
          </form>
        </PanelCard>

        <PanelCard
          title="Preview / reply"
          :status="dispatchResult?.reply_payload?.status ? String(dispatchResult.reply_payload.status) : 'idle'"
          :status-tone="dispatchResult?.reply_payload?.status === 'ok' ? 'healthy' : dispatchResult ? 'warning' : 'neutral'"
          :accent-tone="dispatchResult?.reply_payload?.status === 'ok' ? 'healthy' : dispatchResult ? 'warning' : 'neutral'"
        >
          <p v-if="dispatchNotice" class="helper-text success-copy">{{ dispatchNotice }}</p>
          <p v-if="dispatchErrorMessage" class="helper-text error-copy">{{ dispatchErrorMessage }}</p>

          <div class="payload-shell">
            <div class="payload-header">
              <h3>{{ dispatchResult ? "Derniere commande envoyee" : "Payload commande" }}</h3>
              <StatusBadge :label="displayedCommandAction" tone="running" compact />
            </div>
            <pre class="payload-preview">{{ payloadPrettyPrint(displayedCommandPayload) }}</pre>
          </div>

          <div class="payload-shell">
            <div class="payload-header">
              <h3>Derniere reponse</h3>
              <StatusBadge
                :label="dispatchResult?.round_trip_ms ? `${dispatchResult.round_trip_ms} ms` : 'n/a'"
                :tone="dispatchResult ? 'neutral' : 'waiting'"
                compact
              />
            </div>
            <pre class="payload-preview reply-preview-scroll">{{ payloadPrettyPrint(dispatchResult?.reply_payload ?? { status: 'idle' }) }}</pre>
          </div>

          <div v-if="plannerReadReply" class="payload-shell">
            <div class="payload-header">
              <h3>Snapshot planificateur</h3>
              <StatusBadge
                :label="`CRC16 ${plannerReadReply.plannerCrc16 ?? 'n/a'}`"
                :tone="plannerReadReply.count > 0 ? 'healthy' : 'neutral'"
                compact
              />
            </div>
            <div class="planner-read-grid">
              <article class="planner-read-tile">
                <p class="muted-2 uppercase">Ordres</p>
                <strong>{{ plannerReadReply.count }}</strong>
              </article>
              <article class="planner-read-tile">
                <p class="muted-2 uppercase">Words</p>
                <strong>{{ plannerReadReply.plannerWordCount ?? "---" }}</strong>
              </article>
            </div>
            <div class="table-shell">
              <table class="orders-table planner-table">
                <thead>
                  <tr>
                    <th>Slot</th>
                    <th>Register</th>
                    <th>Order ID</th>
                    <th>Profil</th>
                    <th>Execution</th>
                    <th>C1-2</th>
                    <th>C1-3</th>
                    <th>C2-2</th>
                    <th>C2-3</th>
                    <th>C3-1</th>
                    <th>CRC16</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="order in plannerReadReply.orders" :key="`${order.registerBase}-${order.id}`">
                    <td class="mono">{{ order.slotIndex ?? "n/a" }}</td>
                    <td class="mono">%MW{{ order.registerBase ?? "?" }}</td>
                    <td class="mono">{{ order.id ?? "n/a" }}</td>
                    <td>{{ order.profileLabel }}</td>
                    <td>{{ order.executeAt }}</td>
                    <td>{{ order.powerLimitKw ?? "n/a" }} kW</td>
                    <td>{{ order.elecPressureBar != null ? `${order.elecPressureBar} bar` : "n/a" }}</td>
                    <td>{{ order.metType ?? "n/a" }}</td>
                    <td>{{ order.metPressureBar != null ? `${order.metPressureBar} bar` : "n/a" }}</td>
                    <td>{{ order.secoursEnabled == null ? "n/a" : order.secoursEnabled ? 1 : 0 }}</td>
                    <td class="mono">{{ order.crc16 ?? "n/a" }}</td>
                  </tr>
                  <tr v-if="plannerReadReply.orders.length === 0">
                    <td colspan="11" class="muted-copy">Le planificateur est vide.</td>
                  </tr>
                </tbody>
              </table>
            </div>

          </div>

          <div class="payload-shell">
            <div class="payload-header">
              <h3>Execution log</h3>
              <div class="log-actions">
                <StatusBadge :label="`${executionLog.length} lignes`" :tone="executionLog.length ? 'neutral' : 'waiting'" compact />
                <button class="button-secondary button-compact" type="button" :disabled="executionLog.length === 0" @click="clearExecutionLog">
                  Clear logs
                </button>
              </div>
            </div>
            <div class="execution-log">
              <div v-for="entry in executionLog" :key="entry.id" class="execution-log-line" :data-tone="entry.tone">
                <span class="mono execution-log-time">[{{ formatDateTime(entry.loggedAt) }}]</span>
                <span>{{ entry.message }}</span>
              </div>
              <p v-if="executionLog.length === 0" class="helper-text">
                Le journal d'execution se remplira au premier ping ou au premier ordre envoye.
              </p>
            </div>
          </div>
        </PanelCard>
      </div>

      <PanelCard
        title="Verification permanente des lots registres"
        :status="`${plannerRegisterVerification.matchedRows}/${plannerRegisterVerification.knownRows} champs OK`"
        :status-tone="plannerRegisterVerification.statusTone"
        accent-tone="running"
      >
        <div class="planner-verification-shell">
          <p class="helper-text">
            Dernier upsert envoye:
            <span class="mono">ID {{ plannerRegisterVerification.sent?.orderId ?? "aucun" }}</span>.
            Slot relu:
            <span class="mono">
              {{
                plannerRegisterVerification.matchedOrder?.slotIndex != null
                  ? `#${plannerRegisterVerification.matchedOrder.slotIndex} @ %MW${plannerRegisterVerification.matchedOrder.registerBase}`
                  : "aucun slot relu"
              }}
            </span>.
          </p>
          <p v-if="!plannerRegisterVerification.sent" class="helper-text">
            Les lignes restent fixes; la colonne Envoye se remplira au prochain Upsert.
          </p>
          <p v-else-if="!plannerReadReply" class="helper-text warning-copy">
            Upsert capture. Cliquez Read plan pour remplir la colonne Relu Modbus.
          </p>
          <p v-else-if="!plannerRegisterVerification.matchedOrder" class="helper-text warning-copy">
            Aucun slot ne porte encore cet Order ID. Si l'ordre vient d'etre execute ou supprime, c'est normal; sinon relancez Read plan apres quelques secondes.
          </p>
          <div class="table-shell">
            <table class="orders-table verification-table">
              <thead>
                <tr>
                  <th>Champ</th>
                  <th>Registres</th>
                  <th>Envoye</th>
                  <th>Relu Modbus</th>
                  <th>Etat</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in plannerRegisterVerification.rows" :key="row.label">
                  <td>{{ row.label }}</td>
                  <td class="mono">{{ row.registers }}</td>
                  <td class="mono">{{ row.sent }}</td>
                  <td class="mono">{{ row.received }}</td>
                  <td>
                    <StatusBadge
                      :label="row.matched === null ? 'n/a' : row.matched ? 'OK' : 'Mismatch'"
                      :tone="row.tone"
                      compact
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <details class="raw-register-details" open>
            <summary>
              Lot brut fixe 46 mots:
              {{ plannerRegisterVerification.knownWords > 0
                ? `${plannerRegisterVerification.matchedWords}/${plannerRegisterVerification.knownWords} mots identiques`
                : "en attente de valeurs envoyees et relues" }}
            </summary>
            <div class="table-shell raw-word-table-shell">
              <table class="orders-table raw-word-table">
                <thead>
                  <tr>
                    <th>Registre</th>
                    <th>Offset</th>
                    <th>Role</th>
                    <th>Envoye</th>
                    <th>Relu Modbus</th>
                    <th>Etat</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(word, index) in plannerRegisterVerification.wordRows"
                    :key="word.register"
                    :data-match="word.matched === null ? 'unknown' : word.matched ? 'ok' : 'mismatch'"
                  >
                    <td class="mono">{{ word.register }}</td>
                    <td class="mono">+{{ index }}</td>
                    <td>{{ word.label }}</td>
                    <td class="mono">{{ word.sent ?? "n/a" }}</td>
                    <td class="mono">{{ word.received ?? "n/a" }}</td>
                    <td>
                      <StatusBadge
                        :label="word.matched === null ? 'n/a' : word.matched ? 'OK' : 'Mismatch'"
                        :tone="verificationTone(word.matched)"
                        compact
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>

          <details class="raw-register-details" open>
            <summary>
              Lecture brute complete %MW8120-%MW8578:
              {{ plannerRegisterCheckReply
                ? `${plannerRegisterCheckReply.wordCount} registres relus`
                : "cliquez Register check pour remplir cette table" }}
            </summary>
            <template v-if="plannerRegisterCheckReply">
              <div class="register-check-slot-strip">
                <article
                  v-for="slot in plannerRegisterCheckReply.slots"
                  :key="`slot-${slot.slotIndex}`"
                  class="register-check-slot-card"
                  :data-active="slot.orderId !== 0 ? 'yes' : 'no'"
                >
                  <span class="mono">Slot {{ slot.slotIndex }} / %MW{{ slot.baseRegister }}</span>
                  <strong>{{ slot.orderId === 0 ? "vide" : `ID ${slot.orderId}` }}</strong>
                  <small>{{ slot.nonZeroCount }} valeurs non nulles</small>
                </article>
              </div>
              <div class="table-shell planner-register-check-shell">
                <table class="orders-table planner-register-check-table">
                  <thead>
                    <tr>
                      <th>Lot</th>
                      <th>Registre</th>
                      <th>Offset</th>
                      <th>Champ</th>
                      <th>Valeur ecrite actuelle</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in plannerRegisterCheckReply.rows"
                      :key="row.register"
                      :data-active="row.value !== 0 ? 'yes' : 'no'"
                    >
                      <td class="mono">slot {{ row.slotIndex }}</td>
                      <td class="mono">{{ row.registerLabel }}</td>
                      <td class="mono">+{{ row.slotOffset }}</td>
                      <td>{{ row.field }}</td>
                      <td class="mono">{{ row.value }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
            <p v-else class="helper-text">
              Cette table lit directement la plage officielle du planificateur. Utilise le bouton
              <strong>Register check %MW8120-%MW8578</strong> pour afficher les valeurs actuellement ecrites dans chaque registre.
            </p>
          </details>
        </div>
      </PanelCard>
    </section>
  </section>
</template>

<style scoped>
.section-shell {
  display: grid;
  gap: 1rem;
  padding: 1.45rem 1.55rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(12, 14, 16, 0.96), rgba(8, 9, 10, 0.94));
}

.section-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 1rem;
}

.orders-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: end;
}

.controls-shell {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  align-items: end;
  justify-content: flex-end;
}

.controls-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 1.25rem;
}

.operation-mode-card {
  border-color: rgba(92, 211, 148, 0.22);
  background:
    linear-gradient(135deg, rgba(29, 101, 70, 0.16), transparent 44%),
    rgba(255, 255, 255, 0.025);
}

.operation-mode-card[data-mode="real"] {
  border-color: rgba(255, 154, 139, 0.42);
  background:
    linear-gradient(135deg, rgba(123, 38, 33, 0.34), transparent 46%),
    rgba(255, 255, 255, 0.03);
  box-shadow: 0 0 0 1px rgba(255, 154, 139, 0.08), 0 18px 42px rgba(123, 38, 33, 0.16);
}

.operation-mode-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem;
}

.operation-mode-tile {
  display: grid;
  gap: 0.45rem;
  padding: 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(6, 7, 8, 0.42);
}

.operation-mode-tile p,
.operation-mode-tile strong,
.operation-mode-tile span {
  margin: 0;
}

.operation-mode-tile strong {
  color: var(--text);
  font-size: 1.05rem;
}

.operation-mode-tile span {
  color: var(--muted);
}

.execution-utility-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.25rem;
}

.register-reference-shell {
  display: grid;
  gap: 1rem;
  padding: 1.15rem;
  border-radius: var(--radius-xl);
  border: 1px solid rgba(212, 166, 62, 0.24);
  background:
    linear-gradient(135deg, rgba(95, 74, 20, 0.2), transparent 38%),
    rgba(255, 255, 255, 0.025);
}

.register-reference-shell summary {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 1rem;
  cursor: pointer;
  list-style: none;
}

.register-reference-shell summary::-webkit-details-marker {
  display: none;
}

.register-reference-shell summary::after {
  content: "+";
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 2rem;
  height: 2rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  color: var(--gold);
}

.register-reference-shell[open] summary::after {
  content: "-";
}

.register-reference-shell summary h2,
.register-reference-shell summary p {
  margin: 0;
}

.register-reference-grid {
  display: grid;
  gap: 1rem;
}

.register-guide-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.85rem;
}

.register-guide-step {
  display: grid;
  gap: 0.65rem;
  padding: 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(6, 7, 8, 0.5);
}

.register-guide-step h3,
.register-guide-step p {
  margin: 0;
}

.register-guide-step[data-tone="healthy"],
.register-guide-step[data-tone="pass"] {
  border-color: rgba(92, 211, 148, 0.28);
}

.register-guide-step[data-tone="warning"] {
  border-color: rgba(212, 166, 62, 0.28);
}

.register-guide-expected {
  color: var(--green);
  font-size: 0.86rem;
}

.register-reference-card {
  display: grid;
  gap: 0.85rem;
  padding: 1rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(6, 7, 8, 0.52);
}

.register-reference-card h3,
.register-reference-card p {
  margin: 0;
}

.register-table-shell {
  overflow-x: auto;
}

.register-reference-table td,
.register-reference-table th {
  min-width: 10rem;
}

.execution-metric-grid {
  margin-bottom: 0.15rem;
}

.watchdog-form,
.quick-tools {
  display: grid;
  gap: 0.9rem;
}

.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.watchdog-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.watchdog-tile {
  padding: 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
}

.watchdog-tile p,
.watchdog-tile strong {
  margin: 0;
}

.watchdog-tile strong {
  display: block;
  margin-top: 0.45rem;
  font-size: 1.45rem;
}

.control-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.field {
  display: grid;
  gap: 0.4rem;
}

.field span {
  color: var(--muted);
  font-size: 0.9rem;
}

.field select {
  min-width: 9rem;
  min-height: 2.85rem;
  padding: 0.75rem 0.95rem;
  border-radius: 1rem;
  border: 1px solid rgba(122, 168, 255, 0.34);
  background:
    linear-gradient(135deg, rgba(122, 168, 255, 0.16), transparent 58%),
    #171c23;
  color: var(--text);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}

.field select option {
  color: var(--text);
  background: #141820;
}

.field select option:checked {
  color: #050607;
  background: var(--green);
}

.field select:disabled {
  color: var(--muted-2);
  border-color: rgba(255, 255, 255, 0.12);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.05), transparent 58%),
    rgba(255, 255, 255, 0.05);
}

.field input,
.field textarea {
  min-height: 2.85rem;
  padding: 0.75rem 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}

.field textarea {
  resize: vertical;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
  line-height: 1.45;
}

.field-wide {
  grid-column: 1 / -1;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1.3rem;
}

.notice-shell {
  padding: 0.95rem 1.15rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
}

.notice-warning {
  border-color: rgba(212, 166, 62, 0.28);
  color: var(--gold);
  background: rgba(95, 74, 20, 0.22);
}

.notice-error {
  border-color: rgba(255, 154, 139, 0.28);
  color: var(--red-soft);
  background: rgba(123, 38, 33, 0.22);
}

.orders-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 0.9fr);
  gap: 1.25rem;
}

.consigne-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem;
}

.consigne-card {
  display: grid;
  gap: 0.7rem;
  padding: 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
}

.consigne-card h3 {
  margin: 0;
  color: var(--text);
}

.planner-preview-grid,
.planner-read-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.planner-preview-card,
.planner-read-tile {
  padding: 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
}

.planner-preview-card p,
.planner-preview-card h3,
.planner-read-tile p,
.planner-read-tile strong {
  margin: 0;
}

.planner-read-tile strong {
  display: block;
  margin-top: 0.45rem;
  font-size: 1.45rem;
}

.error-test-shell {
  display: grid;
  gap: 0.85rem;
  padding: 1rem;
  border-radius: 1rem;
  border: 1px solid rgba(212, 166, 62, 0.28);
  background:
    linear-gradient(135deg, rgba(95, 74, 20, 0.18), transparent 60%),
    rgba(255, 255, 255, 0.025);
}

.badge-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.45rem;
}

.safety-standby-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.85rem;
  align-items: center;
  padding: 0.95rem;
  border-radius: 1rem;
  border: 1px solid rgba(92, 211, 148, 0.22);
  background: rgba(92, 211, 148, 0.07);
}

.safety-standby-panel[data-active="no"] {
  border-color: rgba(255, 154, 139, 0.36);
  background:
    linear-gradient(135deg, rgba(255, 154, 139, 0.12), transparent 70%),
    rgba(255, 255, 255, 0.03);
}

.safety-standby-panel h3,
.safety-standby-panel p {
  margin: 0;
}

.manual-test-grid {
  display: grid;
  grid-template-columns: minmax(12rem, 0.85fr) minmax(0, 1.15fr);
  gap: 0.85rem;
}

.manual-scenario-card {
  padding: 0.85rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.035);
}

.manual-scenario-card p,
.manual-scenario-card strong {
  margin: 0;
}

.manual-scenario-card strong {
  display: block;
  margin: 0.3rem 0;
  color: var(--gold);
}

.manual-payload-editor {
  min-height: 16rem;
  max-height: 32rem;
  overflow: auto;
  white-space: pre;
}

.planner-table td,
.planner-table th {
  white-space: nowrap;
}

.planner-verification-shell {
  display: grid;
  gap: 0.75rem;
  padding-top: 0.4rem;
}

.verification-table td,
.verification-table th {
  white-space: nowrap;
}

.raw-register-details {
  border: 1px solid var(--line);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.025);
}

.raw-register-details summary {
  cursor: pointer;
  padding: 0.85rem 1rem;
  color: var(--text);
  font-weight: 700;
}

.raw-word-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(10.5rem, 1fr));
  gap: 0.55rem;
  padding: 0 1rem 1rem;
}

.raw-word-chip {
  display: grid;
  gap: 0.25rem;
  padding: 0.65rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.035);
  font-size: 0.82rem;
}

.raw-word-chip[data-match="ok"] {
  border-color: rgba(92, 211, 148, 0.28);
}

.raw-word-chip[data-match="mismatch"] {
  border-color: rgba(255, 154, 139, 0.38);
  background: rgba(123, 38, 33, 0.18);
}

.raw-word-table-shell {
  max-height: 30rem;
  overflow: auto;
}

.raw-word-table td,
.raw-word-table th {
  white-space: nowrap;
}

.raw-word-table tr[data-match="ok"] td {
  background: rgba(92, 211, 148, 0.035);
}

.raw-word-table tr[data-match="mismatch"] td {
  background: rgba(123, 38, 33, 0.16);
}

.register-check-slot-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: 0.6rem;
  padding: 0 1rem 1rem;
}

.register-check-slot-card {
  display: grid;
  gap: 0.25rem;
  padding: 0.7rem;
  border-radius: 0.85rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
}

.register-check-slot-card[data-active="yes"] {
  border-color: rgba(92, 211, 148, 0.32);
  background: rgba(29, 101, 70, 0.12);
}

.register-check-slot-card span,
.register-check-slot-card strong,
.register-check-slot-card small {
  margin: 0;
}

.register-check-slot-card small {
  color: var(--muted);
}

.planner-register-check-shell {
  max-height: 34rem;
  overflow: auto;
}

.planner-register-check-table td,
.planner-register-check-table th {
  white-space: nowrap;
}

.planner-register-check-table tr[data-active="yes"] td {
  background: rgba(92, 211, 148, 0.035);
}

.raw-register-label {
  color: var(--accent);
}

.table-shell {
  overflow: hidden;
  border-radius: 1rem;
  border: 1px solid var(--line);
}

.orders-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}

.orders-table thead th {
  padding: 0.9rem 1rem;
  text-align: left;
  color: var(--muted);
  border-bottom: 1px solid var(--line);
}

.orders-table tbody td {
  padding: 0.9rem 1rem;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}

.orders-table tbody tr:last-child td {
  border-bottom: none;
}

.orders-table tbody tr {
  cursor: pointer;
  transition: background 150ms ease;
}

.orders-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.035);
}

.row-selected {
  background: rgba(82, 117, 176, 0.12);
}

.detail-grid {
  display: grid;
  gap: 0.55rem;
}

.detail-grid p {
  margin: 0;
}

.payload-shell {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.payload-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.payload-header h3 {
  margin: 0;
  color: var(--text);
  font-size: 1rem;
}

.fifo-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.85rem;
}

.fifo-toolbar .helper-text {
  margin: 0;
}

.payload-preview {
  margin: 0;
  padding: 1rem;
  min-height: 18rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(6, 7, 8, 0.92);
  color: var(--text);
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.reply-preview-scroll {
  min-height: 14rem;
  max-height: 28rem;
}

.execution-log {
  display: grid;
  gap: 0.55rem;
  margin: 0;
  padding: 1rem;
  min-height: 12rem;
  max-height: 18rem;
  overflow: auto;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(6, 7, 8, 0.92);
}

.execution-log-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  color: var(--text);
}

.execution-log-line[data-tone="healthy"] {
  color: var(--green);
}

.execution-log-line[data-tone="warning"] {
  color: var(--gold);
}

.execution-log-line[data-tone="critical"] {
  color: var(--red-soft);
}

.execution-log-time {
  color: var(--muted);
}

.log-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.65rem;
}

.button-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.85rem;
  padding: 0.75rem 1rem;
  border-radius: 999px;
  font-weight: 600;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}

.button-secondary:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.button-compact {
  min-height: 2rem;
  padding: 0.45rem 0.75rem;
  font-size: 0.86rem;
}

.button-warning {
  border-color: rgba(212, 166, 62, 0.28);
  color: var(--gold);
}

.button-danger {
  border-color: rgba(255, 154, 139, 0.28);
  color: var(--red-soft);
}

.button-monitor {
  border-color: rgba(122, 168, 255, 0.28);
  color: var(--blue);
  background:
    linear-gradient(135deg, rgba(46, 84, 150, 0.2), transparent 58%),
    rgba(255, 255, 255, 0.04);
}

.action-row {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.85rem;
}

.action-row-compact {
  gap: 0.6rem;
}

.helper-text,
.muted-copy {
  color: var(--muted);
}

.success-copy {
  color: var(--green);
}

.warning-copy {
  color: var(--gold);
}

.error-copy {
  color: var(--red-soft);
}

.mono {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
}

@media (max-width: 1100px) {
  .orders-heading,
  .orders-layout,
  .execution-utility-grid,
  .operation-mode-grid,
  .controls-layout,
  .consigne-grid,
  .register-guide-strip,
  .planner-preview-grid,
  .planner-read-grid,
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .controls-shell {
    justify-content: stretch;
  }
}
</style>
