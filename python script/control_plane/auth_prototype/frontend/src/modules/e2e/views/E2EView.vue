<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { ApiError } from "@/api/client";
import { fetchInventoryAssets, runE2ETest } from "@/api/provisioning";
import MetricCard from "@/components/ui/MetricCard.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import type {
  ApiE2EConnectionPayload,
  ApiE2ETestPayload,
  ApiInventoryAssetPayload,
  DashboardMetric,
} from "@/types/controlPlane";

const route = useRoute();

type E2ERunMode = "manual" | "auto";

interface E2ETrendPoint {
  id: string;
  mode: E2ERunMode;
  recordedAt: string;
  sampleCount: number;
  sampleIndex: number;
  totalWithProxyMs: number | null;
  totalWithoutProxyMs: number | null;
  observedTotalMs: number | null;
}

const loadingAssets = ref(false);
const runningTest = ref(false);
const errorMessage = ref<string | null>(null);
const noticeMessage = ref<string | null>(null);

const assets = ref<ApiInventoryAssetPayload[]>([]);
const selectedAssetId = ref<number | null>(null);
const latestResult = ref<ApiE2ETestPayload | null>(null);
const selectedRunMode = ref<E2ERunMode>("manual");
const selectedFlowKey = ref<"ems_site" | "ems_light">("ems_site");
const selectedSampleCount = ref(5);
const selectedSampleIntervalSeconds = ref(0);
const selectedAutoIntervalSeconds = ref(10);
const autoModeEnabled = ref(false);
const trendHistory = ref<E2ETrendPoint[]>([]);

const flowOptions = [
  {
    key: "ems_site" as const,
    label: "ems-site",
    description: "Control Panel -> Broker -> Industrial PC",
  },
  {
    key: "ems_light" as const,
    label: "ems-light",
    description: "Control Panel -> Broker -> ems-light",
  },
];

const sampleCountOptions = [1, 5, 10, 20, 50, 100];
const sampleIntervalOptions = [0, 1, 2, 5, 10, 20];
const autoIntervalOptions = [5, 10, 20, 30, 60, 120];
const maxTrendHistoryPoints = 120;

let autoTimerHandle: ReturnType<typeof setTimeout> | null = null;
let trendPointSequence = 0;

function toErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : "Une erreur inconnue est survenue.";
}

function parseRouteSiteId() {
  const rawValue = String(route.params.siteId ?? "");
  const parsed = Number.parseInt(rawValue, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "n/a";
  }
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    return value;
  }
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(timestamp);
}

function formatLatency(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ms`;
}

function formatInteger(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return value.toLocaleString("fr-FR");
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function roundLatency(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return null;
  }
  return Math.round(value * 1000) / 1000;
}

function getMeasurementStatAverage(result: ApiE2ETestPayload | null, key: string) {
  const stat = result?.measurement_batch?.stats.find((candidate) => candidate.key === key);
  return stat?.avg_ms ?? null;
}

function sumLatencies(values: Array<number | null | undefined>) {
  if (!values.every((value) => value !== null && value !== undefined && Number.isFinite(value))) {
    return null;
  }
  return roundLatency(values.reduce<number>((sum, value) => sum + Number(value), 0));
}

function parseIsoTimestampMs(value: unknown) {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function splitRoundTripMs(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return {
      outboundMs: null,
      returnMs: null,
    };
  }
  const halfValue = value / 2;
  return {
    outboundMs: roundLatency(halfValue),
    returnMs: roundLatency(value - halfValue),
  };
}

function formatDurationWindow(startMs: number, endMs: number) {
  return `${formatLatency(startMs)} -> ${formatLatency(endMs)}`;
}

function shortenMiddle(value: string | null | undefined, maxLength = 28) {
  if (!value) {
    return "n/a";
  }
  if (value.length <= maxLength) {
    return value;
  }
  const visible = Math.max(8, maxLength - 3);
  const head = Math.ceil(visible * 0.58);
  const tail = Math.max(4, visible - head);
  return `${value.slice(0, head)}...${value.slice(-tail)}`;
}

function latencyTone(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "neutral";
  }
  if (value <= 100) {
    return "healthy";
  }
  if (value <= 350) {
    return "warning";
  }
  return "critical";
}

function statusTone(status: string | null | undefined) {
  switch ((status ?? "").toLowerCase()) {
    case "ok":
    case "enabled":
    case "healthy":
      return "healthy";
    case "warning":
    case "degraded":
      return "warning";
    case "error":
    case "failed":
    case "critical":
      return "critical";
    default:
      return "neutral";
  }
}

const routeSiteId = computed(() => parseRouteSiteId());

const industrialPcAssets = computed(() =>
  assets.value.filter(
    (asset) => asset.asset_type === "industrial_pc" && asset.inventory_hostname && asset.registration_status !== "discovered",
  ),
);

const selectedAsset = computed(
  () => industrialPcAssets.value.find((asset) => asset.id === selectedAssetId.value) ?? null,
);

const probe = computed(() => latestResult.value?.probe ?? null);
const measurementBatch = computed(() => latestResult.value?.measurement_batch ?? null);
const currentFlowKey = computed(() => probe.value?.flow_key ?? selectedFlowKey.value);
const requiresAssetSelection = computed(() => selectedFlowKey.value === "ems_site");
const isManualMode = computed(() => selectedRunMode.value === "manual");

const resultWarnings = computed(() => {
  const warnings = [
    ...(probe.value?.warnings ?? []),
    ...(probe.value?.monitoring.warnings ?? []),
  ];
  return [...new Set(warnings)];
});

const monitoringConnections = computed(() => {
  if (!probe.value) {
    return [];
  }

  if (currentFlowKey.value === "ems_light") {
    return [
      {
        key: "ems_light_bridge",
        label: "ems-light bridge",
        description: "Connexion NATS singleton observee depuis le broker pour ems-light",
        connection: probe.value.monitoring.connections.ems_light_bridge ?? null,
      },
    ].filter((row) => row.connection !== null);
  }

  const rows: Array<{
    key: string;
    label: string;
    description: string;
    connection: ApiE2EConnectionPayload | null;
  }> = [
    {
      key: "control_panel_probe",
      label: probe.value.probe_mode === "broker_proxy" ? "Broker-local probe" : "Control panel probe",
      description:
        probe.value.probe_mode === "broker_proxy"
          ? "Client NATS ephemere ouvert dans le broker pour lancer le watchdog et relire /connz. Diagnostic local uniquement."
          : "Connexion du probe lance depuis le control panel vers NATS",
      connection: probe.value.monitoring.connections.control_panel_probe,
    },
    {
      key: "gateway_modbus",
      label: "Industrial PC gateway_modbus",
      description: "Canal NATS du service gateway_modbus, utilise pour les commandes et le request/reply",
      connection: probe.value.monitoring.connections.gateway_modbus,
    },
    {
      key: "telemetry_publisher",
      label: "Industrial PC telemetry_publisher",
      description: "Canal NATS publish-only de telemetrie, distinct du request/reply gateway_modbus; son RTT /connz est tres sensible au polling Modbus local",
      connection: probe.value.monitoring.connections.telemetry_publisher,
    },
  ];
  return rows.filter((row) => row.connection !== null);
});

const monitoringUrlValue = computed(() => probe.value?.monitoring.url ?? "n/a");

const monitoringUrlIsInternal = computed(() => {
  if (probe.value?.monitoring_visibility === "broker_internal") {
    return true;
  }
  const url = probe.value?.monitoring.url ?? "";
  return url.includes("host.docker.internal") || url.includes("127.0.0.1") || url.includes("localhost");
});

const monitoringUrlTitle = computed(() =>
  monitoringUrlIsInternal.value ? "Broker-side monitoring target" : "Monitoring URL",
);

const monitoringUrlSubtitle = computed(() =>
  monitoringUrlIsInternal.value
    ? "URL interne au broker, pas directement ouvrable depuis ton navigateur"
    : "/connz, /varz, /healthz",
);

const brokerNameValue = computed(() =>
  shortenMiddle(probe.value?.monitoring.varz?.server_name ?? null, 34),
);

const controlPlaneTotalMs = computed(
  () => probe.value?.summary.control_plane_total_ms ?? probe.value?.summary.round_trip_ms ?? null,
);

const transportOverheadMs = computed(() => probe.value?.summary.transport_overhead_ms ?? null);

const modbusSimulatorRoundTripMs = computed(() => {
  const backendValue = probe.value?.summary.modbus_simulator_round_trip_ms;
  if (backendValue !== null && backendValue !== undefined) {
    return backendValue;
  }
  const receivedAt = parseIsoTimestampMs(probe.value?.reply_payload?.edge_received_at);
  const repliedAt = parseIsoTimestampMs(probe.value?.reply_payload?.edge_replied_at);
  if (receivedAt === null || repliedAt === null) {
    return null;
  }
  return roundLatency(Math.max(repliedAt - receivedAt, 0));
});

const brokerToIndustrialPcRoundTripMs = computed(() =>
  currentFlowKey.value === "ems_site"
    ? (probe.value?.summary.broker_to_ipc_active_ms ?? probe.value?.summary.gateway_connection_rtt_ms ?? null)
    : (probe.value?.summary.gateway_connection_rtt_ms ?? null),
);

const controlPanelToBrokerRoundTripMs = computed(() => {
  const backendValue = probe.value?.summary.control_panel_to_broker_active_ms;
  if (backendValue !== null && backendValue !== undefined) {
    return backendValue;
  }
  return transportOverheadMs.value;
});

const brokerProxyInternalMs = computed(() =>
  probe.value?.summary.broker_proxy_internal_ms ?? probe.value?.summary.broker_proxy_handler_ms ?? null,
);

const brokerProxySetupMs = computed(() =>
  currentFlowKey.value === "ems_site"
    ? (probe.value?.summary.probe_nats_connect_ms ?? null)
    : null,
);

const brokerProxyFinalizeMs = computed(() =>
  currentFlowKey.value === "ems_site"
    ? (probe.value?.summary.probe_monitoring_fetch_ms ?? null)
    : null,
);

const activeCascadeTotalMs = computed(() => {
  const backendValue = probe.value?.summary.reconstructed_active_total_ms;
  if (backendValue !== null && backendValue !== undefined) {
    return backendValue;
  }
  const knownComponents =
    currentFlowKey.value === "ems_light"
      ? [
          controlPanelToBrokerRoundTripMs.value,
          brokerProxyInternalMs.value,
          probe.value?.summary.ems_light_connection_rtt_ms,
        ].filter((value): value is number => typeof value === "number" && Number.isFinite(value))
      : [
          controlPanelToBrokerRoundTripMs.value,
          brokerProxyInternalMs.value,
          brokerToIndustrialPcRoundTripMs.value,
          modbusSimulatorRoundTripMs.value,
        ].filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (knownComponents.length === (currentFlowKey.value === "ems_light" ? 3 : 4)) {
    return roundLatency(knownComponents.reduce((sum, value) => sum + value, 0));
  }
  return controlPlaneTotalMs.value;
});

const activeHotFlowWithoutProxyMs = computed(() => {
  if (currentFlowKey.value === "ems_light") {
    const knownComponents = [
      controlPanelToBrokerRoundTripMs.value,
      probe.value?.summary.ems_light_connection_rtt_ms,
    ].filter((value): value is number => typeof value === "number" && Number.isFinite(value));
    if (knownComponents.length === 2) {
      return roundLatency(knownComponents.reduce((sum, value) => sum + value, 0));
    }
    if (
      activeCascadeTotalMs.value !== null
      && brokerProxyInternalMs.value !== null
      && brokerProxyInternalMs.value !== undefined
    ) {
      return roundLatency(Math.max(activeCascadeTotalMs.value - brokerProxyInternalMs.value, 0));
    }
    return null;
  }
  const knownComponents = [
    controlPanelToBrokerRoundTripMs.value,
    brokerToIndustrialPcRoundTripMs.value,
    modbusSimulatorRoundTripMs.value,
  ].filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (knownComponents.length === 3) {
    return roundLatency(knownComponents.reduce((sum, value) => sum + value, 0));
  }
  if (
    activeCascadeTotalMs.value !== null
    && brokerProxyInternalMs.value !== null
    && brokerProxyInternalMs.value !== undefined
  ) {
    return roundLatency(Math.max(activeCascadeTotalMs.value - brokerProxyInternalMs.value, 0));
  }
  return null;
});

const roundTripSubtitle = computed(() =>
  probe.value?.round_trip_label
  ?? (currentFlowKey.value === "ems_light"
    ? "Control Panel -> Broker -> ems-light -> Broker -> Control Panel"
    : probe.value?.probe_mode === "broker_proxy"
      ? "Control Panel -> Broker -> Industrial PC -> Modbus Simulator -> Industrial PC -> Broker -> Control Panel"
      : "Control Panel -> Broker VM -> Industrial PC -> Modbus Simulator -> Industrial PC -> Broker VM -> Control Panel"),
);

const roundTripExplanation = computed(() => {
  if (currentFlowKey.value === "ems_light") {
    return "La cascade ci-dessous reconstitue trois composants sequentiels pour ce flux global: control panel <-> broker, traitement local dans le broker, puis lien broker <-> ems-light observe dans /connz. Ce flux est singleton et ne depend pas d'un industrial PC particulier.";
  }
  return "La cascade ci-dessous affiche un RTT actif reconstruit, plus proche du watchdog que du simple temps HTTP. Elle additionne quatre composants: control panel <-> broker, traitement interne du broker, broker <-> industrial PC, puis industrial PC <-> modbus simulator. Le traitement broker est lui-meme decoupe en setup local avant l'aller NATS, puis finalize/observabilite avant la reponse HTTP. Les segments sont places sequentiellement sur la timeline totale.";
});

const probeChannelTitle = computed(() =>
  currentFlowKey.value === "ems_light"
    ? "Control panel -> broker"
    :
  probe.value?.probe_mode === "broker_proxy" ? "Broker-local NATS client RTT" : "Control panel probe RTT",
);

const probeChannelSubtitle = computed(() =>
  currentFlowKey.value === "ems_light"
    ? "Round-trip HTTPS observe vers le broker probe"
    :
  probe.value?.probe_mode === "broker_proxy"
    ? "Snapshot /connz du client NATS ephemere ouvert dans le broker pour lancer le watchdog. Diagnostic local uniquement, hors cascade active."
    : "Snapshot /connz de la connexion du probe control panel vers NATS",
);

const metrics = computed<DashboardMetric[]>(() => {
  if (!probe.value) {
    return [];
  }

  if (currentFlowKey.value === "ems_light") {
    return [
      {
        title: "RTT actif (avec traitement broker)",
        value: formatLatency(activeCascadeTotalMs.value),
        subtitle: "Somme du flux reconstruit, incluant le traitement local du broker",
        tone: latencyTone(activeCascadeTotalMs.value),
      },
      {
        title: "RTT actif (sans traitement broker)",
        value: formatLatency(activeHotFlowWithoutProxyMs.value),
        subtitle: "Flux reconstruit sans le temps local de traitement dans le broker",
        tone: latencyTone(activeHotFlowWithoutProxyMs.value),
      },
      {
        title: "Control Panel <-> Broker VM",
        value: formatLatency(controlPanelToBrokerRoundTripMs.value),
        subtitle: "Composant d'acces au broker depuis le control panel",
        tone: latencyTone(controlPanelToBrokerRoundTripMs.value),
      },
      {
        title: "Traitement broker",
        value: formatLatency(brokerProxyInternalMs.value),
        subtitle: "Temps local passe dans le broker pour interroger /connz et construire la reponse",
        tone: latencyTone(brokerProxyInternalMs.value),
      },
      {
        title: "Broker VM <-> ems-light",
        value: formatLatency(probe.value.summary.ems_light_connection_rtt_ms),
        subtitle: "Snapshot /connz de la connexion iec104-bridge",
        tone: latencyTone(probe.value.summary.ems_light_connection_rtt_ms),
      },
      {
        title: "Observed connection",
        value: probe.value.reply_payload?.name ? String(probe.value.reply_payload.name) : "n/a",
        subtitle: probe.value.reply_payload?.ip ? `IP: ${String(probe.value.reply_payload.ip)}` : "Connexion singleton cote broker",
        tone: "neutral",
      },
    ];
  }

  return [
    {
      title: "RTT actif (avec traitement broker)",
      value: formatLatency(activeCascadeTotalMs.value),
      subtitle: "Somme du hot flow reconstitue, incluant le traitement interne du broker",
      tone: latencyTone(activeCascadeTotalMs.value),
    },
    {
      title: "RTT actif (sans traitement broker)",
      value: formatLatency(activeHotFlowWithoutProxyMs.value),
      subtitle: "Hot flow reconstitue sans le temps local de traitement dans le broker",
      tone: latencyTone(activeHotFlowWithoutProxyMs.value),
    },
    {
      title: "Probe mode",
      value: probe.value.probe_mode === "broker_proxy" ? "Via broker" : "Direct NATS",
      subtitle:
        probe.value.probe_mode === "broker_proxy"
          ? "Total vu depuis le control panel, mesure active executee depuis le broker"
          : "Total et request/reply mesures depuis le control panel",
      tone: "neutral",
    },
    {
      title: probeChannelTitle.value,
      value: formatLatency(probe.value.summary.probe_connection_rtt_ms),
      subtitle: probeChannelSubtitle.value,
      tone: latencyTone(probe.value.summary.probe_connection_rtt_ms),
    },
    {
      title: "Traitement broker",
      value: formatLatency(brokerProxyInternalMs.value),
      subtitle:
        probe.value.probe_mode === "broker_proxy"
          ? "Temps local passe dans le broker hors acces control panel, incluant surtout client NATS local et snapshot monitoring"
          : "n/a en mode direct",
      tone: latencyTone(brokerProxyInternalMs.value),
    },
    {
      title: "Reply payload",
      value:
        probe.value.summary.reply_value === null || probe.value.summary.reply_value === undefined
          ? "n/a"
          : String(probe.value.summary.reply_value),
      subtitle: `status: ${probe.value.summary.reply_status ?? "unknown"}`,
      tone: statusTone(probe.value.summary.reply_status),
    },
  ];
});

const channelSnapshotMetrics = computed<DashboardMetric[]>(() => {
  if (!probe.value) {
    return [];
  }

  if (currentFlowKey.value === "ems_light") {
    return [
      {
        title: "ems-light",
        value: formatLatency(probe.value.summary.ems_light_connection_rtt_ms),
        subtitle: "Snapshot /connz de la connexion broker -> ems-light (iec104-bridge)",
        tone: latencyTone(probe.value.summary.ems_light_connection_rtt_ms),
      },
    ];
  }

  return [
    {
      title: "gateway_modbus",
      value: formatLatency(probe.value.summary.gateway_connection_rtt_ms),
      subtitle: "Snapshot /connz du canal gateway_modbus, distinct du canal telemetry_publisher",
      tone: latencyTone(probe.value.summary.gateway_connection_rtt_ms),
    },
    {
      title: "telemetry_publisher",
      value: formatLatency(probe.value.summary.telemetry_connection_rtt_ms),
      subtitle: "Snapshot /connz du canal telemetry_publisher, sensible au polling Modbus synchrone et a la reactivite de son event loop",
      tone: latencyTone(probe.value.summary.telemetry_connection_rtt_ms),
    },
  ];
});

const activeCascadeRows = computed(() => {
  if (!probe.value || activeCascadeTotalMs.value === null || activeCascadeTotalMs.value <= 0) {
    return [];
  }

  const totalMs = activeCascadeTotalMs.value;
  const segmentDefinitions: Array<{
    key: string;
    label: string;
    subtitle: string;
    approximation: string | null;
    durationMs: number | null | undefined;
    outboundDurationMs?: number | null | undefined;
    returnDurationMs?: number | null | undefined;
    outboundLabel?: string;
    returnLabel?: string;
  }> = [];

  if (currentFlowKey.value === "ems_light") {
    segmentDefinitions.push(
      {
        key: "broker_access",
        label: "Control Panel -> Broker VM",
        subtitle: "RTT observe entre le control panel et le broker pour ce flux singleton",
        durationMs: controlPanelToBrokerRoundTripMs.value,
        approximation: "aller/retour reconstruits a parts egales",
      },
      {
        key: "broker_processing",
        label: "Traitement broker",
        subtitle: "Temps local dans le broker pour interroger /connz et construire la reponse du probe",
        durationMs: brokerProxyInternalMs.value,
        approximation: "aller/retour reconstruits a parts egales a partir du temps mesure cote broker",
      },
      {
        key: "ems_light_bridge",
        label: "Broker VM -> ems-light",
        subtitle: "Connexion iec104-bridge observee dans /connz cote broker",
        durationMs: probe.value.summary.ems_light_connection_rtt_ms,
        approximation: "aller/retour reconstruits a parts egales a partir du RTT observe",
      },
    );
  } else {
    segmentDefinitions.push(
      {
        key: "control_panel_broker",
        label: "Control Panel -> Broker VM",
        subtitle:
          probe.value.probe_mode === "broker_proxy"
            ? "Segment residuel du RTT actif. Il couvre le passage control panel -> broker -> control panel, hors broker -> IPC et hors Modbus."
            : "Segment residuel du RTT actif entre le control panel et le broker NATS.",
        durationMs: controlPanelToBrokerRoundTripMs.value,
        approximation: "aller/retour reconstruits a parts egales",
      },
      {
        key: "broker_proxy_internal",
        label: "Traitement broker",
        subtitle: "Temps local dans le broker: setup du client NATS avant l'aller, puis finalize/observabilite avant la reponse HTTP",
        durationMs: brokerProxyInternalMs.value,
        outboundDurationMs: brokerProxySetupMs.value,
        returnDurationMs: brokerProxyFinalizeMs.value,
        outboundLabel: "setup",
        returnLabel: "finalize",
        approximation: "phases mesurees cote broker",
      },
      {
        key: "broker_industrial_pc",
        label: "Broker VM -> Industrial PC",
        subtitle: "RTT du canal gateway_modbus observe via /connz cote broker",
        durationMs: brokerToIndustrialPcRoundTripMs.value,
        approximation: "aller/retour reconstruits a parts egales a partir du RTT /connz",
      },
      {
        key: "industrial_pc_modbus",
        label: "Industrial PC -> Modbus Simulator",
        subtitle: "RTT derive des timestamps edge_received_at / edge_replied_at autour du write/read Modbus",
        durationMs: modbusSimulatorRoundTripMs.value,
        approximation: "aller/retour reconstruits a parts egales a partir du temps edge",
      },
    );
  }

  const normalizedSegments = segmentDefinitions
    .filter((segment) => segment.durationMs !== null && segment.durationMs !== undefined && Number.isFinite(segment.durationMs) && segment.durationMs > 0)
    .map((segment) => {
      const normalizedDuration = segment.durationMs as number;
      const explicitOutboundDuration = segment.outboundDurationMs;
      const explicitReturnDuration = segment.returnDurationMs;
      const outboundDuration =
        explicitOutboundDuration !== null && explicitOutboundDuration !== undefined && Number.isFinite(explicitOutboundDuration)
          ? explicitOutboundDuration
          : normalizedDuration / 2;
      const returnDuration =
        explicitReturnDuration !== null && explicitReturnDuration !== undefined && Number.isFinite(explicitReturnDuration)
          ? explicitReturnDuration
          : normalizedDuration - outboundDuration;
      return {
        ...segment,
        durationMs: normalizedDuration,
        outboundDuration,
        returnDuration,
        outboundMs: roundLatency(outboundDuration),
        returnMs: roundLatency(returnDuration),
        outboundLabel: segment.outboundLabel ?? "aller",
        returnLabel: segment.returnLabel ?? "retour",
      };
    });

  const outboundPrefixSums: number[] = [];
  let outboundAccumulator = 0;
  for (const segment of normalizedSegments) {
    outboundPrefixSums.push(outboundAccumulator);
    outboundAccumulator += segment.outboundDuration;
  }

  const returnSuffixSums: number[] = new Array(normalizedSegments.length).fill(0);
  let returnAccumulator = 0;
  for (let index = normalizedSegments.length - 1; index >= 0; index -= 1) {
    returnSuffixSums[index] = returnAccumulator;
    returnAccumulator += normalizedSegments[index].returnDuration;
  }

  return normalizedSegments.map((segment, index) => {
    const outboundStartMs = outboundPrefixSums[index];
    const returnStartMs = outboundAccumulator + returnSuffixSums[index];
    const rowStartMs = outboundStartMs;
    const rowEndMs = returnStartMs + segment.returnDuration;

    return {
      key: segment.key,
      label: segment.label,
      subtitle: segment.subtitle,
      startMs: rowStartMs,
      endMs: rowEndMs,
      durationMs: segment.durationMs,
      outboundMs: segment.outboundMs,
      returnMs: segment.returnMs,
      outboundLabel: segment.outboundLabel,
      returnLabel: segment.returnLabel,
      outboundOffsetPct: (outboundStartMs / totalMs) * 100,
      outboundWidthPct: (segment.outboundDuration / totalMs) * 100,
      returnOffsetPct: (returnStartMs / totalMs) * 100,
      returnWidthPct: (segment.returnDuration / totalMs) * 100,
      approximation: segment.approximation,
    };
  });
});

const pageTitle = computed(() => {
  if (selectedFlowKey.value === "ems_light") {
    return "Telemetry E2E - ems-light";
  }
  const siteName = latestResult.value?.site?.name ?? selectedAsset.value?.site?.name;
  if (siteName) {
    return `Telemetry E2E - ${siteName}`;
  }
  return "Telemetry E2E";
});

const pageSubtitle = computed(() => {
  if (selectedFlowKey.value === "ems_light") {
    return "Flux global singleton : Control Panel -> Broker -> ems-light. Ce test ne depend pas d'un industrial PC specifique.";
  }
  if (selectedAsset.value) {
    const siteCode = selectedAsset.value.site?.code ? `${selectedAsset.value.site?.code} - ` : "";
    return `${siteCode}${selectedAsset.value.inventory_hostname} (${selectedAsset.value.management_ip ?? "IP n/a"})`;
  }
  return "Selectionne un industrial PC puis lance un round-trip NATS via le broker.";
});

const latestTrendPoint = computed(() =>
  trendHistory.value.length ? trendHistory.value[trendHistory.value.length - 1] : null,
);

const launchButtonLabel = computed(() => {
  if (isManualMode.value) {
    return runningTest.value ? "Test manuel en cours..." : "Lancer";
  }
  return autoModeEnabled.value
    ? (runningTest.value ? "Arreter auto (run en cours)" : "Arreter auto")
    : "Lancer";
});

const launchButtonSubtitle = computed(() => {
  if (isManualMode.value) {
    return `Serie manuelle: ${selectedSampleCount.value} point${selectedSampleCount.value > 1 ? "s" : ""}`;
  }
  return autoModeEnabled.value
    ? `Mode auto actif, une mesure toutes les ${selectedAutoIntervalSeconds.value}s`
    : `Mode auto pret, une mesure toutes les ${selectedAutoIntervalSeconds.value}s`;
});

const runModeExplanation = computed(() => {
  if (isManualMode.value) {
    const cadenceText =
      selectedSampleCount.value > 1
        ? ` Cadence inter-mesures: ${selectedSampleIntervalSeconds.value === 0 ? "immediate" : `${selectedSampleIntervalSeconds.value}s`}.`
        : "";
    return `Mode manuel actif. Cette serie lancera ${selectedSampleCount.value} mesure${selectedSampleCount.value > 1 ? "s" : ""}.${cadenceText} Chaque mesure individuelle sera tracee comme un point.`;
  }
  return `Mode auto actif. Une mesure unique sera relancee toutes les ${selectedAutoIntervalSeconds.value} seconde${selectedAutoIntervalSeconds.value > 1 ? "s" : ""} sans chevauchement, puis ajoutee au graphe.`;
});

const trendChart = computed(() => {
  const points = trendHistory.value.filter(
    (point) => point.totalWithProxyMs !== null || point.totalWithoutProxyMs !== null,
  );

  if (!points.length) {
    return null;
  }

  const width = 980;
  const height = 280;
  const plotLeft = 52;
  const plotRight = width - 18;
  const plotTop = 18;
  const plotBottom = height - 34;
  const plotWidth = plotRight - plotLeft;
  const plotHeight = plotBottom - plotTop;

  const allValues = points.flatMap((point) => [point.totalWithProxyMs, point.totalWithoutProxyMs])
    .filter((value): value is number => value !== null && Number.isFinite(value));

  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const yMin = Math.max(0, Math.floor(minValue * 0.85));
  const yMax = Math.max(yMin + 10, Math.ceil(maxValue * 1.12));
  const yRange = Math.max(yMax - yMin, 1);

  const timestamps = points.map((point) => parseIsoTimestampMs(point.recordedAt));
  const validTimestamps = timestamps.filter((value): value is number => value !== null);
  const timestampMin = validTimestamps.length ? Math.min(...validTimestamps) : null;
  const timestampMax = validTimestamps.length ? Math.max(...validTimestamps) : null;
  const timestampSpan = timestampMin !== null && timestampMax !== null ? timestampMax - timestampMin : 0;

  const positionX = (index: number, timestampMs: number | null) => {
    if (points.length === 1) {
      return plotLeft + plotWidth / 2;
    }
    if (timestampMin !== null && timestampMax !== null && timestampMs !== null && timestampSpan > 0) {
      return plotLeft + ((timestampMs - timestampMin) / timestampSpan) * plotWidth;
    }
    return plotLeft + (index / (points.length - 1)) * plotWidth;
  };

  const positionY = (value: number | null) => {
    if (value === null || !Number.isFinite(value)) {
      return null;
    }
    return plotTop + ((yMax - value) / yRange) * plotHeight;
  };

  const chartPoints = points.map((point, index) => {
    const timestampMs = timestamps[index];
    return {
      ...point,
      x: positionX(index, timestampMs),
      yWithProxy: positionY(point.totalWithProxyMs),
      yWithoutProxy: positionY(point.totalWithoutProxyMs),
      tooltipLabel: `${formatDateTime(point.recordedAt)} | ${point.mode === "auto" ? "auto" : "manuel"} | point ${point.sampleIndex}/${point.sampleCount}`,
    };
  });

  const buildPath = (selector: (point: (typeof chartPoints)[number]) => number | null) => {
    const plottedPoints = chartPoints
      .map((point) => {
        const yValue = selector(point);
        return yValue === null ? null : `${point.x.toFixed(1)},${yValue.toFixed(1)}`;
      })
      .filter((value): value is string => value !== null);
    if (!plottedPoints.length) {
      return null;
    }
    return `M ${plottedPoints.join(" L ")}`;
  };

  const midpointValue = roundLatency(yMin + yRange / 2) ?? yMin;

  return {
    width,
    height,
    plotLeft,
    plotRight,
    plotTop,
    plotBottom,
    guides: [
      { key: "max", value: yMax, y: positionY(yMax) ?? plotTop },
      { key: "mid", value: midpointValue, y: positionY(midpointValue) ?? (plotTop + plotBottom) / 2 },
      { key: "min", value: yMin, y: positionY(yMin) ?? plotBottom },
    ],
    withProxyPath: buildPath((point) => point.yWithProxy),
    withoutProxyPath: buildPath((point) => point.yWithoutProxy),
    points: chartPoints,
    startedAt: points[0].recordedAt,
    endedAt: points[points.length - 1].recordedAt,
  };
});

function appendTrendPoints(result: ApiE2ETestPayload, mode: E2ERunMode) {
  const measurementSamples = result.measurement_batch?.samples ?? [];

  if (measurementSamples.length) {
    const appendedPoints: E2ETrendPoint[] = measurementSamples.map((sample, index) => {
      trendPointSequence += 1;
      const sampleValues = sample.values ?? {};
      const withProxyValue =
        (typeof sampleValues.active_total_ms === "number" ? sampleValues.active_total_ms : null)
        ?? result.probe.summary.reconstructed_active_total_ms
        ?? result.probe.summary.control_plane_total_ms
        ?? result.probe.summary.round_trip_ms
        ?? null;

      const withoutProxyValue =
        (typeof sampleValues.active_total_without_proxy_ms === "number"
          ? sampleValues.active_total_without_proxy_ms
          : null)
        ?? withProxyValue;

      const observedTotalValue =
        (typeof sampleValues.observed_total_ms === "number" ? sampleValues.observed_total_ms : null)
        ?? result.probe.summary.control_plane_total_ms
        ?? result.probe.summary.round_trip_ms
        ?? null;

      return {
        id: `${mode}-${trendPointSequence}`,
        mode,
        recordedAt: sample.tested_at || result.probe.tested_at || new Date().toISOString(),
        sampleCount: result.measurement_batch?.completed_count ?? measurementSamples.length,
        sampleIndex: sample.index ?? index + 1,
        totalWithProxyMs: withProxyValue,
        totalWithoutProxyMs: withoutProxyValue,
        observedTotalMs: observedTotalValue,
      };
    });

    trendHistory.value = [...trendHistory.value, ...appendedPoints].slice(-maxTrendHistoryPoints);
    return;
  }

  const withProxyValue = getMeasurementStatAverage(result, "active_total_ms")
    ?? result.probe.summary.reconstructed_active_total_ms
    ?? result.probe.summary.control_plane_total_ms
    ?? result.probe.summary.round_trip_ms
    ?? null;

  const withoutProxyValue = getMeasurementStatAverage(result, "active_total_without_proxy_ms")
    ?? sumLatencies([
      result.probe.summary.control_panel_to_broker_active_ms,
      result.probe.summary.broker_to_ipc_active_ms,
      result.probe.summary.modbus_simulator_round_trip_ms,
    ])
    ?? withProxyValue;

  const observedTotalValue = getMeasurementStatAverage(result, "observed_total_ms")
    ?? result.probe.summary.control_plane_total_ms
    ?? result.probe.summary.round_trip_ms
    ?? null;

  trendPointSequence += 1;
  trendHistory.value = [
    ...trendHistory.value,
    {
      id: `${mode}-${trendPointSequence}`,
      mode,
      recordedAt: result.probe.tested_at || new Date().toISOString(),
      sampleCount: result.measurement_batch?.completed_count ?? 1,
      sampleIndex: 1,
      totalWithProxyMs: withProxyValue,
      totalWithoutProxyMs: withoutProxyValue,
      observedTotalMs: observedTotalValue,
    },
  ].slice(-maxTrendHistoryPoints);
}

function clearAutoTimer() {
  if (autoTimerHandle !== null) {
    clearTimeout(autoTimerHandle);
    autoTimerHandle = null;
  }
}

function stopAutoMode() {
  autoModeEnabled.value = false;
  clearAutoTimer();
}

function resetTrendHistory() {
  trendHistory.value = [];
}

function clearTrendGraph() {
  resetTrendHistory();
}

function scheduleNextAutoRun() {
  clearAutoTimer();
  if (!autoModeEnabled.value) {
    return;
  }
  autoTimerHandle = setTimeout(() => {
    if (!autoModeEnabled.value) {
      return;
    }
    if (runningTest.value) {
      scheduleNextAutoRun();
      return;
    }
    void handleRunTest("auto");
  }, selectedAutoIntervalSeconds.value * 1000);
}

async function loadAssets() {
  loadingAssets.value = true;
  errorMessage.value = null;

  try {
    const response = await fetchInventoryAssets({
      siteId: routeSiteId.value,
      registrationStatus: "active",
    });
    assets.value = response.assets;

    if (selectedFlowKey.value === "ems_light") {
      noticeMessage.value = null;
    } else if (!routeSiteId.value) {
      noticeMessage.value =
        "Le site courant n'a pas d'identifiant numerique exploitable cote API. La liste affiche tous les industrial PCs actifs.";
    } else {
      noticeMessage.value = null;
    }

    if (!industrialPcAssets.value.length) {
      selectedAssetId.value = null;
      latestResult.value = null;
      return;
    }

    if (!industrialPcAssets.value.some((asset) => asset.id === selectedAssetId.value)) {
      selectedAssetId.value = industrialPcAssets.value[0].id;
      latestResult.value = null;
    }
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    loadingAssets.value = false;
  }
}

async function handleRunTest(mode: E2ERunMode = "manual") {
  if (requiresAssetSelection.value && !selectedAssetId.value) {
    errorMessage.value = "Selectionne d'abord un industrial PC.";
    return;
  }

  runningTest.value = true;
  errorMessage.value = null;

  try {
    latestResult.value = await runE2ETest({
      asset_id: requiresAssetSelection.value ? selectedAssetId.value : null,
      site_id: routeSiteId.value,
      flow_key: selectedFlowKey.value,
      sample_count: mode === "manual" ? selectedSampleCount.value : 1,
      sample_interval_seconds: mode === "manual" ? selectedSampleIntervalSeconds.value : 0,
    });
    if (latestResult.value) {
      appendTrendPoints(latestResult.value, mode);
    }
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    runningTest.value = false;
    if (autoModeEnabled.value) {
      scheduleNextAutoRun();
    }
  }
}

function selectRunMode(mode: E2ERunMode) {
  if (selectedRunMode.value === mode) {
    return;
  }
  if (autoModeEnabled.value) {
    stopAutoMode();
  }
  selectedRunMode.value = mode;
}

function handleAutoModeLaunchToggle() {
  selectedRunMode.value = "auto";
  if (autoModeEnabled.value) {
    stopAutoMode();
    return;
  }
  autoModeEnabled.value = true;
  errorMessage.value = null;
  if (runningTest.value) {
    scheduleNextAutoRun();
    return;
  }
  void handleRunTest("auto");
}

function handleLaunchCurrentMode() {
  if (isManualMode.value) {
    void handleRunTest("manual");
    return;
  }
  handleAutoModeLaunchToggle();
}

watch(
  () => route.params.siteId,
  () => {
    stopAutoMode();
    resetTrendHistory();
    void loadAssets();
  },
);

watch(selectedAssetId, (nextValue, previousValue) => {
  if (previousValue !== undefined && nextValue !== previousValue) {
    stopAutoMode();
    resetTrendHistory();
  }
  if (selectedFlowKey.value !== "ems_site") {
    return;
  }
  if (latestResult.value?.asset && latestResult.value.asset.id !== nextValue) {
    latestResult.value = null;
  }
});

watch(selectedFlowKey, () => {
  stopAutoMode();
  resetTrendHistory();
  errorMessage.value = null;
  latestResult.value = null;
  noticeMessage.value =
    selectedFlowKey.value === "ems_light" || routeSiteId.value
      ? null
      : "Le site courant n'a pas d'identifiant numerique exploitable cote API. La liste affiche tous les industrial PCs actifs.";
});

watch(selectedAutoIntervalSeconds, () => {
  if (autoModeEnabled.value) {
    scheduleNextAutoRun();
  }
});

onMounted(() => {
  void loadAssets();
});

onBeforeUnmount(() => {
  stopAutoMode();
});
</script>

<template>
  <section class="stack-card">
    <header class="page-heading">
      <div>
        <p class="muted-2 uppercase">NATS request/reply + monitoring</p>
        <h1>{{ pageTitle }}</h1>
        <p class="page-copy">{{ pageSubtitle }}</p>
      </div>
      <div class="page-actions">
        <button
          :class="['action-button', selectedRunMode === 'manual' ? '' : 'action-button--secondary']"
          type="button"
          @click="selectRunMode('manual')"
        >
          Mode manuel
        </button>
        <button
          :class="['action-button', selectedRunMode === 'auto' ? '' : 'action-button--secondary']"
          type="button"
          @click="selectRunMode('auto')"
        >
          Mode auto
        </button>
      </div>
    </header>

    <section class="control-shell">
      <label class="field-block">
        <span class="field-label">Flux</span>
        <select v-model="selectedFlowKey" :disabled="loadingAssets || runningTest">
          <option v-for="flow in flowOptions" :key="flow.key" :value="flow.key">
            {{ flow.label }} - {{ flow.description }}
          </option>
        </select>
      </label>
      <template v-if="isManualMode">
        <label class="field-block">
          <span class="field-label">Mesures</span>
          <select v-model="selectedSampleCount" :disabled="runningTest">
            <option v-for="count in sampleCountOptions" :key="count" :value="count">
              {{ count }} mesure{{ count > 1 ? "s" : "" }}
            </option>
          </select>
        </label>
        <label class="field-block">
          <span class="field-label">Cadence mesures</span>
          <select v-model="selectedSampleIntervalSeconds" :disabled="runningTest">
            <option v-for="seconds in sampleIntervalOptions" :key="seconds" :value="seconds">
              {{ seconds === 0 ? "immediate" : `1 mesure / ${seconds}s` }}
            </option>
          </select>
        </label>
      </template>
      <label v-else class="field-block">
        <span class="field-label">Frequence auto</span>
        <select v-model="selectedAutoIntervalSeconds" :disabled="runningTest && !autoModeEnabled">
          <option v-for="seconds in autoIntervalOptions" :key="seconds" :value="seconds">
            toutes les {{ seconds }} s
          </option>
        </select>
      </label>
      <label class="field-block">
        <template v-if="requiresAssetSelection">
          <span class="field-label">Industrial PC</span>
          <select v-model="selectedAssetId" :disabled="loadingAssets || runningTest">
            <option :value="null">Selectionner un IPC</option>
            <option v-for="asset in industrialPcAssets" :key="asset.id" :value="asset.id">
              {{ asset.site?.code ? `${asset.site.code} - ` : "" }}{{ asset.inventory_hostname }}
              {{ asset.management_ip ? `(${asset.management_ip})` : "" }}
            </option>
          </select>
        </template>
        <template v-else>
          <span class="field-label">Target</span>
          <div class="field-static">
            <strong>ems-light</strong>
            <span class="field-static-copy">Flux global singleton partage par tout le systeme</span>
          </div>
        </template>
      </label>
      <div class="field-hint">
        {{
          requiresAssetSelection
            ? (loadingAssets ? "Chargement des assets..." : `${industrialPcAssets.length} industrial PC(s) disponible(s)`)
            : "Aucune selection IPC necessaire pour ce flux global."
        }}
        {{ measurementBatch ? ` Derniere serie: ${measurementBatch.completed_count}/${measurementBatch.requested_count} mesure(s).` : "" }}
        {{ ` ${runModeExplanation}` }}
      </div>
    </section>

    <section class="launch-shell">
      <div class="launch-copy">
        <span class="field-label">Execution</span>
        <strong>{{ isManualMode ? "Serie manuelle" : "Cycle auto" }}</strong>
        <span class="muted-copy">{{ launchButtonSubtitle }}</span>
      </div>
      <button
        class="action-button"
        type="button"
        :disabled="loadingAssets || (isManualMode && runningTest) || (requiresAssetSelection && !selectedAssetId)"
        @click="handleLaunchCurrentMode"
      >
        {{ launchButtonLabel }}
      </button>
    </section>

    <div v-if="noticeMessage" class="info-banner">
      {{ noticeMessage }}
    </div>
    <div v-if="errorMessage" class="error-banner">
      {{ errorMessage }}
    </div>
    <div v-for="warning in resultWarnings" :key="warning" class="warning-banner">
      {{ warning }}
    </div>

    <template v-if="probe">
      <section class="section-block">
        <div class="section-heading">
          <h2 class="section-title">Cascade du test actif</h2>
          <StatusBadge
            :label="probe.summary.reply_status ?? 'unknown'"
            :tone="statusTone(probe.summary.reply_status)"
          />
        </div>
        <p class="section-copy">
          {{ roundTripExplanation }}
        </p>
        <div class="cascade-shell">
        <div class="cascade-axis mono">
          <span>0 ms</span>
          <span>{{ formatLatency(activeCascadeTotalMs) }}</span>
        </div>

        <div class="cascade-legend">
          <span class="cascade-legend-item">
            <span class="cascade-legend-swatch cascade-legend-swatch--outbound" />
            trajet aller
          </span>
          <span class="cascade-legend-item">
            <span class="cascade-legend-swatch cascade-legend-swatch--return" />
            trajet retour
          </span>
        </div>

          <article class="cascade-row cascade-row--total">
            <div class="cascade-meta">
              <div>
                <h3 class="cascade-title">Temps total actif reconstruit</h3>
                <p class="cascade-copy">{{ roundTripSubtitle }}</p>
              </div>
              <div class="cascade-values">
                <span class="mono cascade-duration">{{ formatLatency(activeCascadeTotalMs) }}</span>
                <span class="mono muted-copy">{{ formatDurationWindow(0, activeCascadeTotalMs ?? 0) }}</span>
              </div>
            </div>
            <div class="cascade-track">
              <div class="cascade-bar cascade-bar--total tone-neutral" style="left: 0%; width: 100%" />
            </div>
          </article>

          <article
            v-for="row in activeCascadeRows"
            :key="row.key"
            class="cascade-row"
          >
            <div class="cascade-meta">
              <div>
                <h3 class="cascade-title">{{ row.label }}</h3>
                <p class="cascade-copy">{{ row.subtitle }}</p>
              </div>
              <div class="cascade-values">
                <span class="mono cascade-duration">{{ formatLatency(row.durationMs) }}</span>
                <span class="mono muted-copy">{{ formatDurationWindow(row.startMs, row.endMs) }}</span>
                <span v-if="row.outboundMs !== null && row.returnMs !== null" class="mono muted-copy">
                  {{ row.outboundLabel }} {{ formatLatency(row.outboundMs) }} / {{ row.returnLabel }} {{ formatLatency(row.returnMs) }}
                </span>
              </div>
            </div>
            <div class="cascade-track">
              <div
                class="cascade-bar cascade-bar--outbound"
                :style="{ left: `${row.outboundOffsetPct}%`, width: `${row.outboundWidthPct}%` }"
              />
              <div
                class="cascade-bar cascade-bar--return"
                :style="{ left: `${row.returnOffsetPct}%`, width: `${row.returnWidthPct}%` }"
              />
            </div>
            <p v-if="row.approximation" class="cascade-note">
              {{ row.approximation }}
            </p>
          </article>
        </div>
      </section>

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

      <section class="section-block">
        <div class="section-heading">
          <h2 class="section-title">Evolution du RTT dans le temps</h2>
          <div class="section-heading-actions">
            <StatusBadge
              :label="autoModeEnabled ? `auto / ${selectedAutoIntervalSeconds}s` : 'manuel'"
              :tone="autoModeEnabled ? 'healthy' : 'neutral'"
            />
            <button
              class="action-button action-button--secondary action-button--compact"
              type="button"
              :disabled="!trendHistory.length"
              @click="clearTrendGraph"
            >
              Reset graph
            </button>
          </div>
        </div>
        <p class="section-copy">
          Chaque point correspond a un batch complet. La courbe pleine suit le RTT actif avec traitement broker, la courbe en pointilles suit le RTT actif sans traitement broker.
          Les anneaux de point distinguent les runs manuels et auto pour garder un historique exploitable quand tu compares les series.
        </p>
        <div v-if="trendChart" class="trend-chart-shell">
          <div class="trend-chart-head">
            <div class="trend-chart-legend">
              <span class="trend-legend-item">
                <span class="trend-legend-line trend-legend-line--with-proxy" />
                RTT actif avec traitement broker
              </span>
              <span class="trend-legend-item">
                <span class="trend-legend-line trend-legend-line--without-proxy" />
                RTT actif sans traitement broker
              </span>
              <span class="trend-legend-item">
                <span class="trend-legend-point trend-legend-point--manual" />
                run manuel
              </span>
              <span class="trend-legend-item">
                <span class="trend-legend-point trend-legend-point--auto" />
                run auto
              </span>
            </div>
            <div class="trend-chart-summary mono">
              {{ trendHistory.length }} point(s) | de {{ formatDateTime(trendChart.startedAt) }} a {{ formatDateTime(trendChart.endedAt) }}
            </div>
          </div>

          <svg
            class="trend-chart"
            :viewBox="`0 0 ${trendChart.width} ${trendChart.height}`"
            preserveAspectRatio="none"
            role="img"
            aria-label="Evolution du RTT dans le temps"
          >
            <line
              v-for="guide in trendChart.guides"
              :key="guide.key"
              :x1="trendChart.plotLeft"
              :x2="trendChart.plotRight"
              :y1="guide.y"
              :y2="guide.y"
              class="trend-grid-line"
            />
            <line
              :x1="trendChart.plotLeft"
              :x2="trendChart.plotRight"
              :y1="trendChart.plotBottom"
              :y2="trendChart.plotBottom"
              class="trend-axis-line"
            />
            <line
              :x1="trendChart.plotLeft"
              :x2="trendChart.plotLeft"
              :y1="trendChart.plotTop"
              :y2="trendChart.plotBottom"
              class="trend-axis-line"
            />
            <text
              v-for="guide in trendChart.guides"
              :key="`${guide.key}-label`"
              :x="trendChart.plotLeft - 8"
              :y="guide.y + 4"
              class="trend-axis-label"
              text-anchor="end"
            >
              {{ formatLatency(guide.value) }}
            </text>
            <path
              v-if="trendChart.withProxyPath"
              :d="trendChart.withProxyPath"
              class="trend-series trend-series--with-proxy"
            />
            <path
              v-if="trendChart.withoutProxyPath"
              :d="trendChart.withoutProxyPath"
              class="trend-series trend-series--without-proxy"
            />

            <g v-for="point in trendChart.points" :key="point.id">
              <circle
                v-if="point.yWithProxy !== null"
                :cx="point.x"
                :cy="point.yWithProxy"
                r="4.8"
                :class="['trend-point', 'trend-point--with-proxy', point.mode === 'auto' ? 'trend-point--auto' : 'trend-point--manual']"
              >
                <title>
                  {{ `${point.tooltipLabel} | avec traitement broker ${formatLatency(point.totalWithProxyMs)}` }}
                </title>
              </circle>
              <circle
                v-if="point.yWithoutProxy !== null"
                :cx="point.x"
                :cy="point.yWithoutProxy"
                r="4"
                :class="['trend-point', 'trend-point--without-proxy', point.mode === 'auto' ? 'trend-point--auto' : 'trend-point--manual']"
              >
                <title>
                  {{ `${point.tooltipLabel} | sans traitement broker ${formatLatency(point.totalWithoutProxyMs)}` }}
                </title>
              </circle>
            </g>

            <text
              :x="trendChart.plotLeft"
              :y="trendChart.height - 10"
              class="trend-axis-label"
              text-anchor="start"
            >
              {{ formatDateTime(trendChart.startedAt) }}
            </text>
            <text
              :x="trendChart.plotRight"
              :y="trendChart.height - 10"
              class="trend-axis-label"
              text-anchor="end"
            >
              {{ formatDateTime(trendChart.endedAt) }}
            </text>
          </svg>

          <div class="trend-chart-foot">
            <span v-if="latestTrendPoint" class="mono">
              Dernier point: {{ latestTrendPoint.mode === "auto" ? "auto" : "manuel" }} |
              avec traitement broker {{ formatLatency(latestTrendPoint.totalWithProxyMs) }} |
              sans traitement broker {{ formatLatency(latestTrendPoint.totalWithoutProxyMs) }}
            </span>
          </div>
        </div>
        <div v-else class="empty-shell">
          Lance un premier run en manuel ou en auto pour commencer le tracage du RTT dans le temps.
        </div>
      </section>

      <section v-if="measurementBatch" class="section-block">
        <div class="section-heading">
          <h2 class="section-title">Serie de mesures</h2>
          <StatusBadge
            :label="`${measurementBatch.completed_count}/${measurementBatch.requested_count} completees`"
            tone="neutral"
          />
        </div>
        <p class="section-copy">
          Le probe affiche ici l'echantillon representatif #{{ measurementBatch.representative_index }}.
          Les agregats ci-dessous sont calcules sur toute la serie et serviront a affiner plus tard la decoupe des segments RTT.
          Cadence du batch: {{ measurementBatch.sample_interval_seconds ? `1 mesure / ${measurementBatch.sample_interval_seconds}s` : "immediate" }}.
        </p>
        <div class="table-shell">
          <table class="history-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Count</th>
                <th>Min</th>
                <th>Avg</th>
                <th>Median</th>
                <th>P95</th>
                <th>Max</th>
                <th>Std dev</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="stat in measurementBatch.stats" :key="stat.key">
                <td>
                  <div class="connection-name">{{ stat.label }}</div>
                  <div class="mono muted-copy">{{ stat.key }}</div>
                </td>
                <td class="mono">{{ formatInteger(stat.count) }}</td>
                <td class="mono">{{ formatLatency(stat.min_ms) }}</td>
                <td class="mono">{{ formatLatency(stat.avg_ms) }}</td>
                <td class="mono">{{ formatLatency(stat.median_ms) }}</td>
                <td class="mono">{{ formatLatency(stat.p95_ms) }}</td>
                <td class="mono">{{ formatLatency(stat.max_ms) }}</td>
                <td class="mono">{{ formatLatency(stat.stddev_ms) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="section-block">
        <div class="section-heading">
          <h2 class="section-title">Canaux NATS distincts</h2>
        </div>
        <p class="section-copy">
          <template v-if="currentFlowKey === 'ems_light'">
            <span class="mono">ems-light</span> est observe ici via la connexion <span class="mono">iec104-bridge</span> cote broker.
            Son RTT vient de <span class="mono">/connz</span> et sert a observer le lien broker -> ems-light.
          </template>
          <template v-else>
            <span class="mono">gateway_modbus</span> et <span class="mono">telemetry_publisher</span> sont deux connexions NATS separees. Leurs RTT viennent de
            <span class="mono">/connz</span>. Le client <span class="mono">Broker-local probe</span> est un client NATS ephemere cree dans le broker pour lancer le watchdog:
            son RTT sert a verifier la reactivite locale du broker NATS, pas a mesurer le trajet vers l'IPC. Dans la cascade active, seul <span class="mono">gateway_modbus</span>
            est utilise pour reconstituer le segment broker -> industrial PC. <span class="mono">telemetry_publisher</span> reste un canal de publication distinct, utile pour observer
            la sante du flux telemetrie, mais non additif avec le request/reply de commande. Comme <span class="mono">telemetry_publisher</span> est un client publish-only qui boucle
            sur plusieurs lectures Modbus synchrones avant chaque publication, son RTT <span class="mono">/connz</span> mesure surtout la rapidite avec laquelle son event loop rend la main
            au client NATS pour repondre aux ping/pong du broker. Une valeur tres haute ici indique plutot un blocage local ou un polling Modbus lent qu'une latence metier utile du hot flow.
          </template>
        </p>
        <section class="metric-grid metric-grid--compact">
          <MetricCard
            v-for="metric in channelSnapshotMetrics"
            :key="metric.title"
            :title="metric.title"
            :value="metric.value"
            :subtitle="metric.subtitle"
            :tone="metric.tone"
          />
        </section>
      </section>

      <section class="section-block">
        <div class="section-heading">
          <h2 class="section-title">Broker monitoring</h2>
          <StatusBadge
            :label="probe.monitoring.available ? 'monitoring ready' : 'monitoring partial'"
            :tone="probe.monitoring.available ? 'healthy' : 'warning'"
          />
        </div>
        <div class="metric-grid">
          <div :title="probe.monitoring.url ?? ''">
            <MetricCard :title="monitoringUrlTitle" :value="monitoringUrlValue" :subtitle="monitoringUrlSubtitle" tone="neutral" />
          </div>
          <div :title="probe.monitoring.varz?.server_name ?? ''">
            <MetricCard
              title="Broker name"
              :value="brokerNameValue"
              :subtitle="probe.monitoring.varz?.version ?? 'version n/a'"
              tone="neutral"
            />
          </div>
          <MetricCard
            title="Connections"
            :value="formatInteger(probe.monitoring.varz?.connections)"
            :subtitle="`Total: ${formatInteger(probe.monitoring.varz?.total_connections)}`"
            tone="neutral"
          />
          <MetricCard
            title="Slow consumers"
            :value="formatInteger(probe.monitoring.varz?.slow_consumers)"
            :subtitle="`Routes: ${formatInteger(probe.monitoring.varz?.routes)}`"
            :tone="(probe.monitoring.varz?.slow_consumers ?? 0) > 0 ? 'warning' : 'healthy'"
          />
        </div>
        <div class="table-shell">
          <table class="history-table">
            <thead>
              <tr>
                <th>Connection</th>
                <th>RTT</th>
                <th>Pending bytes</th>
                <th>In msgs</th>
                <th>Out msgs</th>
                <th>Subscriptions</th>
                <th>Uptime</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in monitoringConnections" :key="row.key">
                <td>
                  <div class="connection-name">{{ row.label }}</div>
                  <div class="muted-copy">{{ row.description }}</div>
                  <div class="mono muted-copy">{{ row.connection?.name ?? "n/a" }}</div>
                </td>
                <td class="mono">{{ formatLatency(row.connection?.rtt_ms) }}</td>
                <td class="mono">{{ formatInteger(row.connection?.pending_bytes) }}</td>
                <td class="mono">{{ formatInteger(row.connection?.in_msgs) }}</td>
                <td class="mono">{{ formatInteger(row.connection?.out_msgs) }}</td>
                <td class="mono">{{ formatInteger(row.connection?.subscriptions) }}</td>
                <td class="mono">{{ row.connection?.uptime ?? "n/a" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="payload-grid">
        <article class="payload-card">
          <header class="payload-heading">
            <h2 class="section-title">{{ currentFlowKey === "ems_light" ? "Probe payload" : "Request payload" }}</h2>
            <span class="mono muted-copy">{{ probe.request_id }}</span>
          </header>
          <pre class="payload-shell">{{ formatJson(probe.request_payload) }}</pre>
        </article>

        <article class="payload-card">
          <header class="payload-heading">
            <h2 class="section-title">{{ currentFlowKey === "ems_light" ? "Observed connection" : "Reply payload" }}</h2>
            <span class="mono muted-copy">{{ formatDateTime(probe.tested_at) }}</span>
          </header>
          <pre class="payload-shell">{{ formatJson(probe.reply_payload) }}</pre>
        </article>
      </section>
    </template>

    <section v-else class="empty-shell">
      <h2 class="section-title">Pas encore de mesure live</h2>
      <p>
        <template v-if="selectedFlowKey === 'ems_light'">
          Le test observera le flux global <span class="mono">Control Panel -> Broker -> ems-light</span>, puis recoupera
          les informations du broker via <span class="mono">/connz</span>, <span class="mono">/varz</span> et <span class="mono">/healthz</span>.
        </template>
        <template v-else>
          Le test enverra une requete NATS sur <span class="mono">cascadya.routing.ping</span>, attendra la
          reponse de l'IPC, puis recoupera les informations du broker via
          <span class="mono">/connz</span>, <span class="mono">/varz</span> et <span class="mono">/healthz</span>
          quand ces endpoints sont accessibles.
        </template>
      </p>
    </section>
  </section>
</template>

<style scoped>
.uppercase {
  margin-bottom: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.76rem;
}

.page-copy {
  margin-top: 0.75rem;
  max-width: 56rem;
  color: var(--muted);
  font-size: 1.05rem;
}

.control-shell {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 14rem)) auto;
  gap: 1rem 1.4rem;
  align-items: end;
}

.page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  align-items: center;
}

.action-button--secondary {
  background: rgba(16, 22, 26, 0.9);
  border-color: rgba(120, 155, 173, 0.32);
}

.action-button--compact {
  min-height: auto;
  padding: 0.72rem 0.95rem;
}

.field-block {
  display: grid;
  gap: 0.55rem;
}

.field-label {
  color: var(--muted);
  font-size: 0.88rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.field-block select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: rgba(10, 12, 13, 0.92);
  color: var(--text);
  padding: 0.95rem 1rem;
}

.field-static {
  display: grid;
  gap: 0.35rem;
  min-height: 3.4rem;
  padding: 0.95rem 1rem;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: rgba(10, 12, 13, 0.92);
  color: var(--text);
}

.field-static-copy {
  color: var(--muted);
  font-size: 0.92rem;
}

.field-hint {
  color: var(--muted);
}

.launch-shell {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 1rem;
  padding: 1rem 1.15rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(10, 12, 13, 0.78);
}

.launch-copy {
  display: grid;
  gap: 0.25rem;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: 1.3rem;
}

.metric-grid--compact {
  gap: 1rem;
}

.section-block {
  display: grid;
  gap: 1rem;
}

.section-copy {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.section-heading-actions {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  flex-wrap: wrap;
}

.cascade-shell {
  display: grid;
  gap: 1rem;
  padding: 1.4rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(9, 10, 12, 0.97), rgba(6, 7, 8, 0.94));
}

.cascade-axis {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  font-size: 0.88rem;
}

.cascade-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  color: var(--muted);
  font-size: 0.88rem;
}

.cascade-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.cascade-legend-swatch {
  width: 1rem;
  height: 0.55rem;
  border-radius: 999px;
}

.cascade-legend-swatch--outbound {
  background: linear-gradient(90deg, rgba(54, 133, 205, 0.92), rgba(76, 170, 221, 0.94));
}

.cascade-legend-swatch--return {
  background: linear-gradient(90deg, rgba(82, 154, 69, 0.92), rgba(133, 198, 92, 0.94));
}

.cascade-row {
  display: grid;
  gap: 0.8rem;
}

.cascade-row--total {
  margin-bottom: 0.35rem;
}

.cascade-meta {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 1rem;
}

.cascade-title {
  margin: 0;
  font-size: 1rem;
}

.cascade-copy {
  margin: 0.35rem 0 0;
  color: var(--muted);
}

.cascade-values {
  display: grid;
  justify-items: end;
  gap: 0.2rem;
  text-align: right;
}

.cascade-duration {
  font-size: 1rem;
  color: var(--text);
}

.cascade-track {
  position: relative;
  height: 1.2rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.05);
  overflow: hidden;
}

.cascade-bar {
  position: absolute;
  top: 0.1rem;
  bottom: 0.1rem;
  min-width: 0.2rem;
  border-radius: 999px;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06) inset;
}

.cascade-bar--total {
  background: linear-gradient(90deg, rgba(96, 107, 124, 0.96), rgba(133, 145, 165, 0.92));
}

.cascade-bar--outbound {
  background: linear-gradient(90deg, rgba(54, 133, 205, 0.94), rgba(76, 170, 221, 0.92));
}

.cascade-bar--return {
  background: linear-gradient(90deg, rgba(82, 154, 69, 0.94), rgba(133, 198, 92, 0.92));
}

.cascade-note {
  margin: 0;
  color: var(--muted);
  font-size: 0.88rem;
}

.trend-chart-shell {
  display: grid;
  gap: 1rem;
  padding: 1.3rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(8, 10, 11, 0.96), rgba(5, 6, 7, 0.94));
}

.trend-chart-head,
.trend-chart-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.trend-chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.9rem 1.25rem;
}

.trend-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  color: var(--muted);
  font-size: 0.9rem;
}

.trend-legend-line {
  width: 1.4rem;
  height: 0;
  border-top-width: 3px;
  border-top-style: solid;
  border-radius: 999px;
}

.trend-legend-line--with-proxy {
  border-top-color: rgba(237, 156, 75, 0.98);
}

.trend-legend-line--without-proxy {
  border-top-color: rgba(97, 163, 255, 0.98);
  border-top-style: dashed;
}

.trend-legend-point {
  width: 0.8rem;
  height: 0.8rem;
  border-radius: 999px;
  background: rgba(15, 17, 18, 0.96);
  border: 2px solid transparent;
}

.trend-legend-point--manual {
  border-color: rgba(216, 228, 238, 0.92);
}

.trend-legend-point--auto {
  border-color: rgba(111, 202, 116, 0.95);
}

.trend-chart-summary {
  color: var(--muted);
  font-size: 0.9rem;
}

.trend-chart {
  width: 100%;
  height: 18rem;
  overflow: visible;
}

.trend-grid-line {
  stroke: rgba(255, 255, 255, 0.08);
  stroke-dasharray: 4 6;
}

.trend-axis-line {
  stroke: rgba(255, 255, 255, 0.16);
}

.trend-axis-label {
  fill: rgba(212, 222, 229, 0.88);
  font-size: 11px;
}

.trend-series {
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 3;
}

.trend-series--with-proxy {
  stroke: rgba(237, 156, 75, 0.98);
}

.trend-series--without-proxy {
  stroke: rgba(97, 163, 255, 0.98);
  stroke-dasharray: 7 6;
}

.trend-point {
  stroke-width: 2.4;
}

.trend-point--with-proxy {
  fill: rgba(237, 156, 75, 0.98);
}

.trend-point--without-proxy {
  fill: rgba(97, 163, 255, 0.98);
}

.trend-point--manual {
  stroke: rgba(224, 232, 238, 0.95);
}

.trend-point--auto {
  stroke: rgba(111, 202, 116, 0.95);
}

.table-shell {
  overflow: hidden;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(9, 10, 11, 0.96), rgba(6, 7, 8, 0.94));
}

.history-table thead th {
  padding: 1rem 1.25rem;
  color: var(--muted);
  border-bottom: 1px solid var(--line);
  text-align: left;
}

.history-table tbody td {
  padding: 1.05rem 1.25rem;
  border-bottom: 1px solid var(--line);
  color: var(--text);
  vertical-align: top;
}

.connection-name {
  font-weight: 700;
}

.payload-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.3rem;
}

.payload-card {
  display: grid;
  gap: 0.9rem;
  padding: 1.3rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(11, 13, 14, 0.97), rgba(7, 8, 9, 0.94));
}

.payload-heading {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
}

.payload-shell {
  margin: 0;
  padding: 1rem;
  border-radius: 0.9rem;
  background: rgba(2, 4, 5, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.04);
  color: var(--text);
  overflow: auto;
  font-size: 0.92rem;
}

.empty-shell,
.info-banner,
.warning-banner,
.error-banner {
  padding: 1.1rem 1.25rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
}

.empty-shell {
  background: rgba(10, 12, 13, 0.78);
}

.info-banner {
  background: rgba(24, 57, 102, 0.26);
  border-color: rgba(64, 131, 226, 0.24);
}

.warning-banner {
  background: rgba(114, 84, 14, 0.28);
  border-color: rgba(214, 166, 54, 0.24);
}

.error-banner {
  background: rgba(112, 30, 26, 0.28);
  border-color: rgba(208, 81, 76, 0.26);
}

.muted-copy {
  color: var(--muted);
}

@media (max-width: 1200px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .payload-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .control-shell,
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .section-heading,
  .payload-heading,
  .cascade-meta,
  .trend-chart-head,
  .trend-chart-foot {
    align-items: start;
    flex-direction: column;
  }

  .cascade-values {
    justify-items: start;
    text-align: left;
  }

  .section-heading-actions {
    align-items: start;
  }

  .launch-shell {
    align-items: start;
    flex-direction: column;
  }

  .table-shell {
    overflow-x: auto;
  }

  .history-table {
    min-width: 920px;
  }
}
</style>
