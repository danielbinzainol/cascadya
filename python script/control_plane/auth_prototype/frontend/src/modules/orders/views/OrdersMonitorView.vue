<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { dispatchOrderCommand } from "@/api/orders";
import MetricCard from "@/components/ui/MetricCard.vue";
import PanelCard from "@/components/ui/PanelCard.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { useSessionStore } from "@/stores/session";
import type { BadgeTone, DashboardMetric } from "@/types/controlPlane";

const COMMAND_SUBJECT = "cascadya.routing.command";
const DEFAULT_ASSET = "cascadya-ipc-10-109";
const route = useRoute();
const session = useSessionStore();

const assetName = ref(typeof route.query.asset === "string" && route.query.asset ? route.query.asset : DEFAULT_ASSET);
const refreshIntervalMs = ref(1000);
const autoRefresh = ref(true);
const loading = ref(false);
const errorMessage = ref<string | null>(null);
const snapshot = ref<Record<string, unknown> | null>(null);
const lastRoundTripMs = ref<number | null>(null);
let pollHandle: number | null = null;

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function getRecord(parent: Record<string, unknown> | null, key: string) {
  return asRecord(parent?.[key]);
}

function getNumber(parent: Record<string, unknown> | null, key: string, fallback = 0) {
  const value = parent?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function getString(parent: Record<string, unknown> | null, key: string, fallback = "n/a") {
  const value = parent?.[key];
  return typeof value === "string" && value ? value : fallback;
}

function getBoolean(parent: Record<string, unknown> | null, key: string) {
  return parent?.[key] === true;
}

function getArray(parent: Record<string, unknown> | null, key: string) {
  const value = parent?.[key];
  return Array.isArray(value) ? value : [];
}

function formatClock(clock: Record<string, unknown>) {
  const year = String(getNumber(clock, "year")).padStart(4, "0");
  const month = String(getNumber(clock, "month")).padStart(2, "0");
  const day = String(getNumber(clock, "day")).padStart(2, "0");
  const hour = String(getNumber(clock, "hour")).padStart(2, "0");
  const minute = String(getNumber(clock, "minute")).padStart(2, "0");
  const second = String(getNumber(clock, "second")).padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

function formatNumber(value: number | null | undefined, digits = 1) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}

function buildDemoSnapshot(): Record<string, unknown> {
  return {
    status: "ok",
    action: "monitor_snapshot",
    timestamp: new Date().toISOString(),
    operation_mode: {
      mode: "simulation",
      label: "ENVIRONMENT: DIGITAL TWIN (SAFE)",
      target_host: "192.168.50.2",
      target_port: 502,
      telemetry_profile: "digital_twin",
      watchdog_strict: false,
    },
    plc_clock: {
      year: 2026,
      month: 4,
      day: 21,
      hour: 9,
      minute: 0,
      second: Math.floor(Date.now() / 1000) % 60,
    },
    plc_watchdog: Math.floor(Date.now() / 1000) % 65535,
    operation_status: { add: 0, delete: 0, reset: 0 },
    planner: {
      state: 0,
      state_text: "ok",
      crc16: 37460,
      crc16_calculated: 37460,
      crc16_matches: true,
      crc_state: 0,
      crc_state_text: "complete",
      queue_head_crc16: 0,
      count: 3,
      word_count: 460,
      slot_limit: 10,
      slot_stride: 46,
      slot_words: 46,
    },
    queue_head: {
      id: 9201,
      execute_at: "2026-04-21 09:01:30",
      mode_profile_label: "5.5.*",
      elec_pressure_bar: 5.3,
      power_limit_kw: 40,
      met_type: 2,
      met_pressure_bar: 5.3,
      secours_enabled: false,
      slot_index: 0,
      register_base: 8120,
      crc16: 12101,
    },
    queue_head_raw: [0, 9201, 21, 4, 2026, 9, 1, 30],
    orders: [
      {
        id: 9201,
        execute_at: "2026-04-21 09:01:30",
        mode_profile_label: "5.5.*",
        elec_pressure_bar: 5.3,
        power_limit_kw: 40,
        met_type: 2,
        met_pressure_bar: 5.3,
        secours_enabled: false,
        slot_index: 0,
        register_base: 8120,
        crc16: 12101,
      },
      {
        id: 9202,
        execute_at: "2026-04-21 09:02:00",
        mode_profile_label: "5.5.*",
        elec_pressure_bar: 5.3,
        power_limit_kw: 40,
        met_type: 2,
        met_pressure_bar: 5.3,
        secours_enabled: false,
        slot_index: 1,
        register_base: 8166,
        crc16: 22402,
      },
      {
        id: 9203,
        execute_at: "2026-04-21 09:03:00",
        mode_profile_label: "2.5.*",
        elec_pressure_bar: 5.3,
        power_limit_kw: 40,
        met_type: 2,
        met_pressure_bar: 5.3,
        secours_enabled: true,
        slot_index: 2,
        register_base: 8212,
        crc16: 32703,
      },
    ],
    steam_header: {
      pressure_bar: 5.3,
      pressure_raw: 53,
      pressure_label: "PT01_MESURE simulated mirror",
      pressure_register_label: "%MW9588",
      demand_kw: 820,
      demand_label: "Factory Demand",
      demand_unit: "kW",
      demand_register_label: "%MW9001",
    },
    plc_health: {
      fault: false,
      fault_count: 0,
      alarm: false,
      alarm_count: 0,
      registers: {
        fault: "%MW9457.0 -> real %MW257.0",
        fault_count: "%MW9458 -> real %MW258",
        alarm: "%MW9459.0 -> real %MW259.0",
        alarm_count: "%MW9460 -> real %MW260",
      },
    },
    pressure_sensor: {
      error: false,
      error_register_label: "%MW9590.0",
      percent: 42.4,
      percent_register_label: "%MW9592",
    },
    pressure_regulation: {
      thermo_running: true,
      mini_technique: false,
      limiter_position: false,
      mode: "auto",
      mode_auto: true,
      mode_manual: false,
      mode_disabled: false,
      load_pct: 42,
      load_register_label: "%MW9712",
      setpoint_bar: 5.3,
      setpoint_register_label: "%MW9714",
      boost: false,
      boost_register_label: "%MW9716.0",
    },
    heater_feedback: {
      load_pct: 41.5,
      load_register_label: "%MW9774",
      error: false,
      error_register_label: "%MW9776.0",
    },
    runtime: {
      active_strategy_code: 3,
      active_strategy: "C3",
      active_order_id: 9201,
      target_pressure_bar: 5.3,
      active_stages: 1,
      register_base: 9070,
    },
    ibcs: {
      ibc1: { state: 3, state_label: "RUNNING", load_pct: 100, target_pct: 100, register_base: 9010 },
      ibc2: { state: 3, state_label: "RUNNING", load_pct: 62, target_pct: 0, register_base: 9020 },
      ibc3: { state: 3, state_label: "RUNNING", load_pct: 45, target_pct: 100, register_base: 9030 },
    },
  };
}

const plcClock = computed(() => getRecord(snapshot.value, "plc_clock"));
const operationStatus = computed(() => getRecord(snapshot.value, "operation_status"));
const planner = computed(() => getRecord(snapshot.value, "planner"));
const queueHead = computed(() => {
  const raw = snapshot.value?.queue_head;
  return raw === null ? null : asRecord(raw);
});
const steamHeader = computed(() => getRecord(snapshot.value, "steam_header"));
const plcHealth = computed(() => getRecord(snapshot.value, "plc_health"));
const pressureSensor = computed(() => getRecord(snapshot.value, "pressure_sensor"));
const pressureRegulation = computed(() => getRecord(snapshot.value, "pressure_regulation"));
const heaterFeedback = computed(() => getRecord(snapshot.value, "heater_feedback"));
const runtime = computed(() => getRecord(snapshot.value, "runtime"));
const ibcs = computed(() => getRecord(snapshot.value, "ibcs"));
const queueHeadRaw = computed(() => {
  const value = snapshot.value?.queue_head_raw;
  return Array.isArray(value) ? value.map((item) => Number(item)) : [];
});
const operationMode = computed(() => getRecord(snapshot.value, "operation_mode"));
const operationModeTone = computed<BadgeTone>(() => (getString(operationMode.value, "mode") === "real" ? "critical" : "healthy"));
const monitorTitle = computed(() => (getString(operationMode.value, "mode") === "real" ? "LCI LIVE MONITOR" : "DIGITAL TWIN MONITOR"));
const pressureDisplayLabel = computed(() => getString(steamHeader.value, "pressure_label", "Steam Header Pressure"));
const pressureRegisterLabel = computed(() => getString(steamHeader.value, "pressure_register_label", "%MW9000"));
const demandDisplayLabel = computed(() => getString(steamHeader.value, "demand_label", "Factory Demand"));
const demandDisplayUnit = computed(() => getString(steamHeader.value, "demand_unit", "kW"));
const demandRegisterLabel = computed(() => getString(steamHeader.value, "demand_register_label", "%MW9001"));
const plcHealthRegisters = computed(() => getRecord(plcHealth.value, "registers"));
const plannerSlotLimit = computed(() => getNumber(planner.value, "slot_limit", 10));
const plannerOrders = computed(() =>
  getArray(snapshot.value, "orders")
    .filter((value): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value))
    .map((order) => ({
      id: getNumber(order, "id"),
      executeAt: getString(order, "execute_at"),
      slotIndex: getNumber(order, "slot_index"),
      registerBase: getNumber(order, "register_base"),
      profileLabel: getString(order, "mode_profile_label"),
      powerLimitKw: getNumber(order, "power_limit_kw"),
      elecPressureBar: getNumber(order, "elec_pressure_bar"),
      metType: getNumber(order, "met_type"),
      metPressureBar: getNumber(order, "met_pressure_bar"),
      secoursEnabled: getBoolean(order, "secours_enabled"),
      crc16: getNumber(order, "crc16"),
    })),
);
const plannerVisibleCount = computed(() => plannerOrders.value.length);
const activeOrderId = computed(() => getNumber(runtime.value, "active_order_id"));
const nextOrder = computed(() => plannerOrders.value[0] ?? null);

function orderLifecycle(order: { id: number; slotIndex: number }) {
  if (order.id > 0 && order.id === activeOrderId.value) {
    return "ACTIVE";
  }
  if (order.slotIndex === 0) {
    return "NEXT";
  }
  return "PENDING";
}

function orderLifecycleTone(order: { id: number; slotIndex: number }): BadgeTone {
  const lifecycle = orderLifecycle(order);
  if (lifecycle === "ACTIVE") {
    return "healthy";
  }
  if (lifecycle === "NEXT") {
    return "running";
  }
  return "pending";
}

const monitorMetrics = computed<DashboardMetric[]>(() => [
  {
    title: "Pression vapeur",
    value: `${formatNumber(getNumber(steamHeader.value, "pressure_bar"), 1)} bar`,
    subtitle: pressureRegisterLabel.value,
    tone: getNumber(steamHeader.value, "pressure_bar") > 0 ? "healthy" : "warning",
  },
  {
    title: "Charge thermo",
    value: `${formatNumber(getNumber(pressureRegulation.value, "load_pct"), 1)}%`,
    subtitle: getString(pressureRegulation.value, "load_register_label", "%MW512"),
    tone: getNumber(pressureRegulation.value, "load_pct") > 0 ? "running" : "neutral",
  },
  {
    title: "Sante PLC",
    value: getBoolean(plcHealth.value, "fault") || getBoolean(plcHealth.value, "alarm") ? "A verifier" : "OK",
    subtitle: `D=${getNumber(plcHealth.value, "fault_count")} A=${getNumber(plcHealth.value, "alarm_count")}`,
    tone: getBoolean(plcHealth.value, "fault") ? "critical" : getBoolean(plcHealth.value, "alarm") ? "warning" : "healthy",
  },
  {
    title: "Strategie active",
    value: getString(runtime.value, "active_strategy", "NONE"),
    subtitle: `order_id=${getNumber(runtime.value, "active_order_id")}`,
    tone: getNumber(runtime.value, "active_order_id") > 0 ? "running" : "neutral",
  },
  {
    title: "Queue head",
    value: queueHead.value ? String(getNumber(queueHead.value, "id")) : "vide",
    subtitle: nextOrder.value ? `slot ${nextOrder.value.slotIndex} / %MW${nextOrder.value.registerBase}` : "%MW8120 slot 0",
    tone: queueHead.value ? "active" : "neutral",
  },
  {
    title: "Ordres pending",
    value: String(plannerOrders.value.length),
    subtitle: "slots %MW8120 + n*46",
    tone: plannerOrders.value.length > 0 ? "running" : "neutral",
  },
  {
    title: "CRC plan",
    value: String(getNumber(planner.value, "crc16")),
    subtitle: getBoolean(planner.value, "crc16_matches")
      ? `%MW8101 matches / ${getString(planner.value, "crc_state_text")}`
      : `%MW8101 mismatch / ${getString(planner.value, "crc_state_text")}`,
    tone: getNumber(planner.value, "crc_state") === 0 && getBoolean(planner.value, "crc16_matches") ? "pass" : "warning",
  },
]);

function boolText(value: boolean, trueLabel = "1", falseLabel = "0") {
  return value ? trueLabel : falseLabel;
}

function okWhenFalseTone(value: boolean): BadgeTone {
  return value ? "critical" : "healthy";
}

function onOffTone(value: boolean): BadgeTone {
  return value ? "running" : "neutral";
}

const ibcRows = computed(() =>
  ["ibc1", "ibc2", "ibc3"].map((key) => {
    const row = getRecord(ibcs.value, key);
    return {
      key,
      label: key.toUpperCase(),
      state: getString(row, "state_label", "UNKNOWN"),
      load: getNumber(row, "load_pct"),
      target: getNumber(row, "target_pct"),
      registerBase: getNumber(row, "register_base"),
    };
  }),
);

async function loadSnapshot() {
  loading.value = true;
  errorMessage.value = null;

  try {
    if (session.demoModeEnabled) {
      snapshot.value = buildDemoSnapshot();
      lastRoundTripMs.value = 8;
      return;
    }

    const result = await dispatchOrderCommand({
      subject: COMMAND_SUBJECT,
      timeout_seconds: 5,
      command_payload: {
        action: "monitor_snapshot",
        asset_name: assetName.value.trim() || DEFAULT_ASSET,
      },
    });

    snapshot.value = result.reply_payload;
    lastRoundTripMs.value = result.round_trip_ms;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "Erreur inconnue pendant la lecture du monitor.";
  } finally {
    loading.value = false;
  }
}

function stopPolling() {
  if (pollHandle !== null) {
    window.clearInterval(pollHandle);
    pollHandle = null;
  }
}

function restartPolling() {
  stopPolling();
  if (!autoRefresh.value || refreshIntervalMs.value <= 0) {
    return;
  }
  pollHandle = window.setInterval(() => {
    void loadSnapshot();
  }, refreshIntervalMs.value);
}

function statusTone(value: number): BadgeTone {
  return value === 0 ? "healthy" : value === 8 ? "warning" : "critical";
}

watch(
  () => [autoRefresh.value, refreshIntervalMs.value, assetName.value],
  () => {
    void loadSnapshot();
    restartPolling();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<template>
  <section class="monitor-page">
    <header class="monitor-hero">
      <div>
        <p class="muted-2 uppercase">Digital twin live monitor</p>
        <h1>Visualisation simulateur Modbus</h1>
        <p class="helper-text">
          Vue web du monitor Rev02: elle lit le simulateur via le gateway IPC et se rafraichit pendant que les ordres
          sont envoyes depuis l'autre onglet.
        </p>
      </div>

      <div class="monitor-controls">
        <label class="field">
          <span>IPC cible</span>
          <input v-model="assetName" type="text" />
        </label>
        <label class="field">
          <span>Refresh</span>
          <select v-model.number="refreshIntervalMs">
            <option :value="500">0.5 s</option>
            <option :value="1000">1 s</option>
            <option :value="2000">2 s</option>
            <option :value="5000">5 s</option>
          </select>
        </label>
        <button class="button-secondary" type="button" @click="autoRefresh = !autoRefresh">
          {{ autoRefresh ? "Pause" : "Reprendre" }}
        </button>
        <button class="button-secondary" type="button" :disabled="loading" @click="loadSnapshot">
          {{ loading ? "Lecture..." : "Lire maintenant" }}
        </button>
      </div>
    </header>

    <section v-if="errorMessage" class="notice-shell notice-error">
      {{ errorMessage }}
    </section>

    <section class="monitor-status-line">
      <StatusBadge :label="snapshot ? 'monitor online' : 'waiting snapshot'" :tone="snapshot ? 'healthy' : 'waiting'" compact />
      <StatusBadge
        :label="getString(operationMode, 'label', 'ENVIRONMENT: DIGITAL TWIN (SAFE)')"
        :tone="operationModeTone"
        compact
      />
      <StatusBadge :label="`SBC ${formatClock(plcClock)}`" tone="neutral" compact />
      <StatusBadge :label="`WD %MW256=${getNumber(snapshot, 'plc_watchdog')}`" tone="running" compact />
      <StatusBadge :label="lastRoundTripMs != null ? `${lastRoundTripMs} ms` : 'RTT n/a'" tone="neutral" compact />
    </section>

    <section class="metric-grid">
      <MetricCard
        v-for="metric in monitorMetrics"
        :key="metric.title"
        :title="metric.title"
        :value="metric.value"
        :subtitle="metric.subtitle"
        :tone="metric.tone"
      />
    </section>

    <section class="real-signal-grid">
      <PanelCard title="Sante automate Rev02" status="sim +9200 / reel natif" status-tone="healthy" accent-tone="healthy">
        <div class="signal-list">
          <div class="signal-row">
            <span>Defaut automate</span>
            <StatusBadge
              :label="`${getString(plcHealthRegisters, 'fault', '%MW257.0')}=${boolText(getBoolean(plcHealth, 'fault'))}`"
              :tone="okWhenFalseTone(getBoolean(plcHealth, 'fault'))"
              compact
            />
          </div>
          <div class="signal-row">
            <span>Nombre defauts</span>
            <strong class="mono">{{ getNumber(plcHealth, "fault_count") }}</strong>
          </div>
          <div class="signal-row">
            <span>Alarme automate</span>
            <StatusBadge
              :label="`${getString(plcHealthRegisters, 'alarm', '%MW259.0')}=${boolText(getBoolean(plcHealth, 'alarm'))}`"
              :tone="getBoolean(plcHealth, 'alarm') ? 'warning' : 'healthy'"
              compact
            />
          </div>
          <div class="signal-row">
            <span>Nombre alarmes</span>
            <strong class="mono">{{ getNumber(plcHealth, "alarm_count") }}</strong>
          </div>
        </div>
      </PanelCard>

      <PanelCard title="Capteur pression vapeur" status="PT01 sim -> reel" status-tone="running" accent-tone="running">
        <div class="signal-list">
          <div class="signal-row">
            <span>Mesure</span>
            <strong>{{ formatNumber(getNumber(steamHeader, "pressure_bar"), 2) }} bar <small>{{ pressureRegisterLabel }}</small></strong>
          </div>
          <div class="signal-row">
            <span>Erreur sonde</span>
            <StatusBadge
              :label="`${getString(pressureSensor, 'error_register_label', '%MW390.0')}=${boolText(getBoolean(pressureSensor, 'error'))}`"
              :tone="okWhenFalseTone(getBoolean(pressureSensor, 'error'))"
              compact
            />
          </div>
          <div class="signal-row">
            <span>Mesure % optionnelle</span>
            <strong>{{ formatNumber(getNumber(pressureSensor, "percent"), 1) }}% <small>{{ getString(pressureSensor, "percent_register_label", "%MW392") }}</small></strong>
          </div>
        </div>
      </PanelCard>

      <PanelCard title="Thermoplongeur / regulation" status="%MW508-%MW516 / %MW574" status-tone="running" accent-tone="running">
        <div class="signal-list">
          <div class="signal-row">
            <span>Etat thermoplongeur</span>
            <StatusBadge
              :label="`%MW508.0=${boolText(getBoolean(pressureRegulation, 'thermo_running'), 'marche', 'arret')}`"
              :tone="onOffTone(getBoolean(pressureRegulation, 'thermo_running'))"
              compact
            />
          </div>
          <div class="signal-row">
            <span>Mode RP08</span>
            <strong class="mono">{{ getString(pressureRegulation, "mode", "n/a") }}</strong>
          </div>
          <div class="signal-row">
            <span>Charge commande</span>
            <strong>{{ formatNumber(getNumber(pressureRegulation, "load_pct"), 1) }}% <small>{{ getString(pressureRegulation, "load_register_label", "%MW512") }}</small></strong>
          </div>
          <div class="signal-row">
            <span>Consigne pression</span>
            <strong>{{ formatNumber(getNumber(pressureRegulation, "setpoint_bar"), 2) }} bar <small>{{ getString(pressureRegulation, "setpoint_register_label", "%MW514") }}</small></strong>
          </div>
          <div class="signal-row">
            <span>Boost / limiteur / mini</span>
            <div class="signal-badges">
              <StatusBadge :label="`boost=${boolText(getBoolean(pressureRegulation, 'boost'))}`" :tone="onOffTone(getBoolean(pressureRegulation, 'boost'))" compact />
              <StatusBadge :label="`limiteur=${boolText(getBoolean(pressureRegulation, 'limiter_position'))}`" :tone="onOffTone(getBoolean(pressureRegulation, 'limiter_position'))" compact />
              <StatusBadge :label="`mini=${boolText(getBoolean(pressureRegulation, 'mini_technique'))}`" :tone="onOffTone(getBoolean(pressureRegulation, 'mini_technique'))" compact />
            </div>
          </div>
          <div class="signal-row">
            <span>Recopie charge</span>
            <strong>{{ formatNumber(getNumber(heaterFeedback, "load_pct"), 1) }}% <small>{{ getString(heaterFeedback, "load_register_label", "%MW574") }}</small></strong>
          </div>
          <div class="signal-row">
            <span>Erreur recopie</span>
            <StatusBadge
              :label="`${getString(heaterFeedback, 'error_register_label', '%MW576.0')}=${boolText(getBoolean(heaterFeedback, 'error'))}`"
              :tone="okWhenFalseTone(getBoolean(heaterFeedback, 'error'))"
              compact
            />
          </div>
        </div>
      </PanelCard>
    </section>

    <section class="planner-live-grid">
      <PanelCard title="File planificateur dynamique" status="%MW8120 + slot*46" status-tone="running" accent-tone="running">
        <div class="planner-limit-row">
          <StatusBadge :label="`${plannerVisibleCount} / ${plannerSlotLimit} slots utilises`" tone="running" compact />
          <span class="helper-text">Limite physique Rev02: 10 ordres maximum, stride 46 mots par slot.</span>
        </div>

        <div class="planner-flow-summary">
          <article class="queue-card">
            <p class="muted-2 uppercase">Ordre actif runtime</p>
            <p>
              <strong class="mono">ID {{ activeOrderId || 0 }}</strong>
              <span>strategie {{ getString(runtime, "active_strategy") }}</span>
              <span>target {{ formatNumber(getNumber(runtime, "target_pressure_bar"), 1) }} bar</span>
              <span>%MW9070-%MW9074</span>
            </p>
          </article>
          <article class="queue-card">
            <p class="muted-2 uppercase">Prochain ordre queue head</p>
            <p v-if="nextOrder">
              <strong class="mono">ID {{ nextOrder.id }}</strong>
              <span>{{ nextOrder.executeAt }}</span>
              <span>slot {{ nextOrder.slotIndex }} / %MW{{ nextOrder.registerBase }}</span>
            </p>
            <p v-else>Aucun ordre en attente.</p>
          </article>
        </div>

        <div class="table-shell planner-live-table-shell">
          <table class="monitor-table">
            <thead>
              <tr>
                <th>Etat</th>
                <th>Slot</th>
                <th>Registre</th>
                <th>Order ID</th>
                <th>Execution</th>
                <th>Profil</th>
                <th>C1-2</th>
                <th>Cible</th>
                <th>C2-2</th>
                <th>C3-1</th>
                <th>CRC16</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="order in plannerOrders"
                :key="`${order.registerBase}-${order.id}`"
                :class="{
                  'row-active': orderLifecycle(order) === 'ACTIVE',
                  'row-next': orderLifecycle(order) === 'NEXT',
                }"
              >
                <td><StatusBadge :label="orderLifecycle(order)" :tone="orderLifecycleTone(order)" compact /></td>
                <td class="mono">{{ order.slotIndex }}</td>
                <td class="mono">%MW{{ order.registerBase }}</td>
                <td class="mono">{{ order.id }}</td>
                <td>{{ order.executeAt }}</td>
                <td>{{ order.profileLabel }}</td>
                <td>{{ formatNumber(order.powerLimitKw, 1) }} kW</td>
                <td>{{ formatNumber(order.elecPressureBar, 1) }} bar</td>
                <td>{{ order.metType }}</td>
                <td>{{ order.secoursEnabled ? 1 : 0 }}</td>
                <td class="mono">{{ order.crc16 }}</td>
              </tr>
              <tr v-if="plannerOrders.length === 0">
                <td colspan="11" class="helper-text">Aucun ordre pending: les slots `%MW8120+` sont vides.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </PanelCard>
    </section>

    <section class="monitor-grid">
      <PanelCard title="Moniteur style terminal" status="%MW250 / %MW8120 / %MW9070" status-tone="running" accent-tone="running">
        <pre class="terminal-card">==============================================================
{{ monitorTitle }} | SBC Time: {{ formatClock(plcClock) }} | WD=%MW256:{{ getNumber(snapshot, "plc_watchdog") }}
==============================================================
{{ pressureDisplayLabel }} : {{ formatNumber(getNumber(steamHeader, "pressure_bar"), 1) }} bar       [{{ pressureRegisterLabel }}]
{{ demandDisplayLabel }}        : {{ getNumber(steamHeader, "demand_kw") }} {{ demandDisplayUnit }}        [{{ demandRegisterLabel }}]
PLC Health            : fault={{ boolText(getBoolean(plcHealth, "fault")) }} count={{ getNumber(plcHealth, "fault_count") }} alarm={{ boolText(getBoolean(plcHealth, "alarm")) }} count={{ getNumber(plcHealth, "alarm_count") }} [{{ getString(plcHealthRegisters, "fault", "%MW9457.0 -> real %MW257.0") }}]
PT01 / RP08 / ZT16    : sensor_error={{ boolText(getBoolean(pressureSensor, "error")) }} mode={{ getString(pressureRegulation, "mode") }} setpoint={{ formatNumber(getNumber(pressureRegulation, "setpoint_bar"), 1) }}bar feedback={{ formatNumber(getNumber(heaterFeedback, "load_pct"), 1) }}%
Planner State         : state={{ getNumber(planner, "state") }} crc={{ getNumber(planner, "crc16") }} crc_state={{ getNumber(planner, "crc_state") }} [%MW8100-%MW8102]
Queue Head Order ID   : {{ queueHead ? getNumber(queueHead, "id") : 0 }}         [slot0 %MW8120]
Queue Head Profile    : {{ queueHead ? getString(queueHead, "mode_profile_label") : "n/a" }}
Active Runtime        : strategy={{ getString(runtime, "active_strategy") }} order_id={{ getNumber(runtime, "active_order_id") }} target={{ formatNumber(getNumber(runtime, "target_pressure_bar"), 1) }} bar stages={{ getNumber(runtime, "active_stages") }} [%MW9070-%MW9074]
--------------------------------------------------------------
IBC1 : {{ ibcRows[0].state }} Load={{ ibcRows[0].load }}% Target={{ ibcRows[0].target }}%
IBC2 : {{ ibcRows[1].state }} Load={{ ibcRows[1].load }}% Target={{ ibcRows[1].target }}%
IBC3 : {{ ibcRows[2].state }} Load={{ ibcRows[2].load }}% Target={{ ibcRows[2].target }}%
--------------------------------------------------------------
Status %MW1045={{ getNumber(operationStatus, "add") }} | %MW1057={{ getNumber(operationStatus, "delete") }} | %MW1069={{ getNumber(operationStatus, "reset") }}</pre>
      </PanelCard>

      <PanelCard title="Planificateur Rev02" status="read_plan live" status-tone="healthy" accent-tone="healthy">
        <div class="status-row">
          <StatusBadge :label="`%MW1045=${getNumber(operationStatus, 'add')}`" :tone="statusTone(getNumber(operationStatus, 'add'))" compact />
          <StatusBadge :label="`%MW1057=${getNumber(operationStatus, 'delete')}`" :tone="statusTone(getNumber(operationStatus, 'delete'))" compact />
          <StatusBadge :label="`%MW1069=${getNumber(operationStatus, 'reset')}`" :tone="statusTone(getNumber(operationStatus, 'reset'))" compact />
        </div>

        <div class="queue-card">
          <p class="muted-2 uppercase">Queue head raw %MW8120-%MW8127</p>
          <p class="mono">{{ queueHeadRaw.slice(0, 8).join(", ") || "n/a" }}</p>
        </div>

        <div v-if="queueHead" class="queue-card">
          <p class="muted-2 uppercase">Ordre en tete</p>
          <p>
            ID <strong>{{ getNumber(queueHead, "id") }}</strong>,
            profil <strong>{{ getString(queueHead, "mode_profile_label") }}</strong>,
            cible <strong>{{ formatNumber(getNumber(queueHead, "elec_pressure_bar"), 1) }} bar</strong>,
            secours <strong>{{ getBoolean(queueHead, "secours_enabled") ? "1" : "0" }}</strong>
          </p>
        </div>
        <p v-else class="helper-text">Aucun ordre en attente: le slot 0 est vide.</p>
      </PanelCard>
    </section>

    <section class="ibc-grid">
      <article v-for="ibc in ibcRows" :key="ibc.key" class="ibc-card">
        <div class="payload-header">
          <h3>{{ ibc.label }}</h3>
          <StatusBadge :label="`%MW${ibc.registerBase}`" tone="neutral" compact />
        </div>
        <p class="ibc-state">{{ ibc.state }}</p>
        <div class="bar-track">
          <span class="bar-fill" :style="{ width: `${Math.min(100, Math.max(0, ibc.load))}%` }" />
        </div>
        <p class="helper-text">Load {{ ibc.load }}% / Target {{ ibc.target }}%</p>
      </article>
    </section>

    <details class="debug-snapshot">
      <summary>
        <span>Snapshot JSON brut</span>
        <StatusBadge label="debug replie" tone="neutral" compact />
      </summary>
      <pre class="payload-preview">{{ JSON.stringify(snapshot ?? { status: "waiting" }, null, 2) }}</pre>
    </details>
  </section>
</template>

<style scoped>
.monitor-page {
  display: grid;
  gap: 1.3rem;
}

.monitor-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1.2rem;
  align-items: end;
  padding: 1.45rem 1.55rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background:
    radial-gradient(circle at top left, rgba(82, 117, 176, 0.22), transparent 32%),
    linear-gradient(180deg, rgba(12, 14, 16, 0.96), rgba(8, 9, 10, 0.94));
}

.monitor-hero h1,
.monitor-hero p {
  margin: 0;
}

.monitor-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: end;
  justify-content: flex-end;
}

.monitor-status-line,
.status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  align-items: center;
}

.payload-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.payload-header h3 {
  margin: 0;
}

.monitor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
  gap: 1.25rem;
}

.planner-live-grid {
  display: grid;
  gap: 1rem;
}

.real-signal-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.signal-list {
  display: grid;
  gap: 0.75rem;
}

.signal-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.65rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.signal-row:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.signal-row span,
.signal-row small {
  color: var(--muted);
}

.signal-badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.4rem;
}

.planner-limit-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
}

.planner-limit-row .helper-text {
  margin: 0;
}

.planner-flow-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.planner-flow-summary .queue-card p:last-child {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.table-shell {
  overflow-x: auto;
  border-radius: 1rem;
  border: 1px solid var(--line);
}

.monitor-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 58rem;
}

.monitor-table th,
.monitor-table td {
  padding: 0.8rem 0.9rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  text-align: left;
  white-space: nowrap;
}

.monitor-table th {
  color: var(--muted);
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.monitor-table tbody tr {
  background: rgba(255, 255, 255, 0.015);
}

.monitor-table tbody tr.row-next {
  background: rgba(82, 117, 176, 0.15);
}

.monitor-table tbody tr.row-active {
  background: rgba(92, 211, 148, 0.16);
}

.terminal-card,
.payload-preview {
  margin: 0;
  padding: 1rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(6, 7, 8, 0.92);
  color: var(--green);
  overflow: auto;
  white-space: pre-wrap;
}

.queue-card,
.ibc-card {
  padding: 1rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
}

.queue-card p,
.ibc-card p,
.ibc-card h3 {
  margin: 0;
}

.debug-snapshot {
  display: grid;
  gap: 0.85rem;
  padding: 1rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
}

.debug-snapshot summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  cursor: pointer;
  color: var(--text);
  font-weight: 700;
  list-style: none;
}

.debug-snapshot summary::-webkit-details-marker {
  display: none;
}

.ibc-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.ibc-card {
  display: grid;
  gap: 0.85rem;
}

.ibc-state {
  color: var(--text);
  font-size: 1.45rem;
  font-weight: 700;
}

.bar-track {
  overflow: hidden;
  height: 0.75rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--green), var(--blue));
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

.field {
  display: grid;
  gap: 0.4rem;
}

.field span {
  color: var(--muted);
  font-size: 0.9rem;
}

.field input,
.field select {
  min-height: 2.85rem;
  padding: 0.75rem 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
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

.notice-error {
  border-color: rgba(255, 154, 139, 0.28);
  color: var(--red-soft);
  background: rgba(123, 38, 33, 0.22);
}

.helper-text {
  color: var(--muted);
}

.muted-2 {
  color: var(--muted-2);
}

.uppercase {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.78rem;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
}

@media (max-width: 1100px) {
  .monitor-hero,
  .monitor-grid,
  .real-signal-grid,
  .planner-flow-summary,
  .ibc-grid,
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .monitor-controls {
    justify-content: stretch;
  }
}
</style>
