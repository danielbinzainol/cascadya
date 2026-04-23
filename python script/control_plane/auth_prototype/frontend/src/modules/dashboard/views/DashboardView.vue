<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { ApiError } from "@/api/client";
import { fetchInventoryAssets, fetchProvisioningJobs, fetchSites } from "@/api/provisioning";
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

interface DashboardCandidate {
  siteId: string;
  siteName: string;
  siteCode: string;
  city: string;
  assetLabel: string;
  jobId: number;
  finishedAt: string | null;
}

interface DashboardIpcRecord {
  assetId: string;
  siteId: string;
  siteName: string;
  siteCode: string;
  city: string;
  country: string;
  customerName: string;
  assetLabel: string;
  managementIp: string;
  registrationStatus: string;
}

interface DashboardCompanyBinding {
  assetId: string;
  siteLocation: string;
  region: string;
}

interface DashboardCompanyRecord {
  id: string;
  name: string;
  expanded: boolean;
  ipcBindings: DashboardCompanyBinding[];
}

interface DashboardCompanyPanel {
  id: string;
  name: string;
  expanded: boolean;
  ipcs: Array<DashboardIpcRecord & { binding: DashboardCompanyBinding }>;
  siteCount: number;
}

const DASHBOARD_SITE_STORAGE_KEY = "auth-prototype.dashboard-site-ids";
const DASHBOARD_COMPANY_STORAGE_KEY = "auth-prototype.dashboard-companies";

const router = useRouter();
const appStore = useAppStore();
const session = useSessionStore();

const loading = ref(false);
const errorMessage = ref<string | null>(null);
const noticeMessage = ref<string | null>(null);
const selectorOpen = ref(false);

const backendSites = ref<ApiSitePayload[]>([]);
const backendJobs = ref<ApiProvisioningJobPayload[]>([]);
const backendAssets = ref<ApiInventoryAssetPayload[]>([]);
const dashboardSiteIds = ref<string[]>([]);
const dashboardCompanies = ref<DashboardCompanyRecord[]>([]);

const companyNameDraft = ref("");
const companyAssetSelections = ref<Record<string, string>>({});

const siteSearchQuery = ref("");
const siteSortOrder = ref<"alpha_asc" | "alpha_desc">("alpha_asc");
const siteLocationFilter = ref("all");
const siteRegionFilter = ref("all");
const siteCompanyFilter = ref("all");

const usingBackend = computed(() => !session.demoModeEnabled);
const canProvision = computed(() => session.hasPermission("provision:prepare"));
const canRunE2E = computed(() => session.hasPermission("inventory:scan"));
const centralServices = computed(() => appStore.centralServices);

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

function normalizeSearch(value: string) {
  return value.trim().toLocaleLowerCase("fr-FR");
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.filter((value) => value.trim().length > 0)));
}

function readStoredDashboardSelection() {
  if (typeof window === "undefined") {
    return {
      hasStoredSelection: false,
      ids: [] as string[],
    };
  }

  const rawValue = window.localStorage.getItem(DASHBOARD_SITE_STORAGE_KEY);
  if (rawValue === null) {
    return {
      hasStoredSelection: false,
      ids: [] as string[],
    };
  }

  try {
    const parsed = JSON.parse(rawValue);
    if (!Array.isArray(parsed)) {
      return {
        hasStoredSelection: true,
        ids: [] as string[],
      };
    }
    return {
      hasStoredSelection: true,
      ids: parsed.map((value) => String(value)),
    };
  } catch {
    return {
      hasStoredSelection: true,
      ids: [] as string[],
    };
  }
}

function persistDashboardSelection(siteIds: string[]) {
  const normalized = Array.from(new Set(siteIds.map((siteId) => String(siteId))));
  dashboardSiteIds.value = normalized;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(DASHBOARD_SITE_STORAGE_KEY, JSON.stringify(normalized));
  }
}

function normalizeStoredCompany(rawValue: unknown): DashboardCompanyRecord | null {
  if (typeof rawValue !== "object" || rawValue === null) {
    return null;
  }

  const record = rawValue as Record<string, unknown>;
  const id = String(record.id ?? "").trim();
  const name = String(record.name ?? "").trim();
  if (!id || !name) {
    return null;
  }

  const bindings = Array.isArray(record.ipcBindings)
    ? record.ipcBindings.flatMap((bindingValue) => {
        if (typeof bindingValue !== "object" || bindingValue === null) {
          return [];
        }

        const bindingRecord = bindingValue as Record<string, unknown>;
        const assetId = String(bindingRecord.assetId ?? "").trim();
        if (!assetId) {
          return [];
        }

        return [
          {
            assetId,
            siteLocation: String(bindingRecord.siteLocation ?? "").trim(),
            region: String(bindingRecord.region ?? "").trim(),
          } satisfies DashboardCompanyBinding,
        ];
      })
    : [];

  const uniqueBindings = Array.from(new Map(bindings.map((binding) => [binding.assetId, binding])).values());

  return {
    id,
    name,
    expanded: record.expanded !== false,
    ipcBindings: uniqueBindings,
  };
}

function readStoredDashboardCompanies() {
  if (typeof window === "undefined") {
    return [] as DashboardCompanyRecord[];
  }

  const rawValue = window.localStorage.getItem(DASHBOARD_COMPANY_STORAGE_KEY);
  if (!rawValue) {
    return [] as DashboardCompanyRecord[];
  }

  try {
    const parsed = JSON.parse(rawValue);
    if (!Array.isArray(parsed)) {
      return [] as DashboardCompanyRecord[];
    }
    return parsed
      .map((value) => normalizeStoredCompany(value))
      .filter((value): value is DashboardCompanyRecord => value !== null);
  } catch {
    return [] as DashboardCompanyRecord[];
  }
}

function persistDashboardCompanies(companies: DashboardCompanyRecord[]) {
  dashboardCompanies.value = companies.map((company) => ({
    id: company.id,
    name: company.name.trim(),
    expanded: company.expanded,
    ipcBindings: Array.from(new Map(company.ipcBindings.map((binding) => [binding.assetId, binding])).values()),
  }));

  if (typeof window !== "undefined") {
    window.localStorage.setItem(DASHBOARD_COMPANY_STORAGE_KEY, JSON.stringify(dashboardCompanies.value));
  }
}

function latestSucceededSiteIds(jobs: ApiProvisioningJobPayload[]) {
  const siteIds: string[] = [];
  const seen = new Set<string>();
  const succeededJobs = [...jobs]
    .filter((job) => job.status === "succeeded" && job.site)
    .sort((left, right) => Date.parse(right.finished_at ?? right.created_at) - Date.parse(left.finished_at ?? left.created_at));

  for (const job of succeededJobs) {
    const siteId = String(job.site?.id ?? "");
    if (!siteId || seen.has(siteId)) {
      continue;
    }
    seen.add(siteId);
    siteIds.push(siteId);
  }
  return siteIds;
}

async function loadDashboard() {
  if (!usingBackend.value) {
    return;
  }

  loading.value = true;
  errorMessage.value = null;
  noticeMessage.value = null;

  try {
    const [sitesResponse, jobsResponse, assetsResponse] = await Promise.all([
      fetchSites(),
      fetchProvisioningJobs(),
      fetchInventoryAssets(),
    ]);

    backendSites.value = [...sitesResponse.sites].sort((left, right) => left.name.localeCompare(right.name));
    backendJobs.value = jobsResponse.jobs;
    backendAssets.value = assetsResponse.assets;

    const existingSiteIds = new Set(backendSites.value.map((site) => String(site.id)));
    const storedSelection = readStoredDashboardSelection();

    if (!storedSelection.hasStoredSelection) {
      persistDashboardSelection(latestSucceededSiteIds(backendJobs.value).filter((siteId) => existingSiteIds.has(siteId)));
    } else {
      persistDashboardSelection(storedSelection.ids.filter((siteId) => existingSiteIds.has(siteId)));
    }

    persistDashboardCompanies(readStoredDashboardCompanies());
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

const selectedSiteIdSet = computed(() => new Set(dashboardSiteIds.value));

const dashboardCandidates = computed<DashboardCandidate[]>(() => {
  if (!usingBackend.value) {
    return [];
  }

  const candidatesBySite = new Map<string, DashboardCandidate>();
  const succeededJobs = [...backendJobs.value]
    .filter((job) => job.status === "succeeded" && job.site)
    .sort((left, right) => Date.parse(right.finished_at ?? right.created_at) - Date.parse(left.finished_at ?? left.created_at));

  for (const job of succeededJobs) {
    const site = job.site;
    const siteId = String(site?.id ?? "");
    if (!siteId || selectedSiteIdSet.value.has(siteId) || candidatesBySite.has(siteId)) {
      continue;
    }

    const fullSite = backendSites.value.find((item) => String(item.id) === siteId);
    const asset = job.context.asset;
    const assetLabel = asset?.inventory_hostname ?? asset?.hostname ?? asset?.management_ip ?? "IPC provisionne";

    candidatesBySite.set(siteId, {
      siteId,
      siteName: fullSite?.name ?? site?.name ?? `Site ${siteId}`,
      siteCode: fullSite?.code ?? site?.code ?? "n/a",
      city: fullSite?.city ?? "",
      assetLabel,
      jobId: job.id,
      finishedAt: job.finished_at,
    });
  }

  return [...candidatesBySite.values()];
});

const dashboardSites = computed(() => {
  if (!usingBackend.value) {
    return [];
  }
  return backendSites.value.filter((site) => selectedSiteIdSet.value.has(String(site.id)));
});

const dashboardIpcs = computed<DashboardIpcRecord[]>(() => {
  if (!usingBackend.value) {
    return [];
  }

  return backendAssets.value
    .filter(
      (asset) =>
        asset.asset_type === "industrial_pc" &&
        asset.site &&
        selectedSiteIdSet.value.has(String(asset.site.id)) &&
        asset.registration_status !== "discovered",
    )
    .map((asset) => {
      const siteId = String(asset.site?.id ?? "");
      const fullSite = backendSites.value.find((site) => String(site.id) === siteId);

      return {
        assetId: String(asset.id),
        siteId,
        siteName: fullSite?.name ?? asset.site?.name ?? `Site ${siteId}`,
        siteCode: fullSite?.code ?? asset.site?.code ?? "n/a",
        city: fullSite?.city ?? "",
        country: fullSite?.country ?? "",
        customerName: fullSite?.customer_name ?? "",
        assetLabel: asset.inventory_hostname ?? asset.hostname ?? asset.management_ip ?? `IPC ${asset.id}`,
        managementIp: asset.management_ip ?? asset.ip_address ?? "n/a",
        registrationStatus: asset.registration_status,
      };
    })
    .sort((left, right) => {
      const siteCompare = left.siteName.localeCompare(right.siteName);
      return siteCompare !== 0 ? siteCompare : left.assetLabel.localeCompare(right.assetLabel);
    });
});

const dashboardIpcById = computed(() => new Map(dashboardIpcs.value.map((ipc) => [ipc.assetId, ipc])));

watch(
  () => dashboardIpcs.value.map((ipc) => ipc.assetId).sort().join("|"),
  () => {
    const availableAssetIds = new Set(dashboardIpcs.value.map((ipc) => ipc.assetId));
    let changed = false;

    const nextCompanies = dashboardCompanies.value.map((company) => {
      const nextBindings = company.ipcBindings.filter((binding) => availableAssetIds.has(binding.assetId));
      if (nextBindings.length !== company.ipcBindings.length) {
        changed = true;
      }
      return {
        ...company,
        ipcBindings: nextBindings,
      };
    });

    if (changed) {
      persistDashboardCompanies(nextCompanies);
    }

    companyAssetSelections.value = Object.fromEntries(
      Object.entries(companyAssetSelections.value).filter(([, assetId]) => assetId === "" || availableAssetIds.has(assetId)),
    );
  },
  { immediate: true },
);

const companyBindingByAssetId = computed(() => {
  const bindings = new Map<
    string,
    {
      companyId: string;
      companyName: string;
      binding: DashboardCompanyBinding;
    }
  >();

  for (const company of dashboardCompanies.value) {
    for (const binding of company.ipcBindings) {
      bindings.set(binding.assetId, {
        companyId: company.id,
        companyName: company.name,
        binding,
      });
    }
  }

  return bindings;
});

const companyPanels = computed<DashboardCompanyPanel[]>(() =>
  [...dashboardCompanies.value]
    .sort((left, right) => left.name.localeCompare(right.name))
    .map((company) => {
      const ipcs = company.ipcBindings
        .map((binding) => {
          const ipc = dashboardIpcById.value.get(binding.assetId);
          if (!ipc) {
            return null;
          }
          return {
            ...ipc,
            binding,
          };
        })
        .filter((value): value is DashboardCompanyPanel["ipcs"][number] => value !== null);

      return {
        id: company.id,
        name: company.name,
        expanded: company.expanded,
        ipcs,
        siteCount: new Set(ipcs.map((ipc) => ipc.siteId)).size,
      };
    }),
);

const siteMeta = computed(() => {
  const meta = new Map<
    string,
    {
      companyIds: Set<string>;
      companyNames: Set<string>;
      locations: Set<string>;
      regions: Set<string>;
      assetLabels: Set<string>;
      managementIps: Set<string>;
    }
  >();

  for (const ipc of dashboardIpcs.value) {
    const siteId = ipc.siteId;
    const current = meta.get(siteId) ?? {
      companyIds: new Set<string>(),
      companyNames: new Set<string>(),
      locations: new Set<string>(),
      regions: new Set<string>(),
      assetLabels: new Set<string>(),
      managementIps: new Set<string>(),
    };

    current.assetLabels.add(ipc.assetLabel);
    if (ipc.managementIp && ipc.managementIp !== "n/a") {
      current.managementIps.add(ipc.managementIp);
    }
    if (ipc.city) {
      current.locations.add(ipc.city);
    }

    const assigned = companyBindingByAssetId.value.get(ipc.assetId);
    if (assigned) {
      current.companyIds.add(assigned.companyId);
      current.companyNames.add(assigned.companyName);
      if (assigned.binding.siteLocation) {
        current.locations.add(assigned.binding.siteLocation);
      }
      if (assigned.binding.region) {
        current.regions.add(assigned.binding.region);
      }
    }

    meta.set(siteId, current);
  }

  return meta;
});

function getSiteCompanyNames(siteId: string) {
  return [...(siteMeta.value.get(siteId)?.companyNames ?? new Set<string>())];
}

function getSiteCompanyIds(siteId: string) {
  return [...(siteMeta.value.get(siteId)?.companyIds ?? new Set<string>())];
}

function getSiteLocations(siteId: string, fallbackCity: string) {
  const locations = [...(siteMeta.value.get(siteId)?.locations ?? new Set<string>())];
  if (locations.length > 0) {
    return locations;
  }
  return fallbackCity ? [fallbackCity] : [];
}

function getSiteRegions(siteId: string) {
  return [...(siteMeta.value.get(siteId)?.regions ?? new Set<string>())];
}

function getSiteIpcLabels(siteId: string) {
  return [...(siteMeta.value.get(siteId)?.assetLabels ?? new Set<string>())];
}

function getSiteIpcIps(siteId: string) {
  return [...(siteMeta.value.get(siteId)?.managementIps ?? new Set<string>())];
}

const availableLocationOptions = computed(() =>
  uniqueStrings(
    dashboardSites.value.flatMap((site) => getSiteLocations(String(site.id), site.city || "")),
  ).sort((left, right) => left.localeCompare(right)),
);

const availableRegionOptions = computed(() =>
  uniqueStrings(
    dashboardSites.value.flatMap((site) => getSiteRegions(String(site.id))),
  ).sort((left, right) => left.localeCompare(right)),
);

const availableCompanyOptions = computed(() =>
  companyPanels.value.map((company) => ({
    id: company.id,
    name: company.name,
  })),
);

const filteredDashboardSites = computed(() => {
  const query = normalizeSearch(siteSearchQuery.value);

  const filtered = [...dashboardSites.value].filter((site) => {
    const siteId = String(site.id);
    const companyIds = getSiteCompanyIds(siteId);
    const companyNames = getSiteCompanyNames(siteId);
    const locations = getSiteLocations(siteId, site.city || "");
    const regions = getSiteRegions(siteId);

    if (siteCompanyFilter.value !== "all" && !companyIds.includes(siteCompanyFilter.value)) {
      return false;
    }

    if (siteLocationFilter.value !== "all" && !locations.includes(siteLocationFilter.value)) {
      return false;
    }

    if (siteRegionFilter.value !== "all" && !regions.includes(siteRegionFilter.value)) {
      return false;
    }

    if (!query) {
      return true;
    }

    const searchableValues = [
      site.name,
      site.code,
      site.city,
      site.country,
      site.customer_name,
      ...companyNames,
      ...locations,
      ...regions,
      ...getSiteIpcLabels(siteId),
      ...getSiteIpcIps(siteId),
    ];

    return searchableValues.some((value) => normalizeSearch(value).includes(query));
  });

  filtered.sort((left, right) =>
    siteSortOrder.value === "alpha_desc"
      ? right.name.localeCompare(left.name)
      : left.name.localeCompare(right.name),
  );

  return filtered;
});

const metrics = computed<DashboardMetric[]>(() => {
  if (!usingBackend.value) {
    return appStore.dashboardMetrics;
  }

  const sites = dashboardSites.value;
  const provisioningSites = sites.filter((site) => site.status === "provisioning").length;
  const successfulLatestJobs = sites.filter((site) => site.last_job?.status === "succeeded").length;
  const activeAssets = sites.reduce((total, site) => total + site.active_asset_count, 0);
  const totalAssets = sites.reduce((total, site) => total + site.asset_count, 0);
  const availableCandidates = dashboardCandidates.value.length;

  return [
    {
      title: "Sites actifs",
      value: String(sites.length),
      subtitle: `${provisioningSites} en provisioning`,
      tone: sites.length > 0 ? "healthy" : "neutral",
    },
    {
      title: "IPC actifs",
      value: `${activeAssets} / ${totalAssets}`,
      subtitle: `${dashboardIpcs.value.length} IPC visibles`,
      tone: sites.length === 0 ? "neutral" : activeAssets === totalAssets ? "healthy" : "warning",
    },
    {
      title: "Entreprises",
      value: String(dashboardCompanies.value.length),
      subtitle: `${dashboardIpcs.value.length} IPC regroupes ou disponibles`,
      tone: dashboardCompanies.value.length > 0 ? "active" : "neutral",
    },
    {
      title: "Historique provisioning",
      value: String(backendJobs.value.filter((job) => job.status === "succeeded").length),
      subtitle: `${availableCandidates} sites disponibles a ajouter`,
      tone: successfulLatestJobs === sites.length && sites.length > 0 ? "healthy" : "neutral",
    },
  ];
});

const demoMetrics = computed(() => appStore.dashboardMetrics);
const demoSites = computed(() => appStore.sites);

function openSite(siteId: string) {
  router.push({
    name: "site-detail",
    params: {
      siteId,
    },
  });
}

function openProvisioning() {
  router.push({
    name: "provisioning-center",
  });
}

function openSiteProvisioning(siteId: string) {
  router.push({
    name: "site-provisioning",
    params: {
      siteId,
    },
  });
}

function openSiteE2E(siteId: string) {
  router.push({
    name: "site-e2e",
    params: {
      siteId,
    },
  });
}

function addSiteToDashboard(candidate: DashboardCandidate) {
  persistDashboardSelection([...dashboardSiteIds.value, candidate.siteId]);
  noticeMessage.value = `${candidate.siteName} a ete ajoute au dashboard a partir de ${candidate.assetLabel}.`;
}

function removeSiteFromDashboard(siteId: string, siteName: string) {
  persistDashboardSelection(dashboardSiteIds.value.filter((value) => value !== siteId));
  noticeMessage.value = `${siteName} a ete retire du dashboard.`;
}

function createCompany() {
  const name = companyNameDraft.value.trim();
  if (!name) {
    noticeMessage.value = "Renseigne un nom d'entreprise avant de l'ajouter.";
    return;
  }

  const duplicate = dashboardCompanies.value.some(
    (company) => company.name.toLocaleLowerCase("fr-FR") === name.toLocaleLowerCase("fr-FR"),
  );
  if (duplicate) {
    noticeMessage.value = `L'entreprise ${name} existe deja sur ce dashboard.`;
    return;
  }

  persistDashboardCompanies([
    ...dashboardCompanies.value,
    {
      id: `company-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      name,
      expanded: true,
      ipcBindings: [],
    },
  ]);
  companyNameDraft.value = "";
  noticeMessage.value = `${name} a ete ajoutee au dashboard.`;
}

function removeCompany(companyId: string, companyName: string) {
  persistDashboardCompanies(dashboardCompanies.value.filter((company) => company.id !== companyId));
  const nextSelections = { ...companyAssetSelections.value };
  delete nextSelections[companyId];
  companyAssetSelections.value = nextSelections;
  if (siteCompanyFilter.value === companyId) {
    siteCompanyFilter.value = "all";
  }
  noticeMessage.value = `${companyName} a ete retiree du dashboard.`;
}

function toggleCompany(companyId: string) {
  persistDashboardCompanies(
    dashboardCompanies.value.map((company) =>
      company.id === companyId
        ? {
            ...company,
            expanded: !company.expanded,
          }
        : company,
    ),
  );
}

function availableIpcsForCompany(companyId: string) {
  return dashboardIpcs.value.filter((ipc) => {
    const assigned = companyBindingByAssetId.value.get(ipc.assetId);
    return !assigned || assigned.companyId === companyId;
  });
}

function addIpcToCompany(companyId: string) {
  const assetId = companyAssetSelections.value[companyId];
  if (!assetId) {
    noticeMessage.value = "Selectionne d'abord un IPC a rattacher a l'entreprise.";
    return;
  }

  const ipc = dashboardIpcById.value.get(assetId);
  if (!ipc) {
    noticeMessage.value = "L'IPC selectionne n'est plus disponible sur le dashboard.";
    return;
  }

  persistDashboardCompanies(
    dashboardCompanies.value.map((company) => {
      if (company.id !== companyId) {
        return company;
      }

      if (company.ipcBindings.some((binding) => binding.assetId === assetId)) {
        return company;
      }

      return {
        ...company,
        expanded: true,
        ipcBindings: [
          ...company.ipcBindings,
          {
            assetId,
            siteLocation: ipc.city || ipc.siteName,
            region: "",
          },
        ],
      };
    }),
  );

  companyAssetSelections.value = {
    ...companyAssetSelections.value,
    [companyId]: "",
  };

  const companyName = dashboardCompanies.value.find((company) => company.id === companyId)?.name ?? "Entreprise";
  noticeMessage.value = `${ipc.assetLabel} a ete rattache a ${companyName}.`;
}

function removeIpcFromCompany(companyId: string, assetId: string, assetLabel: string) {
  persistDashboardCompanies(
    dashboardCompanies.value.map((company) =>
      company.id === companyId
        ? {
            ...company,
            ipcBindings: company.ipcBindings.filter((binding) => binding.assetId !== assetId),
          }
        : company,
    ),
  );
  noticeMessage.value = `${assetLabel} a ete retire de l'entreprise.`;
}

function updateCompanyBinding(companyId: string, assetId: string, patch: Partial<DashboardCompanyBinding>) {
  persistDashboardCompanies(
    dashboardCompanies.value.map((company) => {
      if (company.id !== companyId) {
        return company;
      }

      return {
        ...company,
        ipcBindings: company.ipcBindings.map((binding) =>
          binding.assetId === assetId
            ? {
                ...binding,
                siteLocation:
                  patch.siteLocation !== undefined ? patch.siteLocation.trim() : binding.siteLocation,
                region: patch.region !== undefined ? patch.region.trim() : binding.region,
              }
            : binding,
        ),
      };
    }),
  );
}

onMounted(() => {
  if (usingBackend.value) {
    dashboardCompanies.value = readStoredDashboardCompanies();
  }
  void loadDashboard();
});
</script>

<template>
  <section class="stack-card">
    <header class="page-heading">
      <div>
        <p class="muted-2 uppercase">Fleet overview</p>
        <h1>Cascadya control plane</h1>
      </div>
      <div class="header-actions">
        <button
          v-if="usingBackend"
          class="button-secondary"
          type="button"
          :disabled="loading"
          @click="selectorOpen = !selectorOpen"
        >
          {{ selectorOpen ? "Fermer la liste IPC" : "Ajouter depuis un IPC provisionne" }}
        </button>
        <button v-if="canProvision" class="action-button" type="button" @click="openProvisioning">
          + Provisionner un site
        </button>
      </div>
    </header>

    <section v-if="noticeMessage" class="notice-shell notice-ok">
      {{ noticeMessage }}
    </section>

    <section v-if="errorMessage" class="notice-shell notice-error">
      {{ errorMessage }}
    </section>

    <section class="metric-grid">
      <MetricCard
        v-for="metric in usingBackend ? metrics : demoMetrics"
        :key="metric.title"
        :title="metric.title"
        :value="metric.value"
        :subtitle="metric.subtitle"
        :tone="metric.tone"
      />
    </section>

    <section class="section-block">
      <h2 class="section-title">Services centraux</h2>
      <div class="service-grid">
        <PanelCard
          v-for="service in centralServices"
          :key="service.name"
          :title="service.name"
          :status="service.status"
          :status-tone="statusTone(service.status)"
          :accent-tone="statusTone(service.status)"
        >
          <p>{{ service.summary }}</p>
          <p>{{ service.details }}</p>
          <p>{{ service.heartbeat }}</p>
        </PanelCard>
      </div>
    </section>

    <section v-if="usingBackend && selectorOpen" class="section-block">
      <div class="section-heading">
        <div>
          <h2 class="section-title">Ajouter un site via un IPC provisionne</h2>
          <p class="section-copy">
            La liste propose uniquement des IPC dont le dernier job de provisioning est en statut
            <span class="mono">succeeded</span>. Ajouter un IPC ajoute son site parent au dashboard.
          </p>
        </div>
        <StatusBadge :label="`${dashboardCandidates.length} disponibles`" tone="neutral" compact />
      </div>

      <div v-if="dashboardCandidates.length" class="candidate-grid">
        <article v-for="candidate in dashboardCandidates" :key="candidate.siteId" class="candidate-card">
          <div class="candidate-copy">
            <strong>{{ candidate.siteName }}</strong>
            <span>{{ candidate.city }} ({{ candidate.siteCode }})</span>
            <span class="mono">IPC: {{ candidate.assetLabel }}</span>
            <span class="mono">Job #{{ candidate.jobId }} - {{ formatDateTime(candidate.finishedAt) }}</span>
          </div>
          <button class="button-secondary" type="button" @click="addSiteToDashboard(candidate)">
            Ajouter au dashboard
          </button>
        </article>
      </div>
      <div v-else class="empty-shell">
        <p>Aucun nouveau site n'est disponible. Tous les sites issus de jobs succeeds sont deja visibles ici.</p>
      </div>
    </section>

    <section v-if="usingBackend" class="section-block">
      <div class="section-heading">
        <div>
          <h2 class="section-title">Entreprises</h2>
          <p class="section-copy">
            Cree des regroupements metier, rattache-y les IPC deja visibles sur le dashboard et ajuste
            localement les champs <span class="mono">Lieu du site</span> et <span class="mono">Region</span>.
          </p>
        </div>
        <StatusBadge :label="`${companyPanels.length} entreprises`" tone="neutral" compact />
      </div>

      <div class="company-create">
        <input
          v-model="companyNameDraft"
          class="input-shell"
          type="text"
          placeholder="Nom de l'entreprise"
          @keyup.enter="createCompany"
        />
        <button class="button-secondary" type="button" @click="createCompany">
          Ajouter une entreprise
        </button>
      </div>

      <div v-if="companyPanels.length" class="company-grid">
        <article v-for="company in companyPanels" :key="company.id" class="company-card">
          <div class="company-header">
            <button class="company-toggle" type="button" @click="toggleCompany(company.id)">
              <span class="company-chevron">{{ company.expanded ? "▾" : "▸" }}</span>
              <span class="company-name">{{ company.name }}</span>
            </button>
            <div class="company-actions">
              <StatusBadge :label="`${company.ipcs.length} IPC`" tone="neutral" compact />
              <StatusBadge :label="`${company.siteCount} sites`" tone="active" compact />
              <button class="button-danger" type="button" @click="removeCompany(company.id, company.name)">
                Retirer
              </button>
            </div>
          </div>

          <div v-if="company.expanded" class="company-body">
            <div class="company-assign">
              <select v-model="companyAssetSelections[company.id]" class="input-shell">
                <option value="">Selectionner un IPC du dashboard</option>
                <option
                  v-for="ipc in availableIpcsForCompany(company.id)"
                  :key="ipc.assetId"
                  :value="ipc.assetId"
                >
                  {{ ipc.assetLabel }} - {{ ipc.siteName }} ({{ ipc.siteCode }})
                </option>
              </select>
              <button class="button-secondary" type="button" @click="addIpcToCompany(company.id)">
                Ajouter l'IPC
              </button>
            </div>

            <div v-if="company.ipcs.length" class="company-ipc-list">
              <article v-for="ipc in company.ipcs" :key="ipc.assetId" class="company-ipc-card">
                <div class="company-ipc-copy">
                  <strong>{{ ipc.assetLabel }}</strong>
                  <span>{{ ipc.siteName }} ({{ ipc.siteCode }})</span>
                  <span class="mono">IP management: {{ ipc.managementIp }}</span>
                </div>

                <div class="company-ipc-form">
                  <label>
                    <span>Lieu du site</span>
                    <input
                      class="input-shell"
                      type="text"
                      :value="ipc.binding.siteLocation"
                      @change="
                        updateCompanyBinding(
                          company.id,
                          ipc.assetId,
                          { siteLocation: ($event.target as HTMLInputElement).value },
                        )
                      "
                    />
                  </label>
                  <label>
                    <span>Region</span>
                    <input
                      class="input-shell"
                      type="text"
                      :value="ipc.binding.region"
                      @change="
                        updateCompanyBinding(
                          company.id,
                          ipc.assetId,
                          { region: ($event.target as HTMLInputElement).value },
                        )
                      "
                    />
                  </label>
                </div>

                <div class="row-actions row-actions-inline">
                  <button class="button-secondary" type="button" @click.stop="openSite(ipc.siteId)">
                    Ouvrir le site
                  </button>
                  <button class="button-danger" type="button" @click="removeIpcFromCompany(company.id, ipc.assetId, ipc.assetLabel)">
                    Retirer l'IPC
                  </button>
                </div>
              </article>
            </div>
            <div v-else class="empty-shell compact-empty">
              <p>Aucun IPC n'est encore rattache a cette entreprise.</p>
            </div>
          </div>
        </article>
      </div>
      <div v-else class="empty-shell">
        <p>Aucune entreprise n'a encore ete ajoutee au dashboard.</p>
      </div>
    </section>

    <section class="section-block">
      <div class="section-heading">
        <div>
          <h2 class="section-title">{{ usingBackend ? "Sites du dashboard" : "Sites" }}</h2>
          <p v-if="usingBackend" class="section-copy">
            Recherche par site, ville, region, entreprise ou IPC. Trie ensuite la vue par ordre alphabetique et
            filtre-la par lieu, region ou entreprise.
          </p>
        </div>
      </div>

      <template v-if="usingBackend">
        <div class="filter-grid">
          <input
            v-model="siteSearchQuery"
            class="input-shell"
            type="search"
            placeholder="Rechercher un site, un IPC, une region ou une entreprise"
          />
          <select v-model="siteSortOrder" class="input-shell">
            <option value="alpha_asc">Alphabetique A -> Z</option>
            <option value="alpha_desc">Alphabetique Z -> A</option>
          </select>
          <select v-model="siteLocationFilter" class="input-shell">
            <option value="all">Tous les lieux</option>
            <option v-for="location in availableLocationOptions" :key="location" :value="location">
              {{ location }}
            </option>
          </select>
          <select v-model="siteRegionFilter" class="input-shell">
            <option value="all">Toutes les regions</option>
            <option v-for="region in availableRegionOptions" :key="region" :value="region">
              {{ region }}
            </option>
          </select>
          <select v-model="siteCompanyFilter" class="input-shell">
            <option value="all">Toutes les entreprises</option>
            <option v-for="company in availableCompanyOptions" :key="company.id" :value="company.id">
              {{ company.name }}
            </option>
          </select>
        </div>

        <div v-if="loading" class="empty-shell">
          <p>Chargement des sites et du provisioning...</p>
        </div>
        <div v-else-if="dashboardSites.length === 0" class="empty-shell">
          <p>
            Aucun site n'est encore affiche sur le dashboard. Utilise
            <span class="mono">Ajouter depuis un IPC provisionne</span> pour composer la liste.
          </p>
        </div>
        <div v-else-if="filteredDashboardSites.length === 0" class="empty-shell">
          <p>Aucun site ne correspond aux filtres et a la recherche actuels.</p>
        </div>
        <div v-else class="table-shell">
          <table class="site-table">
            <thead>
              <tr>
                <th>Site</th>
                <th>Entreprise</th>
                <th>Region / lieu</th>
                <th>Statut</th>
                <th>IPC / assets</th>
                <th>Dernier job</th>
                <th>Dernier scan</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="site in filteredDashboardSites"
                :key="site.id"
                class="site-row"
                @click="openSite(String(site.id))"
              >
                <td>
                  <strong>{{ site.name }}</strong>
                  <span>{{ site.city || "Ville n/a" }} ({{ site.code }})</span>
                  <span class="muted-copy">{{ site.customer_name || "Client n/a" }}</span>
                </td>
                <td>
                  <div class="tag-stack">
                    <span
                      v-for="companyName in getSiteCompanyNames(String(site.id))"
                      :key="companyName"
                      class="chip-shell"
                    >
                      {{ companyName }}
                    </span>
                    <span v-if="getSiteCompanyNames(String(site.id)).length === 0" class="muted-copy">Aucune</span>
                  </div>
                </td>
                <td>
                  <div class="tag-stack">
                    <span
                      v-for="region in getSiteRegions(String(site.id))"
                      :key="`region-${region}`"
                      class="chip-shell chip-shell-accent"
                    >
                      {{ region }}
                    </span>
                    <span
                      v-for="location in getSiteLocations(String(site.id), site.city || '')"
                      :key="`location-${location}`"
                      class="muted-copy"
                    >
                      {{ location }}
                    </span>
                  </div>
                </td>
                <td>
                  <StatusBadge :label="site.status" :tone="statusTone(site.status)" />
                </td>
                <td>
                  <div class="tag-stack">
                    <span
                      v-for="ipcLabel in getSiteIpcLabels(String(site.id))"
                      :key="ipcLabel"
                      class="chip-shell"
                    >
                      {{ ipcLabel }}
                    </span>
                    <span class="mono muted-copy">{{ site.active_asset_count }} / {{ site.asset_count }}</span>
                  </div>
                </td>
                <td>
                  <div v-if="site.last_job" class="job-cell">
                    <StatusBadge :label="site.last_job.status" :tone="statusTone(site.last_job.status)" compact />
                    <span class="mono">{{ site.last_job.playbook_name }}</span>
                    <span class="muted-copy">{{ formatDateTime(site.last_job.finished_at ?? site.last_job.created_at) }}</span>
                  </div>
                  <span v-else class="muted-copy">Aucun job</span>
                </td>
                <td class="mono">
                  {{ site.last_scan ? formatDateTime(site.last_scan.finished_at ?? site.last_scan.created_at) : "n/a" }}
                </td>
                <td>
                  <div class="row-actions">
                    <button
                      v-if="canRunE2E"
                      class="button-secondary"
                      type="button"
                      @click.stop="openSiteE2E(String(site.id))"
                    >
                      Test E2E
                    </button>
                    <button
                      v-if="canProvision"
                      class="button-secondary"
                      type="button"
                      @click.stop="openSiteProvisioning(String(site.id))"
                    >
                      Jobs
                    </button>
                    <button
                      class="button-danger"
                      type="button"
                      @click.stop="removeSiteFromDashboard(String(site.id), site.name)"
                    >
                      Retirer
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <div v-else class="table-shell">
        <table class="site-table">
          <thead>
            <tr>
              <th>Site</th>
              <th>Statut</th>
              <th>ems-site</th>
              <th>Routes</th>
              <th>Capacite</th>
              <th>Dernier HB</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="site in demoSites" :key="site.siteId" class="site-row" @click="openSite(site.siteId)">
              <td>
                <strong>{{ site.name }}</strong>
                <span>{{ site.city }} ({{ site.code }})</span>
              </td>
              <td>
                <StatusBadge :label="site.status" :tone="statusTone(site.status)" />
              </td>
              <td>
                <StatusBadge :label="site.emsSiteStatus" :tone="statusTone(site.emsSiteStatus)" />
              </td>
              <td>
                <div class="route-cell">
                  <ProgressBar
                    :value="site.routesOk"
                    :max="site.routesTotal"
                    :tone="site.routesOk === site.routesTotal ? 'healthy' : 'warning'"
                  />
                  <span class="mono route-copy">{{ site.routesOk }}/{{ site.routesTotal }}</span>
                </div>
              </td>
              <td class="capacity">{{ site.capacityMw.toFixed(1) }} MW</td>
              <td class="mono heartbeat">{{ site.lastHeartbeat }}</td>
            </tr>
          </tbody>
        </table>
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
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.8rem;
}

.metric-grid,
.service-grid,
.candidate-grid,
.company-grid {
  display: grid;
  gap: 1.25rem;
}

.metric-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.service-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.candidate-grid,
.company-grid {
  grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
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

.notice-error {
  border-color: rgba(255, 154, 139, 0.28);
  color: var(--red-soft);
  background: rgba(123, 38, 33, 0.22);
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

.candidate-card,
.company-card {
  display: grid;
  gap: 1rem;
  padding: 1.25rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(10, 11, 13, 0.97), rgba(6, 7, 8, 0.94));
}

.candidate-copy,
.company-ipc-copy {
  display: grid;
  gap: 0.35rem;
}

.company-create,
.company-assign {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.8rem;
  align-items: center;
}

.input-shell {
  width: 100%;
  min-height: 2.9rem;
  padding: 0.75rem 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
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

.input-shell::placeholder {
  color: var(--muted);
}

.input-shell:focus {
  outline: none;
  border-color: rgba(122, 168, 255, 0.4);
  box-shadow: 0 0 0 1px rgba(122, 168, 255, 0.18);
}

.company-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.company-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text);
  text-align: left;
  font: inherit;
}

.company-chevron {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.1rem;
  color: var(--muted);
  font-weight: 700;
  transition: transform 150ms ease;
}

.company-chevron.is-open {
  transform: rotate(90deg);
}

.company-name {
  font-size: 1.08rem;
  font-weight: 600;
}

.company-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.65rem;
}

.company-body {
  display: grid;
  gap: 1rem;
}

.company-ipc-list {
  display: grid;
  gap: 0.9rem;
}

.company-ipc-card {
  display: grid;
  gap: 1rem;
  padding: 1rem;
  border-radius: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.025);
}

.company-ipc-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}

.company-ipc-form label {
  display: grid;
  gap: 0.45rem;
}

.company-ipc-form label span {
  color: var(--muted);
  font-size: 0.92rem;
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.4fr repeat(4, minmax(0, 1fr));
  gap: 0.8rem;
}

.table-shell {
  overflow: hidden;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(9, 10, 11, 0.96), rgba(6, 7, 8, 0.94));
}

.site-table {
  width: 100%;
  border-collapse: collapse;
}

.site-table thead th {
  padding: 1rem 1.25rem;
  color: var(--muted);
  font-weight: 600;
  text-align: left;
  border-bottom: 1px solid var(--line);
}

.site-row {
  cursor: pointer;
  transition: background 140ms ease;
}

.site-row:hover {
  background: rgba(255, 255, 255, 0.03);
}

.site-row td {
  padding: 1.15rem 1.25rem;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}

.site-row:last-child td {
  border-bottom: none;
}

.site-row td:first-child strong,
.capacity {
  display: block;
  color: var(--text);
  font-size: 1.05rem;
  font-weight: 600;
}

.site-row td:first-child span,
.heartbeat {
  display: block;
}

.tag-stack {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
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

.chip-shell-accent {
  border-color: rgba(72, 132, 216, 0.3);
  background: rgba(31, 61, 110, 0.24);
}

.job-cell {
  display: grid;
  gap: 0.35rem;
}

.route-cell {
  display: grid;
  grid-template-columns: minmax(8rem, 1fr) auto;
  align-items: center;
  gap: 0.9rem;
}

.route-copy {
  color: var(--text);
}

.row-actions,
.row-actions-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
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

.button-secondary:disabled,
.button-danger:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace);
}

.muted-copy {
  color: var(--muted);
}

@media (max-width: 1200px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .metric-grid,
  .service-grid,
  .company-create,
  .company-assign,
  .company-ipc-form,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .section-heading,
  .company-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .company-actions,
  .header-actions {
    justify-content: flex-start;
  }

  .table-shell {
    overflow-x: auto;
  }

  .site-table {
    min-width: 1100px;
  }
}
</style>
