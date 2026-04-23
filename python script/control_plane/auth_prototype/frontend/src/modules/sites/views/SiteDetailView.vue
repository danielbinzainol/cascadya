<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { ApiError } from "@/api/client";
import { fetchInventoryAssets, fetchProvisioningJobs, fetchSite } from "@/api/provisioning";
import MetricCard from "@/components/ui/MetricCard.vue";
import PanelCard from "@/components/ui/PanelCard.vue";
import ProgressBar from "@/components/ui/ProgressBar.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { statusTone } from "@/mocks/controlPlane";
import { useAppStore } from "@/stores/app";
import { useSessionStore } from "@/stores/session";
import type {
  ApiInventoryAssetPayload,
  ApiProvisioningJobPayload,
  ApiSitePayload,
  DashboardMetric,
} from "@/types/controlPlane";

const route = useRoute();
const appStore = useAppStore();
const session = useSessionStore();

const loading = ref(false);
const errorMessage = ref<string | null>(null);
const backendSite = ref<ApiSitePayload | null>(null);
const backendAssets = ref<ApiInventoryAssetPayload[]>([]);
const backendJobs = ref<ApiProvisioningJobPayload[]>([]);

const routeSiteId = computed(() => String(route.params.siteId ?? ""));
const routeSiteNumber = computed(() => {
  const parsed = Number.parseInt(routeSiteId.value, 10);
  return Number.isFinite(parsed) ? parsed : null;
});

const isDemo = computed(() => session.demoModeEnabled);
const demoSite = computed(() => appStore.getSite(routeSiteId.value));
const demoDetail = computed(() => appStore.getSiteDetail(routeSiteId.value));
const canRunE2E = computed(() => session.hasPermission("inventory:scan"));
const canRunProvisioning = computed(() => session.hasPermission("provision:prepare"));

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
    timeStyle: "short",
  }).format(parsed);
}

async function loadBackendSite() {
  if (isDemo.value) {
    return;
  }

  if (routeSiteNumber.value === null) {
    backendSite.value = null;
    backendAssets.value = [];
    backendJobs.value = [];
    errorMessage.value = "L'identifiant de site dans l'URL n'est pas valide.";
    return;
  }

  loading.value = true;
  errorMessage.value = null;

  try {
    const [site, assetsResponse, jobsResponse] = await Promise.all([
      fetchSite(routeSiteNumber.value),
      fetchInventoryAssets({ siteId: routeSiteNumber.value }),
      fetchProvisioningJobs({ siteId: routeSiteNumber.value }),
    ]);

    backendSite.value = site;
    backendAssets.value = assetsResponse.assets;
    backendJobs.value = jobsResponse.jobs;
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

const latestBackendJob = computed(() =>
  [...backendJobs.value].sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))[0] ?? null,
);

const backendMetrics = computed<DashboardMetric[]>(() => {
  if (!backendSite.value) {
    return [];
  }

  return [
    {
      title: "Statut du site",
      value: backendSite.value.status,
      subtitle: backendSite.value.is_active ? "site actif" : "site inactif",
      tone: statusTone(backendSite.value.status),
    },
    {
      title: "IPC actifs",
      value: `${backendSite.value.active_asset_count} / ${backendSite.value.asset_count}`,
      subtitle: "Assets enregistres sur le site",
      tone: backendSite.value.active_asset_count > 0 ? "healthy" : "waiting",
    },
    {
      title: "Dernier job",
      value: latestBackendJob.value?.status ?? "n/a",
      subtitle: latestBackendJob.value ? `#${latestBackendJob.value.id}` : "Aucun job",
      tone: statusTone(latestBackendJob.value?.status ?? "waiting"),
    },
    {
      title: "Fuseau horaire",
      value: backendSite.value.timezone,
      subtitle: backendSite.value.country || "n/a",
      tone: "neutral" as const,
    },
  ];
});

const backendServiceCards = computed(() => {
  if (!backendSite.value) {
    return [];
  }

  const latestJob = latestBackendJob.value;
  return [
    {
      name: "ems-site",
      status: latestJob?.status === "succeeded" ? "healthy" : backendSite.value.status,
      lines: [
        `Site code: ${backendSite.value.code}`,
        `Assets actifs: ${backendSite.value.active_asset_count}/${backendSite.value.asset_count}`,
        `Dernier job: ${latestJob?.status ?? "aucun"}`,
      ],
    },
    {
      name: "Provisioning",
      status: latestJob?.status ?? "waiting",
      lines: [
        `Execution mode: ${latestJob?.execution_mode ?? "n/a"}`,
        `Dernier workflow: ${latestJob?.playbook_name ?? "aucun"}`,
        `Termine: ${formatDateTime(latestJob?.finished_at ?? latestJob?.created_at)}`,
      ],
    },
  ];
});

const latestBackendProgressRatio = computed(() => {
  const progress = latestBackendJob.value?.context.progress;
  if (!progress?.total_steps) {
    return latestBackendJob.value?.status === "succeeded" ? 1 : 0;
  }
  return Math.min(Math.max(progress.completed_steps / progress.total_steps, 0), 1);
});

watch(
  () => route.params.siteId,
  () => {
    void loadBackendSite();
  },
);

onMounted(() => {
  void loadBackendSite();
});
</script>

<template>
  <section class="stack-card">
    <template v-if="isDemo">
      <header class="site-heading">
        <div class="site-heading-left">
          <RouterLink class="breadcrumb" :to="{ name: 'dashboard' }">Dashboard</RouterLink>
          <div class="title-line">
            <h1>{{ demoSite.name }}</h1>
            <StatusBadge :label="demoSite.status" :tone="statusTone(demoSite.status)" />
          </div>
          <p class="subtitle">
            {{ demoSite.city }} ({{ demoSite.code }}) - {{ demoSite.sector }} - {{ demoSite.capacityMw.toFixed(1) }} MW aFRR
          </p>
        </div>

        <div class="site-actions">
          <RouterLink
            v-if="canRunE2E"
            class="action-button"
            :to="{ name: 'site-e2e', params: { siteId: demoSite.siteId } }"
          >
            Test E2E
          </RouterLink>
          <RouterLink
            v-if="canRunProvisioning"
            class="action-button"
            :to="{ name: 'site-provisioning', params: { siteId: demoSite.siteId } }"
          >
            Jobs
          </RouterLink>
        </div>
      </header>

      <section class="section-block">
        <h2 class="section-title">Services du site</h2>
        <div class="service-grid">
          <PanelCard
            v-for="service in demoDetail.services"
            :key="service.name"
            :title="service.name"
            :status="service.status"
            :status-tone="statusTone(service.status)"
            :accent-tone="statusTone(service.status)"
          >
            <p v-for="line in service.lines" :key="line">{{ line }}</p>
          </PanelCard>
        </div>
      </section>

      <section class="section-block">
        <h2 class="section-title">Dernier job de provisioning</h2>
        <div class="job-shell">
          <ProgressBar
            :value="demoDetail.lastProvisioningCompletionRatio * 100"
            :max="100"
            :tone="demoDetail.lastProvisioningCompletionRatio >= 1 ? 'healthy' : 'running'"
          />
          <p class="mono job-summary">{{ demoSite.lastJobSummary }}</p>
        </div>
      </section>
    </template>

    <template v-else>
      <header class="site-heading">
        <div class="site-heading-left">
          <RouterLink class="breadcrumb" :to="{ name: 'dashboard' }">Dashboard</RouterLink>
          <div class="title-line">
            <h1>{{ backendSite?.name ?? "Site industriel" }}</h1>
            <StatusBadge
              :label="backendSite?.status ?? (loading ? 'loading' : 'unknown')"
              :tone="statusTone(backendSite?.status ?? (loading ? 'running' : 'waiting'))"
            />
          </div>
          <p class="subtitle">
            {{ backendSite?.city || "Ville n/a" }} ({{ backendSite?.code || "n/a" }}) - {{ backendSite?.customer_name || "Site industriel" }}
          </p>
        </div>

        <div class="site-actions">
          <RouterLink
            v-if="canRunE2E && routeSiteNumber !== null"
            class="action-button"
            :to="{ name: 'site-e2e', params: { siteId: String(routeSiteNumber) } }"
          >
            Test E2E
          </RouterLink>
          <RouterLink
            v-if="canRunProvisioning && routeSiteNumber !== null"
            class="action-button"
            :to="{ name: 'site-provisioning', params: { siteId: String(routeSiteNumber) } }"
          >
            Jobs
          </RouterLink>
        </div>
      </header>

      <section v-if="errorMessage" class="notice-shell notice-error">
        {{ errorMessage }}
      </section>

      <section v-else-if="loading" class="notice-shell notice-neutral">
        Chargement du site, des assets et de l'historique de provisioning...
      </section>

      <template v-else-if="backendSite">
        <section class="metric-grid">
          <MetricCard
            v-for="metric in backendMetrics"
            :key="metric.title"
            :title="metric.title"
            :value="metric.value"
            :subtitle="metric.subtitle"
            :tone="metric.tone"
          />
        </section>

        <section class="section-block">
          <h2 class="section-title">Services du site</h2>
          <div class="service-grid">
            <PanelCard
              v-for="service in backendServiceCards"
              :key="service.name"
              :title="service.name"
              :status="service.status"
              :status-tone="statusTone(service.status)"
              :accent-tone="statusTone(service.status)"
            >
              <p v-for="line in service.lines" :key="line">{{ line }}</p>
            </PanelCard>
          </div>
        </section>

        <section class="section-block">
          <h2 class="section-title">Dernier job de provisioning</h2>
          <div class="job-shell">
            <ProgressBar
              :value="latestBackendProgressRatio * 100"
              :max="100"
              :tone="latestBackendProgressRatio >= 1 ? 'healthy' : latestBackendJob ? 'running' : 'neutral'"
            />
            <p class="mono job-summary">
              <template v-if="latestBackendJob">
                Job #{{ latestBackendJob.id }} - {{ latestBackendJob.status }} - {{ latestBackendJob.playbook_name }}
                - {{ formatDateTime(latestBackendJob.finished_at ?? latestBackendJob.created_at) }}
              </template>
              <template v-else>
                Aucun job de provisioning pour ce site.
              </template>
            </p>
          </div>
        </section>

        <section class="section-block">
          <h2 class="section-title">Assets</h2>
          <div class="table-shell">
            <table class="detail-table">
              <thead>
                <tr>
                  <th>Hostname</th>
                  <th>Type</th>
                  <th>Management IP</th>
                  <th>WireGuard</th>
                  <th>Statut</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="asset in backendAssets" :key="asset.id">
                  <td>
                    <strong>{{ asset.inventory_hostname ?? asset.hostname ?? `asset-${asset.id}` }}</strong>
                    <span class="muted-copy">{{ asset.vendor ?? "vendor n/a" }} {{ asset.model ?? "" }}</span>
                  </td>
                  <td class="mono">{{ asset.asset_type }}</td>
                  <td class="mono">{{ asset.management_ip ?? "n/a" }}</td>
                  <td class="mono">{{ asset.wireguard_address ?? "n/a" }}</td>
                  <td>
                    <StatusBadge :label="asset.registration_status" :tone="statusTone(asset.registration_status)" compact />
                  </td>
                </tr>
                <tr v-if="backendAssets.length === 0">
                  <td colspan="5" class="muted-copy">Aucun asset associe a ce site.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="section-block">
          <h2 class="section-title">Historique des jobs</h2>
          <div class="table-shell">
            <table class="detail-table">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Statut</th>
                  <th>Workflow</th>
                  <th>Cree le</th>
                  <th>Termine le</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in backendJobs" :key="job.id">
                  <td class="mono">#{{ job.id }}</td>
                  <td>
                    <StatusBadge :label="job.status" :tone="statusTone(job.status)" compact />
                  </td>
                  <td class="mono">{{ job.playbook_name }}</td>
                  <td class="mono">{{ formatDateTime(job.created_at) }}</td>
                  <td class="mono">{{ formatDateTime(job.finished_at) }}</td>
                </tr>
                <tr v-if="backendJobs.length === 0">
                  <td colspan="5" class="muted-copy">Aucun job de provisioning pour ce site.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </template>
  </section>
</template>

<style scoped>
.site-heading {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 1.5rem;
}

.site-heading-left,
.section-block,
.metric-grid,
.service-grid {
  display: grid;
}

.site-heading-left {
  gap: 0.9rem;
}

.section-block {
  gap: 1rem;
}

.metric-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1.2rem;
}

.service-grid {
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1.3rem;
}

.breadcrumb {
  color: var(--blue);
  font-size: 1rem;
  text-decoration: none;
}

.title-line {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.title-line h1 {
  font-size: clamp(2rem, 2vw + 1rem, 3rem);
  line-height: 0.95;
}

.subtitle {
  color: var(--muted);
  font-size: 1.15rem;
  font-weight: 600;
}

.site-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
}

.notice-shell {
  padding: 1rem 1.2rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
}

.notice-neutral {
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
}

.notice-error {
  border-color: rgba(255, 154, 139, 0.28);
  color: var(--red-soft);
  background: rgba(123, 38, 33, 0.22);
}

.job-shell {
  display: grid;
  gap: 0.9rem;
  padding: 1.2rem 1.35rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(9, 10, 11, 0.96), rgba(6, 7, 8, 0.94));
}

.job-summary,
.muted-copy {
  color: var(--muted);
}

.table-shell {
  overflow: hidden;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(9, 10, 11, 0.96), rgba(6, 7, 8, 0.94));
}

.detail-table thead th {
  padding: 1rem 1.25rem;
  color: var(--muted);
  font-size: 0.98rem;
  border-bottom: 1px solid var(--line);
}

.detail-table tbody td {
  padding: 1.15rem 1.25rem;
  border-bottom: 1px solid var(--line);
  color: var(--text);
  vertical-align: top;
}

.detail-table tbody tr:last-child td {
  border-bottom: none;
}

.detail-table strong {
  display: block;
}

@media (max-width: 1100px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .site-heading {
    flex-direction: column;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .table-shell {
    overflow-x: auto;
  }

  .detail-table {
    min-width: 760px;
  }
}
</style>
