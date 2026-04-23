<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { fetchLiveAlerts } from "@/api/alerts";
import MetricCard from "@/components/ui/MetricCard.vue";
import PanelCard from "@/components/ui/PanelCard.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { useSessionStore } from "@/stores/session";
import type { ApiAlertsSourcePayload, ApiLiveAlertPayload, BadgeTone, DashboardMetric } from "@/types/controlPlane";

type AlertSeverity = "critical" | "warning" | "degraded" | "info";
type AlertState = "new" | "acknowledged" | "ignored" | "resolved";
type AlertSource = "Wazuh" | "Grafana" | "Mimir" | "Loki" | "Control Panel";

interface AlertComment {
  id: string;
  author: string;
  message: string;
  createdAt: string;
}

interface AlertLink {
  id: string;
  label: string;
  helper: string;
  kind: "internal" | "external";
  route?: {
    name: string;
    params?: Record<string, string>;
  };
  href?: string;
  configured: boolean;
}

interface AlertRecord {
  id: string;
  title: string;
  summary: string;
  source: AlertSource;
  severity: AlertSeverity;
  priority: 1 | 2 | 3 | 4;
  state: AlertState;
  raisedAt: string;
  company: string;
  siteLabel: string;
  region: string;
  ownerHint: string;
  nextStep: string;
  tags: string[];
  comments: AlertComment[];
  links: AlertLink[];
}

const ALERTS_STORAGE_KEY = "auth-prototype.alerts.prototype-state";

const router = useRouter();
const session = useSessionStore();

const searchQuery = ref("");
const severityFilter = ref<AlertSeverity | "all">("all");
const sourceFilter = ref<AlertSource | "all">("all");
const stateFilter = ref<AlertState | "open" | "all">("open");
const commentDrafts = ref<Record<string, string>>({});
const alerts = ref<AlertRecord[]>([]);
const noticeMessage = ref<string | null>(null);
const alertsLoading = ref(false);
const alertsSource = ref<ApiAlertsSourcePayload | null>(null);

function buildWazuhDashboardLink(id: string): AlertLink {
  const url = session.wazuhDashboardUrl?.trim() || null;

  return {
    id,
    label: "Dashboard Wazuh",
    helper: url
      ? "Ouvrir le dashboard Wazuh dans un nouvel onglet."
      : "URL du dashboard Wazuh non configuree dans le control panel.",
    kind: "external",
    href: url ?? undefined,
    configured: url !== null,
  };
}

function buildSeededAlerts(): AlertRecord[] {
  return [
    {
      id: "alert-wazuh-agent",
      title: "Agent IPC absent dans Wazuh",
      summary:
        "L'agent securite de l'IPC n'a pas remonte depuis plus de 15 minutes. L'alerte doit rediriger vers la vue site puis vers le workflow de remediation.",
      source: "Wazuh",
      severity: "critical",
      priority: 1,
      state: "new",
      raisedAt: "2026-04-03T08:05:00Z",
      company: "Nord Energie",
      siteLabel: "IPC vapeur 10-109",
      region: "Hauts-de-France",
      ownerHint: "Equipe exploitation / cyber",
      nextStep: "Verifier la connectivite IPC puis l'etat du service wazuh-agent.",
      tags: ["wazuh", "ipc", "agent"],
      comments: [],
      links: [
        buildWazuhDashboardLink("link-wazuh-dashboard"),
        {
          id: "link-wazuh-provisioning",
          label: "Provisioning",
          helper: "Relancer ensuite le playbook cible si besoin.",
          kind: "internal",
          route: { name: "provisioning-center" },
          configured: true,
        },
      ],
    },
    {
      id: "alert-rtt-p95",
      title: "RTT actif p95 au-dessus du seuil",
      summary:
        "Le flux chaud Control Panel -> Broker -> IPC montre un P95 anormalement haut. L'operateur doit ouvrir la page E2E pour distinguer reseau et traitement broker.",
      source: "Grafana",
      severity: "warning",
      priority: 2,
      state: "new",
      raisedAt: "2026-04-03T08:18:00Z",
      company: "Nord Energie",
      siteLabel: "SteamSwitch site Nord",
      region: "Hauts-de-France",
      ownerHint: "Equipe exploitation",
      nextStep: "Comparer RTT avec et sans traitement broker, puis verifier le segment broker -> IPC.",
      tags: ["rtt", "e2e", "latence"],
      comments: [],
      links: [
        {
          id: "link-rtt-e2e",
          label: "Test E2E",
          helper: "Ouvrir la page de diagnostic temps reel.",
          kind: "internal",
          route: { name: "e2e-center" },
          configured: true,
        },
        {
          id: "link-rtt-orders",
          label: "Orders",
          helper: "Verifier si les commandes request/reply repondent toujours.",
          kind: "internal",
          route: { name: "orders-center" },
          configured: true,
        },
        {
          id: "link-rtt-grafana",
          label: "Grafana",
          helper: "Base URL Grafana et mapping panel a definir.",
          kind: "external",
          configured: false,
        },
      ],
    },
    {
      id: "alert-noresponders",
      title: "NoRespondersError sur le watchdog NATS",
      summary:
        "Le broker a bien recu la requete, mais aucun subscriber n'etait present sur le sujet request/reply. Ce cas est prioritaire car il indique souvent une perte du edge-agent ou du chemin Modbus.",
      source: "Loki",
      severity: "critical",
      priority: 1,
      state: "acknowledged",
      raisedAt: "2026-04-03T08:02:00Z",
      company: "Nord Energie",
      siteLabel: "IPC vapeur 10-109",
      region: "Hauts-de-France",
      ownerHint: "Equipe exploitation / IPC",
      nextStep: "Verifier d'abord gateway_modbus, telemetry_publisher, puis /connz cote broker.",
      tags: ["loki", "nats", "noresponders"],
      comments: [
        {
          id: "comment-noresponders-1",
          author: "Daniel",
          message: "Incident deja observe apres reboot du simulateur Modbus.",
          createdAt: "2026-04-03T08:10:00Z",
        },
      ],
      links: [
        {
          id: "link-noresponders-orders",
          label: "Orders",
          helper: "Verifier le watchdog ping et les commandes.",
          kind: "internal",
          route: { name: "orders-center" },
          configured: true,
        },
        {
          id: "link-noresponders-e2e",
          label: "Test E2E",
          helper: "Rejouer un probe request/reply cible.",
          kind: "internal",
          route: { name: "e2e-center" },
          configured: true,
        },
        {
          id: "link-noresponders-loki",
          label: "Loki",
          helper: "Requete de logs et deeplink a definir.",
          kind: "external",
          configured: false,
        },
      ],
    },
    {
      id: "alert-wazuh-disk",
      title: "Disque data Wazuh au-dessus du seuil de capacite",
      summary:
        "Le volume data du manager Wazuh approche de la saturation. Cette alerte doit renvoyer vers la console Wazuh ou Grafana infra pour voir l'evolution.",
      source: "Mimir",
      severity: "degraded",
      priority: 2,
      state: "new",
      raisedAt: "2026-04-03T07:55:00Z",
      company: "Plateforme",
      siteLabel: "wazuh-Dev1-S",
      region: "Infra centrale",
      ownerHint: "Equipe plateforme",
      nextStep: "Verifier occupation du disque data, rotation logs et politique retention indexer.",
      tags: ["mimir", "wazuh", "capacity"],
      comments: [],
      links: [buildWazuhDashboardLink("link-wazuh-dashboard-2")],
    },
    {
      id: "alert-ipc-routing",
      title: "Routage IPC non persiste apres redemarrage",
      summary:
        "Le mapping d'interfaces enp2s0 / enp3s0 a ete perdu apres reboot. L'alerte doit conduire l'operateur a reprendre le playbook de persistance reseau.",
      source: "Control Panel",
      severity: "warning",
      priority: 3,
      state: "resolved",
      raisedAt: "2026-04-03T06:45:00Z",
      company: "Nord Energie",
      siteLabel: "IPC vapeur 10-109",
      region: "Hauts-de-France",
      ownerHint: "Equipe provisioning",
      nextStep: "Rejouer le playbook de persistance reseau et verifier le default route attendu.",
      tags: ["provisioning", "routing", "ipc"],
      comments: [
        {
          id: "comment-routing-1",
          author: "Daniel",
          message: "Cause racine identifiee : inversion entre enp2s0 et enp3s0.",
          createdAt: "2026-04-03T07:02:00Z",
        },
      ],
      links: [
        {
          id: "link-routing-provisioning",
          label: "Provisioning",
          helper: "Rouvrir le workflow et relancer la persistance reseau.",
          kind: "internal",
          route: { name: "provisioning-center" },
          configured: true,
        },
        {
          id: "link-routing-e2e",
          label: "Test E2E",
          helper: "Verifier ensuite que le RTT request/reply est revenu.",
          kind: "internal",
          route: { name: "e2e-center" },
          configured: true,
        },
      ],
    },
    {
      id: "alert-telemetry-backlog",
      title: "Backlog de logs sur telemetry_publisher",
      summary:
        "Le flux telemetrie montre des lenteurs ou des blocages intermittents. L'objectif est surtout de savoir ou aller pour investiguer ensuite sans rester sur plusieurs consoles.",
      source: "Grafana",
      severity: "info",
      priority: 4,
      state: "ignored",
      raisedAt: "2026-04-03T06:20:00Z",
      company: "Nord Energie",
      siteLabel: "SteamSwitch site Nord",
      region: "Hauts-de-France",
      ownerHint: "Equipe exploitation",
      nextStep: "Verifier la pression remontee, le rythme publish et l'etat du lien NATS.",
      tags: ["telemetry", "publisher", "logs"],
      comments: [
        {
          id: "comment-telemetry-1",
          author: "Daniel",
          message: "A garder en bruit faible tant qu'on n'a pas les seuils definitifs.",
          createdAt: "2026-04-03T06:34:00Z",
        },
      ],
      links: [
        {
          id: "link-telemetry-orders",
          label: "Orders",
          helper: "Verifier si le flux chaud reste sain.",
          kind: "internal",
          route: { name: "orders-center" },
          configured: true,
        },
        {
          id: "link-telemetry-grafana",
          label: "Grafana",
          helper: "Panel logs / metriques a raccorder.",
          kind: "external",
          configured: false,
        },
      ],
    },
  ];
}

const seededAlerts = computed<AlertRecord[]>(() => buildSeededAlerts());

function cloneAlertRecord(alert: AlertRecord): AlertRecord {
  return {
    ...alert,
    comments: alert.comments.map((comment) => ({ ...comment })),
    links: alert.links.map((link) => ({ ...link })),
    tags: [...alert.tags],
  };
}

function hydrateAlerts(baseAlerts: AlertRecord[]) {
  const storedState = readStoredAlertsState();
  alerts.value = baseAlerts.map((alert) => {
    const saved = storedState.get(alert.id);
    return {
      ...cloneAlertRecord(alert),
      state: saved?.state ?? alert.state,
      comments: saved?.comments ?? alert.comments.map((comment) => ({ ...comment })),
    };
  });
}

function mapApiAlertToRecord(payload: ApiLiveAlertPayload): AlertRecord {
  return {
    id: payload.id,
    title: payload.title,
    summary: payload.summary,
    source: payload.source,
    severity: payload.severity,
    priority: payload.priority,
    state: payload.state,
    raisedAt: payload.raised_at,
    company: payload.company,
    siteLabel: payload.site_label,
    region: payload.region,
    ownerHint: payload.owner_hint,
    nextStep: payload.next_step,
    tags: [...payload.tags],
    comments: [],
    links: [buildWazuhDashboardLink(`link-${payload.id}`)],
  };
}

function generateId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(Date.parse(value));
}

function normalizeSearch(value: string) {
  return value.trim().toLocaleLowerCase("fr-FR");
}

function formatRelativeAge(value: string) {
  const diffMs = Date.now() - Date.parse(value);
  const diffMinutes = Math.max(0, Math.round(diffMs / 60_000));
  if (diffMinutes < 1) {
    return "maintenant";
  }
  if (diffMinutes < 60) {
    return `${diffMinutes} min`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} h`;
  }

  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} j`;
}

function severityTone(severity: AlertSeverity): BadgeTone {
  switch (severity) {
    case "critical":
      return "admin";
    case "warning":
      return "warning";
    case "degraded":
      return "degraded";
    case "info":
      return "running";
  }
}

function sourceTone(source: AlertSource): BadgeTone {
  switch (source) {
    case "Wazuh":
      return "warning";
    case "Grafana":
      return "running";
    case "Mimir":
      return "degraded";
    case "Loki":
      return "admin";
    case "Control Panel":
      return "active";
  }
}

function stateTone(state: AlertState): BadgeTone {
  switch (state) {
    case "new":
      return "warning";
    case "acknowledged":
      return "running";
    case "resolved":
      return "healthy";
    case "ignored":
      return "neutral";
  }
}

function stateLabel(state: AlertState) {
  switch (state) {
    case "new":
      return "nouvelle";
    case "acknowledged":
      return "prise en compte";
    case "resolved":
      return "resolue";
    case "ignored":
      return "non prioritaire";
  }
}

function severityLabel(severity: AlertSeverity) {
  switch (severity) {
    case "critical":
      return "critique";
    case "warning":
      return "warning";
    case "degraded":
      return "degradee";
    case "info":
      return "information";
  }
}

function isActionable(state: AlertState) {
  return state === "new" || state === "acknowledged";
}

function readStoredAlertsState() {
  if (typeof window === "undefined") {
    return new Map<string, { state: AlertState; comments: AlertComment[] }>();
  }

  const rawValue = window.localStorage.getItem(ALERTS_STORAGE_KEY);
  if (!rawValue) {
    return new Map<string, { state: AlertState; comments: AlertComment[] }>();
  }

  try {
    const parsed = JSON.parse(rawValue) as Array<{
      id: string;
      state: AlertState;
      comments: AlertComment[];
    }>;
    return new Map(
      parsed.map((item) => [
        item.id,
        {
          state: item.state,
          comments: Array.isArray(item.comments) ? item.comments : [],
        },
      ]),
    );
  } catch {
    return new Map<string, { state: AlertState; comments: AlertComment[] }>();
  }
}

function persistAlertsState() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    ALERTS_STORAGE_KEY,
    JSON.stringify(
      alerts.value.map((alert) => ({
        id: alert.id,
        state: alert.state,
        comments: alert.comments,
      })),
    ),
  );
}

function resetPrototype() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(ALERTS_STORAGE_KEY);
  }

  hydrateAlerts(seededAlerts.value);
  commentDrafts.value = {};
  noticeMessage.value = "La file d'alertes prototype a ete reinitialisee.";
}

function setAlertState(alertId: string, nextState: AlertState) {
  alerts.value = alerts.value.map((alert) => (alert.id === alertId ? { ...alert, state: nextState } : alert));
  persistAlertsState();
}

function addComment(alertId: string) {
  const draft = commentDrafts.value[alertId]?.trim() ?? "";
  if (!draft) {
    noticeMessage.value = "Ajoute un commentaire avant de l'enregistrer.";
    return;
  }

  const author = session.user?.displayName ?? "Operateur";
  alerts.value = alerts.value.map((alert) =>
    alert.id === alertId
      ? {
          ...alert,
          comments: [
            ...alert.comments,
            {
              id: generateId("comment"),
              author,
              message: draft,
              createdAt: new Date().toISOString(),
            },
          ],
        }
      : alert,
  );

  commentDrafts.value = {
    ...commentDrafts.value,
    [alertId]: "",
  };

  persistAlertsState();
  noticeMessage.value = "Commentaire ajoute a l'alerte.";
}

function openAlertLink(link: AlertLink) {
  if (!link.configured) {
    noticeMessage.value = `${link.label} n'est pas encore raccorde.`;
    return;
  }

  if (link.kind === "internal" && link.route) {
    void router.push(link.route);
    return;
  }

  if (link.kind === "external" && link.href && typeof window !== "undefined") {
    window.open(link.href, "_blank", "noopener,noreferrer");
  }
}

const connectorLabel = computed(() => {
  if (session.demoModeEnabled) {
    return "demo frontend";
  }
  if (alertsSource.value?.healthy) {
    return "Wazuh live";
  }
  if (alertsSource.value?.configured) {
    return "degrade";
  }
  return "a configurer";
});

const connectorTone = computed<BadgeTone>(() => {
  if (session.demoModeEnabled) {
    return "running";
  }
  if (alertsSource.value?.healthy) {
    return "healthy";
  }
  if (alertsSource.value?.configured) {
    return "warning";
  }
  return "degraded";
});

async function loadAlerts() {
  if (session.demoModeEnabled) {
    alertsSource.value = {
      kind: "demo",
      configured: true,
      healthy: true,
      message: "Mode demo frontend actif. Les alertes affichees restent des donnees locales de prototype.",
    };
    hydrateAlerts(seededAlerts.value);
    return;
  }

  alertsLoading.value = true;
  try {
    const payload = await fetchLiveAlerts();
    alertsSource.value = payload.source;
    hydrateAlerts(payload.alerts.map(mapApiAlertToRecord));
  } catch (error) {
    alertsSource.value = {
      kind: "wazuh-indexer",
      configured: true,
      healthy: false,
      message:
        error instanceof Error
          ? `Impossible de charger les alertes Wazuh live: ${error.message}`
          : "Impossible de charger les alertes Wazuh live.",
    };
    alerts.value = [];
  } finally {
    alertsLoading.value = false;
  }
}

const availableSources = computed(() => Array.from(new Set(alerts.value.map((alert) => alert.source))));

const queueOrder = computed(() => {
  const actionable = [...alerts.value]
    .filter((alert) => isActionable(alert.state))
    .sort((left, right) => Date.parse(left.raisedAt) - Date.parse(right.raisedAt));

  return new Map(actionable.map((alert, index) => [alert.id, index + 1]));
});

const filteredAlerts = computed(() => {
  const query = normalizeSearch(searchQuery.value);

  return [...alerts.value]
    .filter((alert) => {
      if (severityFilter.value !== "all" && alert.severity !== severityFilter.value) {
        return false;
      }

      if (sourceFilter.value !== "all" && alert.source !== sourceFilter.value) {
        return false;
      }

      if (stateFilter.value === "open" && !isActionable(alert.state)) {
        return false;
      }

      if (stateFilter.value !== "all" && stateFilter.value !== "open" && alert.state !== stateFilter.value) {
        return false;
      }

      if (!query) {
        return true;
      }

      return [
        alert.title,
        alert.summary,
        alert.source,
        alert.company,
        alert.siteLabel,
        alert.region,
        alert.ownerHint,
        alert.nextStep,
        ...alert.tags,
      ].some((value) => normalizeSearch(value).includes(query));
    })
    .sort((left, right) => {
      const leftActionable = isActionable(left.state);
      const rightActionable = isActionable(right.state);

      if (leftActionable !== rightActionable) {
        return leftActionable ? -1 : 1;
      }

      if (leftActionable && rightActionable) {
        return Date.parse(left.raisedAt) - Date.parse(right.raisedAt);
      }

      return Date.parse(right.raisedAt) - Date.parse(left.raisedAt);
    });
});

const metrics = computed<DashboardMetric[]>(() => {
  const openAlerts = alerts.value.filter((alert) => isActionable(alert.state));
  const newAlerts = alerts.value.filter((alert) => alert.state === "new");
  const criticalAlerts = openAlerts.filter((alert) => alert.priority === 1);
  const resolvedAlerts = alerts.value.filter((alert) => alert.state === "resolved").length;

  return [
    {
      title: "File ouverte",
      value: String(openAlerts.length),
      subtitle: `${newAlerts.length} nouvelles a trier`,
      tone: openAlerts.length > 0 ? "warning" : "healthy",
    },
    {
      title: "Priorite P1",
      value: String(criticalAlerts.length),
      subtitle: "A traiter en premier dans la file FIFO",
      tone: criticalAlerts.length > 0 ? "warning" : "healthy",
    },
    {
      title: "Connecteur",
      value: session.demoModeEnabled ? "demo" : alertsSource.value?.healthy ? "Wazuh" : "0",
      subtitle: session.demoModeEnabled
        ? "Mode demo local pour le frontend"
        : alertsSource.value?.healthy
          ? "Flux live depuis l'indexer Wazuh prive"
          : "Connector Wazuh a configurer ou verifier",
      tone: session.demoModeEnabled ? "running" : alertsSource.value?.healthy ? "active" : "warning",
    },
    {
      title: "Resolues",
      value: String(resolvedAlerts),
      subtitle: session.demoModeEnabled
        ? "Historique local operateur pour ce prototype"
        : "Historique local de qualification dans le control panel",
      tone: resolvedAlerts > 0 ? "healthy" : "neutral",
    },
  ];
});

onMounted(() => {
  void loadAlerts();
});
</script>

<template>
  <section class="stack-card">
    <header class="page-heading">
      <div>
        <p class="muted-2 uppercase">Monitoring orchestration</p>
        <h1>Alertes</h1>
        <p class="section-copy">
          La page sert de point d'entree operateur pour les alertes Wazuh remontees via le backend du control panel,
          avec renvoi direct vers le dashboard Wazuh interne pour le detail et le triage.
        </p>
      </div>

      <div class="header-actions">
        <button class="button-secondary" type="button" @click="loadAlerts">
          {{ alertsLoading ? "Chargement..." : "Recharger les alertes" }}
        </button>
        <button v-if="session.demoModeEnabled" class="button-secondary" type="button" @click="resetPrototype">
          Reinitialiser la demo
        </button>
      </div>
    </header>

    <section v-if="noticeMessage" class="notice-shell notice-ok">
      {{ noticeMessage }}
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

    <section class="info-grid">
      <PanelCard :title="'Flux Wazuh'" :status="connectorLabel" :status-tone="connectorTone" :accent-tone="connectorTone">
        <p>Le control panel lit maintenant les alertes Wazuh recentes via son backend et ouvre le dashboard externe pour le detail.</p>
        <p>{{ alertsSource?.message ?? "En attente du premier chargement du flux Wazuh." }}</p>
      </PanelCard>

      <PanelCard title="Pilotage local" status="qualification locale" status-tone="active" accent-tone="active">
        <p>La prise en compte, la resolution et les commentaires restent locaux au control panel pour accelerer le tri operateur.</p>
        <p>Le detail securite, lui, reste consulte dans Wazuh via le bouton externe present sur chaque alerte.</p>
      </PanelCard>
    </section>

    <section class="section-block">
      <div class="section-heading">
        <div>
          <h2 class="section-title">File operateur</h2>
          <p class="section-copy">
            Les alertes ouvertes sont triees en FIFO par anciennete. Les plus anciennes alertes encore actionnables apparaissent en premier.
          </p>
        </div>
      </div>

      <div class="filter-grid">
        <input
          v-model="searchQuery"
          class="input-shell"
          type="search"
          placeholder="Rechercher une alerte, un site, une entreprise, une source..."
        />
        <select v-model="severityFilter" class="input-shell">
          <option value="all">Toutes les severites</option>
          <option value="critical">Critique</option>
          <option value="warning">Warning</option>
          <option value="degraded">Degradee</option>
          <option value="info">Information</option>
        </select>
        <select v-model="sourceFilter" class="input-shell">
          <option value="all">Toutes les sources</option>
          <option v-for="source in availableSources" :key="source" :value="source">{{ source }}</option>
        </select>
        <select v-model="stateFilter" class="input-shell">
          <option value="open">File ouverte</option>
          <option value="all">Tous les etats</option>
          <option value="new">Nouvelles</option>
          <option value="acknowledged">Prises en compte</option>
          <option value="resolved">Resolues</option>
          <option value="ignored">Non prioritaires</option>
        </select>
      </div>

      <div v-if="alertsLoading" class="empty-shell">
        <p>Chargement des alertes Wazuh...</p>
      </div>

      <div v-else-if="filteredAlerts.length === 0" class="empty-shell">
        <p v-if="session.demoModeEnabled">Aucune alerte ne correspond a la vue courante.</p>
        <p v-else>Aucune alerte Wazuh ne correspond a la vue courante.</p>
      </div>

      <div v-else class="alerts-grid">
        <article v-for="alert in filteredAlerts" :key="alert.id" class="alert-card">
          <div class="alert-topline">
            <div class="alert-title-block">
              <div class="alert-badges">
                <StatusBadge :label="`P${alert.priority}`" :tone="severityTone(alert.severity)" compact />
                <StatusBadge :label="severityLabel(alert.severity)" :tone="severityTone(alert.severity)" compact />
                <StatusBadge :label="alert.source" :tone="sourceTone(alert.source)" compact />
                <StatusBadge :label="stateLabel(alert.state)" :tone="stateTone(alert.state)" compact />
                <StatusBadge
                  v-if="queueOrder.has(alert.id)"
                  :label="`FIFO #${queueOrder.get(alert.id)}`"
                  tone="neutral"
                  compact
                />
              </div>
              <h3 class="alert-title">{{ alert.title }}</h3>
              <p class="alert-summary">{{ alert.summary }}</p>
            </div>

            <div class="alert-age">
              <span class="mono">{{ formatRelativeAge(alert.raisedAt) }}</span>
              <span class="muted-copy">{{ formatDateTime(alert.raisedAt) }}</span>
            </div>
          </div>

          <div class="alert-meta">
            <div>
              <span class="meta-label">Entreprise</span>
              <strong>{{ alert.company }}</strong>
            </div>
            <div>
              <span class="meta-label">Site / asset</span>
              <strong>{{ alert.siteLabel }}</strong>
            </div>
            <div>
              <span class="meta-label">Region</span>
              <strong>{{ alert.region }}</strong>
            </div>
            <div>
              <span class="meta-label">Owner suggere</span>
              <strong>{{ alert.ownerHint }}</strong>
            </div>
          </div>

          <div class="alert-next-step">
            <span class="meta-label">Action recommandee</span>
            <p>{{ alert.nextStep }}</p>
          </div>

          <div class="tag-stack">
            <span v-for="tag in alert.tags" :key="tag" class="chip-shell">#{{ tag }}</span>
          </div>

          <div class="link-grid">
            <button
              v-for="link in alert.links"
              :key="link.id"
              class="button-secondary link-button"
              :class="{ 'is-disabled': !link.configured }"
              type="button"
              @click="openAlertLink(link)"
            >
              <span>{{ link.label }}</span>
              <small>{{ link.helper }}</small>
            </button>
          </div>

          <div class="action-strip">
            <button class="button-secondary" type="button" @click="setAlertState(alert.id, 'acknowledged')">
              Prendre en compte
            </button>
            <button class="button-secondary" type="button" @click="setAlertState(alert.id, 'resolved')">
              Marquer resolue
            </button>
            <button class="button-danger" type="button" @click="setAlertState(alert.id, 'ignored')">
              Non prioritaire
            </button>
          </div>

          <div class="comment-panel">
            <div class="comment-editor">
              <textarea
                v-model="commentDrafts[alert.id]"
                class="text-shell"
                rows="3"
                placeholder="Ajouter un commentaire operateur, une hypothese ou une action prise..."
              />
              <button class="button-secondary" type="button" @click="addComment(alert.id)">Ajouter un commentaire</button>
            </div>

            <div v-if="alert.comments.length" class="comment-list">
              <article v-for="comment in alert.comments" :key="comment.id" class="comment-card">
                <div class="comment-head">
                  <strong>{{ comment.author }}</strong>
                  <span class="muted-copy mono">{{ formatDateTime(comment.createdAt) }}</span>
                </div>
                <p>{{ comment.message }}</p>
              </article>
            </div>
            <div v-else class="empty-shell compact-empty">
              <p>Aucun commentaire pour le moment.</p>
            </div>
          </div>
        </article>
      </div>
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

.header-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.8rem;
}

.metric-grid,
.info-grid,
.alerts-grid {
  display: grid;
  gap: 1.2rem;
}

.metric-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.info-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.section-block {
  display: grid;
  gap: 1rem;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.section-copy {
  margin: 0.35rem 0 0;
  color: var(--muted);
  line-height: 1.55;
  max-width: 78ch;
}

.notice-shell {
  padding: 1rem 1.2rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
}

.notice-ok {
  border-color: rgba(132, 212, 79, 0.28);
  color: var(--green);
  background: rgba(66, 111, 21, 0.18);
}

.empty-shell {
  padding: 1.1rem 1.25rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(10, 12, 13, 0.78);
}

.compact-empty {
  padding: 0.85rem 1rem;
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.5fr repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
}

.input-shell,
.text-shell {
  width: 100%;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}

.input-shell {
  min-height: 2.9rem;
  padding: 0.75rem 0.95rem;
}

select.input-shell {
  background: rgba(10, 12, 13, 0.92);
  color: var(--text);
  color-scheme: dark;
}

select.input-shell option {
  background: rgba(10, 12, 13, 0.98);
  color: var(--text);
}

.text-shell {
  min-height: 6.5rem;
  padding: 0.9rem 1rem;
  resize: vertical;
}

.input-shell::placeholder,
.text-shell::placeholder {
  color: var(--muted);
}

.alerts-grid {
  grid-template-columns: 1fr;
}

.alert-card {
  display: grid;
  gap: 1rem;
  padding: 1.25rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(10, 11, 13, 0.97), rgba(6, 7, 8, 0.94));
}

.alert-topline {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.alert-title-block {
  display: grid;
  gap: 0.7rem;
}

.alert-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.alert-title {
  margin: 0;
  font-size: 1.2rem;
}

.alert-summary {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
}

.alert-age {
  display: grid;
  justify-items: end;
  gap: 0.25rem;
  text-align: right;
}

.alert-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.9rem;
}

.meta-label {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--muted);
  font-size: 0.88rem;
}

.alert-next-step {
  padding: 0.95rem 1rem;
  border-radius: 1rem;
  border: 1px solid rgba(122, 168, 255, 0.18);
  background: rgba(47, 73, 114, 0.12);
}

.alert-next-step p {
  margin: 0.35rem 0 0;
  color: var(--text);
  line-height: 1.55;
}

.tag-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.chip-shell {
  display: inline-flex;
  align-items: center;
  min-height: 1.9rem;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
  font-size: 0.88rem;
}

.link-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: 0.8rem;
}

.action-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
}

.comment-panel {
  display: grid;
  grid-template-columns: minmax(17rem, 22rem) minmax(0, 1fr);
  gap: 1rem;
}

.comment-editor,
.comment-list {
  display: grid;
  gap: 0.8rem;
}

.comment-card {
  padding: 0.9rem 1rem;
  border-radius: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.025);
}

.comment-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  margin-bottom: 0.45rem;
}

.comment-card p {
  margin: 0;
  line-height: 1.55;
}

.button-secondary,
.button-danger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.85rem;
  padding: 0.75rem 1rem;
  border-radius: 999px;
  font-weight: 600;
  transition:
    transform 150ms ease,
    border-color 150ms ease,
    background 150ms ease;
}

.button-secondary {
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
}

.button-danger {
  border: 1px solid rgba(255, 154, 139, 0.28);
  background: rgba(123, 38, 33, 0.2);
  color: var(--red-soft);
}

.button-secondary:hover,
.button-danger:hover {
  transform: translateY(-1px);
}

.link-button {
  display: grid;
  justify-items: start;
  gap: 0.15rem;
  min-height: 4.5rem;
  border-radius: 1rem;
  text-align: left;
}

.link-button small {
  color: var(--muted);
  font-weight: 400;
  line-height: 1.35;
}

.link-button.is-disabled {
  opacity: 0.6;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace);
}

.muted-copy {
  color: var(--muted);
}

@media (max-width: 1200px) {
  .metric-grid,
  .info-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .alert-meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .metric-grid,
  .info-grid,
  .filter-grid,
  .alert-meta,
  .comment-panel {
    grid-template-columns: 1fr;
  }

  .section-heading,
  .alert-topline {
    flex-direction: column;
    align-items: flex-start;
  }

  .alert-age {
    justify-items: start;
    text-align: left;
  }
}
</style>
