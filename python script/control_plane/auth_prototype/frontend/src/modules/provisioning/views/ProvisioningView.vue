<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import {
  cancelProvisioningJob,
  deleteProvisioningJob,
  deleteInventoryAsset,
  fetchInventoryAssets,
  fetchProvisioningJob,
  fetchProvisioningJobs,
  fetchSites,
  prepareProvisioningJob,
  registerInventoryAsset,
  requestInventoryScan,
  runProvisioningJob,
  type AssetRegistrationPayload,
  type ProvisioningJobsResponse,
} from "@/api/provisioning";
import { ApiError } from "@/api/client";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import { statusTone } from "@/mocks/controlPlane";
import { useSessionStore } from "@/stores/session";
import type {
  ApiInventoryAssetPayload,
  ApiProvisioningArtifactsPayload,
  ApiProvisioningJobPayload,
  ApiProvisioningWorkflowPayload,
  ApiProvisioningWorkflowStepPayload,
  ApiSitePayload,
} from "@/types/controlPlane";

const DEFAULT_EDGE_AGENT_MODBUS_HOST = "192.168.50.2";
const DEFAULT_EDGE_AGENT_NATS_URL = "tls://10.30.0.1:4222";
const DEFAULT_IPC_ALLOY_MIMIR_REMOTE_WRITE_URL = "http://10.42.1.4:9009/api/v1/push";
const DEFAULT_IPC_ALLOY_SCRAPE_INTERVAL = "15s";
const DEFAULT_IPC_ALLOY_SCRAPE_TIMEOUT = "10s";
const DEFAULT_IPC_ALLOY_TENANT = "classic";
const IPC_ALLOY_TENANT_OPTIONS = [DEFAULT_IPC_ALLOY_TENANT, "lts-1y", "lts-5y"] as const;
const LEGACY_EDGE_AGENT_NATS_URLS = new Set([
  "100.103.71.126:4222",
  "nats://100.103.71.126:4222",
  "tls://100.103.71.126:4222",
]);
const DEFAULT_REMOTE_UNLOCK_BROKER_URL = "https://10.30.0.1:8443";
const MODBUS_SIMULATOR_REPO_ROOT = "auth_prototype/modbus_simulator";
const MODBUS_SIMULATOR_SYNC_SCRIPT = `${MODBUS_SIMULATOR_REPO_ROOT}/scripts/sync_modbus_simulator.sh`;
const DEFAULT_MODBUS_SIMULATOR_REMOTE_DIR = "/home/cascadya/simulator_sbc";
const DEFAULT_MODBUS_SIMULATOR_SERVICE_NAME = "modbus-serveur.service";
const DEFAULT_MODBUS_SIMULATOR_SSH_USER = "cascadya";

interface ScanFormState {
  siteId: string;
  targetIp: string;
  teltonikaRouterIp: string;
  targetLabel: string;
  sshUsername: string;
  sshPort: string;
  downstreamProbeIp: string;
}

interface OnboardingFormState {
  useExistingSite: boolean;
  siteId: string;
  siteCode: string;
  siteName: string;
  city: string;
  hostname: string;
  inventoryHostname: string;
  managementIp: string;
  teltonikaRouterIp: string;
  managementInterface: string;
  uplinkInterface: string;
  gatewayIp: string;
  wireguardAddress: string;
  wireguardEndpoint: string;
  wireguardPeerPublicKey: string;
  wireguardPrivateKey: string;
  remoteUnlockBrokerUrl: string;
  notes: string;
  edgeAgentModbusHost: string;
  edgeAgentNatsUrl: string;
  edgeAgentProbeNatsUrl: string;
  edgeAgentProbeMonitoringUrl: string;
  ipcAlloyMimirRemoteWriteUrl: string;
  ipcAlloyScrapeInterval: string;
  ipcAlloyScrapeTimeout: string;
  ipcAlloyTenant: string;
  ipcAlloyRetentionProfile: string;
}

interface ProvisioningFormState {
  workflowKey: string;
  dispatchMode: "auto" | "manual";
  manualStepKey: string;
  inventoryGroup: string;
  remoteUnlockVaultSecretValue: string;
  remoteUnlockVaultSecretConfirmOverwrite: boolean;
}

interface ModbusSimulatorSyncState {
  host: string;
  sshUser: string;
  remoteDir: string;
  serviceName: string;
}

const route = useRoute();
const session = useSessionStore();

const loading = ref(false);
const actionKey = ref<string | null>(null);
const errorMessage = ref<string | null>(null);
const noticeMessage = ref<string | null>(null);

const sites = ref<ApiSitePayload[]>([]);
const assets = ref<ApiInventoryAssetPayload[]>([]);
const jobsState = ref<ProvisioningJobsResponse | null>(null);

const selectedAssetId = ref<number | null>(null);
const selectedJobId = ref<number | null>(null);

const scanForm = ref<ScanFormState>({
  siteId: "",
  targetIp: "",
  teltonikaRouterIp: "",
  targetLabel: "",
  sshUsername: "cascadya",
  sshPort: "22",
  downstreamProbeIp: "",
});

const onboardingForm = ref<OnboardingFormState>({
  useExistingSite: true,
  siteId: "",
  siteCode: "",
  siteName: "",
  city: "",
  hostname: "",
  inventoryHostname: "",
  managementIp: "",
  teltonikaRouterIp: "",
  managementInterface: "enp3s0",
  uplinkInterface: "enp2s0",
  gatewayIp: "",
  wireguardAddress: "",
  wireguardEndpoint: "",
  wireguardPeerPublicKey: "",
  wireguardPrivateKey: "",
  remoteUnlockBrokerUrl: DEFAULT_REMOTE_UNLOCK_BROKER_URL,
  notes: "",
  edgeAgentModbusHost: DEFAULT_EDGE_AGENT_MODBUS_HOST,
  edgeAgentNatsUrl: DEFAULT_EDGE_AGENT_NATS_URL,
  edgeAgentProbeNatsUrl: "",
  edgeAgentProbeMonitoringUrl: "",
  ipcAlloyMimirRemoteWriteUrl: "",
  ipcAlloyScrapeInterval: "",
  ipcAlloyScrapeTimeout: "",
  ipcAlloyTenant: DEFAULT_IPC_ALLOY_TENANT,
  ipcAlloyRetentionProfile: DEFAULT_IPC_ALLOY_TENANT,
});

const provisioningForm = ref<ProvisioningFormState>({
  workflowKey: "",
  dispatchMode: "auto",
  manualStepKey: "",
  inventoryGroup: "cascadya_ipc",
  remoteUnlockVaultSecretValue: "",
  remoteUnlockVaultSecretConfirmOverwrite: false,
});

const modbusSimulatorForm = ref<ModbusSimulatorSyncState>({
  host: DEFAULT_EDGE_AGENT_MODBUS_HOST,
  sshUser: DEFAULT_MODBUS_SIMULATOR_SSH_USER,
  remoteDir: DEFAULT_MODBUS_SIMULATOR_REMOTE_DIR,
  serviceName: DEFAULT_MODBUS_SIMULATOR_SERVICE_NAME,
});

function slugify(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function normalizeEdgeAgentNatsUrl(value?: string | null) {
  const cleaned = value?.trim();
  if (!cleaned) {
    return DEFAULT_EDGE_AGENT_NATS_URL;
  }
  return LEGACY_EDGE_AGENT_NATS_URLS.has(cleaned.replace(/\/+$/, "").toLowerCase())
    ? DEFAULT_EDGE_AGENT_NATS_URL
    : cleaned;
}

function normalizeIpcAlloyTenant(
  value?: string | null,
): (typeof IPC_ALLOY_TENANT_OPTIONS)[number] {
  const cleaned = value?.trim() as ((typeof IPC_ALLOY_TENANT_OPTIONS)[number] | undefined);
  return cleaned && IPC_ALLOY_TENANT_OPTIONS.includes(cleaned) ? cleaned : DEFAULT_IPC_ALLOY_TENANT;
}

function resolveIpcAlloyContract(
  tenant?: string | null,
  retentionProfile?: string | null,
): {
  tenant: (typeof IPC_ALLOY_TENANT_OPTIONS)[number];
  retentionProfile: (typeof IPC_ALLOY_TENANT_OPTIONS)[number];
} {
  const cleanedTenant = tenant?.trim() ?? "";
  const cleanedRetentionProfile = retentionProfile?.trim() ?? "";
  const profileSource = cleanedTenant || cleanedRetentionProfile || DEFAULT_IPC_ALLOY_TENANT;
  const effectiveProfile = normalizeIpcAlloyTenant(profileSource);
  return {
    tenant: effectiveProfile,
    retentionProfile: effectiveProfile,
  };
}

function toErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : "Une erreur inconnue est survenue.";
}

function toInt(value: string) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function workflowPhaseLabel(phase: string) {
  switch (phase) {
    case "prepare":
      return "Preparation";
    case "deploy":
      return "Deploiement";
    case "verify":
      return "Validation";
    case "cutover":
      return "Cutover";
    default:
      return phase;
  }
}

function workflowScopeLabel(scope: string) {
  switch (scope) {
    case "ipc":
      return "SSH IPC";
    case "broker":
      return "SSH broker";
    default:
      return "Controleur Ansible";
  }
}

function workflowStepStatus(step: ApiProvisioningWorkflowStepPayload) {
  return step.status ?? "locked";
}

function workflowStepStatusLabel(step: ApiProvisioningWorkflowStepPayload) {
  switch (workflowStepStatus(step)) {
    case "ready":
      return "Pret";
    case "running":
      return "En cours";
    case "succeeded":
      return "Valide";
    case "failed":
      return "Echec";
    default:
      return "Verrouille";
  }
}

function workflowStepDurationLabel(step: ApiProvisioningWorkflowStepPayload) {
  const startedAt = step.started_at ? Date.parse(step.started_at) : Number.NaN;
  const completedAt = step.completed_at ? Date.parse(step.completed_at) : Number.NaN;

  if (!Number.isFinite(startedAt)) {
    return null;
  }

  const endTimestamp = Number.isFinite(completedAt) ? completedAt : Date.now();
  const durationMs = Math.max(0, endTimestamp - startedAt);
  const totalSeconds = Math.floor(durationMs / 1000);

  if (totalSeconds < 1) {
    return workflowStepStatus(step) === "running" ? "en cours: < 1s" : "duree: < 1s";
  }

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const parts: string[] = [];

  if (hours > 0) {
    parts.push(`${hours}h`);
  }
  if (minutes > 0 || hours > 0) {
    parts.push(`${minutes}m`);
  }
  parts.push(`${seconds}s`);

  return workflowStepStatus(step) === "running"
    ? `en cours: ${parts.join(" ")}`
    : `duree: ${parts.join(" ")}`;
}

function workflowStepTimestampMeta(step: ApiProvisioningWorkflowStepPayload) {
  if (step.completed_at) {
    return {
      label: workflowStepStatus(step) === "failed" ? "terminee" : "validee",
      value: step.completed_at,
    };
  }

  if (step.started_at) {
    return {
      label: "demarrage",
      value: step.started_at,
    };
  }

  return null;
}

function bashQuote(value: string) {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function setOptionalProvisioningVar(
  target: Record<string, string>,
  key: string,
  value: string | null | undefined,
) {
  const cleaned = value?.trim();
  if (cleaned) {
    target[key] = cleaned;
    return;
  }
  delete target[key];
}

function delay(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function nextRunnableWorkflowStep(steps: ApiProvisioningWorkflowStepPayload[]) {
  return steps.find((step) => ["ready", "failed"].includes(workflowStepStatus(step))) ?? null;
}

function normalizedWorkflowStepsForJob(job: ApiProvisioningJobPayload) {
  return normalizeWorkflowSteps(job.context.workflow?.steps ?? [], job.status);
}

function completedWorkflowStepsForJob(job: ApiProvisioningJobPayload) {
  const completedSteps = job.context.progress?.completed_steps;
  if (typeof completedSteps === "number") {
    return completedSteps;
  }
  return normalizedWorkflowStepsForJob(job).filter((step) => step.status === "succeeded").length;
}

function nextRunnableStepForJob(job: ApiProvisioningJobPayload) {
  return nextRunnableWorkflowStep(normalizedWorkflowStepsForJob(job));
}

function jobProgressMarker(job: ApiProvisioningJobPayload) {
  return [
    job.status ?? "unknown",
    completedWorkflowStepsForJob(job),
    job.context.progress?.next_step_key ?? nextRunnableStepForJob(job)?.key ?? "none",
  ].join(":");
}

function normalizeWorkflowSteps(
  steps: ApiProvisioningWorkflowStepPayload[],
  jobStatus?: string | null,
) {
  if ((jobStatus ?? "").toLowerCase() === "succeeded") {
    return steps.map((step) => ({
      ...step,
      status: "succeeded" as const,
      error_message: null,
    }));
  }

  let unlocked = false;
  return steps.map((step) => {
    const currentStatus = step.status;
    if (currentStatus) {
      if (currentStatus !== "succeeded") {
        unlocked = true;
      }
      return step;
    }
    if (!unlocked) {
      unlocked = true;
      return { ...step, status: "ready" as const };
    }
    return { ...step, status: "locked" as const };
  });
}

const routeSiteKey = computed(() => (typeof route.params.siteId === "string" ? route.params.siteId : null));
const scopedSite = computed(() => {
  const key = routeSiteKey.value?.trim().toLowerCase();
  if (!key) {
    return null;
  }
  return (
    sites.value.find(
      (site) => String(site.id) === key || site.code.toLowerCase() === key || slugify(site.name) === key,
    ) ?? null
  );
});
const scopedSiteId = computed(() => scopedSite.value?.id ?? null);

const visibleAssets = computed(() =>
  scopedSiteId.value === null ? assets.value : assets.value.filter((asset) => asset.site?.id === scopedSiteId.value),
);
const visibleJobs = computed(() => {
  const jobs = jobsState.value?.jobs ?? [];
  return scopedSiteId.value === null ? jobs : jobs.filter((job) => job.site?.id === scopedSiteId.value);
});

const selectedAsset = computed(() => visibleAssets.value.find((asset) => asset.id === selectedAssetId.value) ?? null);
const selectedJob = computed(() => visibleJobs.value.find((job) => job.id === selectedJobId.value) ?? null);
const workflowCatalog = computed(() => jobsState.value?.workflow_catalog ?? []);
const selectedWorkflowKey = computed(
  () => provisioningForm.value.workflowKey || jobsState.value?.default_workflow_key || workflowCatalog.value[0]?.key || "",
);
const selectedWorkflow = computed<ApiProvisioningWorkflowPayload | null>(
  () =>
    workflowCatalog.value.find((workflow) => workflow.key === selectedWorkflowKey.value) ??
    workflowCatalog.value[0] ??
    null,
);
const selectedWorkflowKeyForLaunch = computed(() => selectedWorkflowKey.value || null);
const isManualDispatchMode = computed(() => provisioningForm.value.dispatchMode === "manual");
const selectedManualStepDefinition = computed<ApiProvisioningWorkflowStepPayload | null>(
  () =>
    selectedWorkflow.value?.steps.find((step) => step.key === provisioningForm.value.manualStepKey) ??
    selectedWorkflow.value?.steps[0] ??
    null,
);
const selectedWorkflowRequiresVaultSeed = computed(
  () =>
    selectedWorkflow.value?.steps.some(
      (step) => step.playbook_name === "remote-unlock-seed-vault-secret.yml",
    ) ?? false,
);
const selectedOperationRequiresVaultSeed = computed(() =>
  isManualDispatchMode.value
    ? selectedManualStepDefinition.value?.playbook_name === "remote-unlock-seed-vault-secret.yml"
    : selectedWorkflowRequiresVaultSeed.value,
);
const selectedJobWorkflow = computed<ApiProvisioningWorkflowPayload | null>(() => {
  const workflow = selectedJob.value?.context.workflow;
  if (!workflow) {
    return null;
  }
  return {
    ...workflow,
    steps: normalizeWorkflowSteps(workflow.steps ?? [], selectedJob.value?.status),
  };
});
const selectedJobArtifacts = computed<ApiProvisioningArtifactsPayload | null>(() => selectedJob.value?.context.artifacts ?? null);
const selectedJobSteps = computed(() => selectedJobWorkflow.value?.steps ?? []);
const selectedJobProgress = computed(() => {
  if (selectedJob.value?.status === "succeeded" && selectedJobSteps.value.length > 0) {
    return {
      completed_steps: selectedJobSteps.value.length,
      total_steps: selectedJobSteps.value.length,
      next_step_key: null,
      next_step_label: null,
    };
  }
  const progress = selectedJob.value?.context.progress;
  if (progress) {
    return progress;
  }
  const completedSteps = selectedJobSteps.value.filter((step) => step.status === "succeeded").length;
  const nextStep = selectedJobSteps.value.find((step) => ["ready", "failed"].includes(workflowStepStatus(step))) ?? null;
  return {
    completed_steps: completedSteps,
    total_steps: selectedJobSteps.value.length,
    next_step_key: nextStep?.key ?? null,
    next_step_label: nextStep?.label ?? null,
  };
});
const selectedJobReady = computed(() => selectedJob.value?.context.ready_for_real_execution === true);
const nextRunnableStep = computed(() => {
  if (selectedJob.value && ["succeeded", "cancelled", "superseded"].includes(selectedJob.value.status)) {
    return null;
  }
  return nextRunnableWorkflowStep(selectedJobSteps.value);
});
const selectedAssetAutoJob = computed(() => {
  const assetId = selectedAsset.value?.id;
  if (!assetId) {
    return null;
  }
  const activeJobs = (jobsState.value?.jobs ?? [])
    .filter(
      (job) =>
        job.asset_id === assetId &&
        ["prepared", "running"].includes(job.status) &&
        job.dispatch_mode !== "manual" &&
        (selectedWorkflowKeyForLaunch.value === null || job.playbook_name === selectedWorkflowKeyForLaunch.value),
    )
    .sort((left, right) => right.id - left.id);
  return activeJobs[0] ?? null;
});
const selectedAssetManualJob = computed(() => {
  const assetId = selectedAsset.value?.id;
  if (!assetId) {
    return null;
  }
  const openJobs = (jobsState.value?.jobs ?? [])
    .filter(
      (job) =>
        job.asset_id === assetId &&
        ["prepared", "running", "failed"].includes(job.status) &&
        job.dispatch_mode === "manual" &&
        (selectedWorkflowKeyForLaunch.value === null || job.playbook_name === selectedWorkflowKeyForLaunch.value),
    )
    .sort((left, right) => right.id - left.id);
  return openJobs[0] ?? null;
});
const selectedAssetLaunchJob = computed(() =>
  isManualDispatchMode.value ? selectedAssetManualJob.value : selectedAssetAutoJob.value,
);
const selectedAssetLabel = computed(
  () => selectedAsset.value?.inventory_hostname ?? selectedAsset.value?.hostname ?? null,
);
const suggestedSimulatorHost = computed(() => {
  const selectedAssetHost = selectedAsset.value?.provisioning_vars?.edge_agent_modbus_host?.trim();
  const onboardingHost = onboardingForm.value.edgeAgentModbusHost.trim();
  return selectedAssetHost || onboardingHost || DEFAULT_EDGE_AGENT_MODBUS_HOST;
});
const modbusSimulatorSyncCommand = computed(() =>
  [
    "cd <repo-root>/control_plane",
    `SIMULATOR_USER=${bashQuote(modbusSimulatorForm.value.sshUser)} \\`,
    `REMOTE_DIR=${bashQuote(modbusSimulatorForm.value.remoteDir)} \\`,
    `SERVICE_NAME=${bashQuote(modbusSimulatorForm.value.serviceName)} \\`,
    `bash ${MODBUS_SIMULATOR_SYNC_SCRIPT} ${bashQuote(modbusSimulatorForm.value.host)}`,
  ].join("\n"),
);
const modbusSimulatorManualCommand = computed(() =>
  [
    "cd <repo-root>/control_plane",
    `rsync -av --delete auth_prototype/modbus_simulator/src/ ${bashQuote(`${modbusSimulatorForm.value.sshUser}@${modbusSimulatorForm.value.host}:${modbusSimulatorForm.value.remoteDir}/`)}`,
    `scp auth_prototype/modbus_simulator/systemd/${modbusSimulatorForm.value.serviceName} ${bashQuote(`${modbusSimulatorForm.value.sshUser}@${modbusSimulatorForm.value.host}:${modbusSimulatorForm.value.remoteDir}/${modbusSimulatorForm.value.serviceName}`)}`,
    `ssh ${bashQuote(`${modbusSimulatorForm.value.sshUser}@${modbusSimulatorForm.value.host}`)} "sudo install -m 0644 '${modbusSimulatorForm.value.remoteDir}/${modbusSimulatorForm.value.serviceName}' '/etc/systemd/system/${modbusSimulatorForm.value.serviceName}' && sudo systemctl daemon-reload && sudo systemctl restart '${modbusSimulatorForm.value.serviceName}' && sudo systemctl status '${modbusSimulatorForm.value.serviceName}' --no-pager"`,
  ].join("\n"),
);
const modbusSimulatorVerifyCommand = computed(() =>
  [
    `ssh ${bashQuote(`${modbusSimulatorForm.value.sshUser}@${modbusSimulatorForm.value.host}`)} "systemctl status '${modbusSimulatorForm.value.serviceName}' --no-pager"`,
    `ssh ${bashQuote(`${modbusSimulatorForm.value.sshUser}@${modbusSimulatorForm.value.host}`)} "ls -lah '${modbusSimulatorForm.value.remoteDir}'"`,
    `ssh ${bashQuote(`${modbusSimulatorForm.value.sshUser}@${modbusSimulatorForm.value.host}`)} "journalctl -u '${modbusSimulatorForm.value.serviceName}' -n 80 --no-pager"`,
  ].join("\n"),
);

const canCreateSite = computed(() => session.hasPermission("site:write"));
const canLaunchProvisioning = computed(
  () => session.hasPermission("provision:prepare") && session.hasPermission("provision:run"),
);
const canManageProvisioningJobs = computed(() => session.hasPermission("provision:cancel"));
const canDeleteSelectedAsset = computed(() => {
  if (!selectedAsset.value) {
    return false;
  }
  if (selectedAsset.value.registration_status === "discovered") {
    return session.hasPermission("inventory:scan");
  }
  return session.hasPermission("provision:prepare");
});
const executionMode = computed(() => jobsState.value?.execution_mode ?? "mock");
const playbookRoot = computed(() => jobsState.value?.playbook_root ?? null);
const launchButtonDisabled = computed(
  () => {
    const resumingActiveRealJob = executionMode.value !== "mock" && Boolean(selectedAssetAutoJob.value);
    return (
      !selectedAsset.value ||
      selectedAsset.value.registration_status === "discovered" ||
      !canLaunchProvisioning.value ||
      (!resumingActiveRealJob && !selectedWorkflowKeyForLaunch.value) ||
      (isManualDispatchMode.value && !selectedManualStepDefinition.value) ||
      (!resumingActiveRealJob &&
        selectedOperationRequiresVaultSeed.value &&
        !provisioningForm.value.remoteUnlockVaultSecretValue.trim()) ||
      actionKey.value === `launch-${selectedAsset.value?.id ?? 0}`
    );
  },
);
const launchButtonLabel = computed(() => {
  if (!selectedAsset.value) {
    return "Selectionne un IPC";
  }
  if (selectedAsset.value.registration_status === "discovered") {
    return "Enregistrer l'IPC d'abord";
  }
  if (isManualDispatchMode.value) {
    if (!selectedManualStepDefinition.value) {
      return "Selectionner un playbook";
    }
    if (selectedOperationRequiresVaultSeed.value && !provisioningForm.value.remoteUnlockVaultSecretValue.trim()) {
      return "Renseigner le secret Vault";
    }
    if (actionKey.value === `launch-${selectedAsset.value.id}`) {
      return "Execution manuelle...";
    }
    if (selectedAssetManualJob.value) {
      return `Executer ${selectedManualStepDefinition.value.playbook_name} dans le job #${selectedAssetManualJob.value.id}`;
    }
    return `Executer ${selectedManualStepDefinition.value.playbook_name}`;
  }
  if (selectedAssetAutoJob.value) {
    if (actionKey.value === `launch-${selectedAsset.value.id}`) {
      return executionMode.value === "mock" ? "Provisionnement..." : "Reprise...";
    }
    return executionMode.value === "mock"
      ? "Relancer le provisionnement complet"
      : `Reprendre le job #${selectedAssetAutoJob.value.id}`;
  }
  if (selectedOperationRequiresVaultSeed.value && !provisioningForm.value.remoteUnlockVaultSecretValue.trim()) {
    return "Renseigner le secret Vault";
  }
  return actionKey.value === `launch-${selectedAsset.value.id}` ? "Provisionnement..." : "Executer le provisionnement complet";
});
const selectedJobCanBeCancelled = computed(() => {
  const job = selectedJob.value;
  if (!job || !canManageProvisioningJobs.value) {
    return false;
  }
  return ["prepared", "running", "failed"].includes(job.status);
});
const selectedJobCanBeDeleted = computed(() => {
  const job = selectedJob.value;
  if (!job || !canManageProvisioningJobs.value) {
    return false;
  }
  return job.status !== "running";
});

const discoveredCount = computed(
  () => visibleAssets.value.filter((asset) => asset.registration_status === "discovered").length,
);
const registeredCount = computed(
  () => visibleAssets.value.filter((asset) => asset.registration_status !== "discovered").length,
);

function resetVaultSeedInputs() {
  provisioningForm.value.remoteUnlockVaultSecretValue = "";
  provisioningForm.value.remoteUnlockVaultSecretConfirmOverwrite = false;
}

function syncManualStepSelection() {
  const availableSteps = selectedWorkflow.value?.steps ?? [];
  if (!availableSteps.length) {
    provisioningForm.value.manualStepKey = "";
    return;
  }
  const hasCurrentSelection = availableSteps.some((step) => step.key === provisioningForm.value.manualStepKey);
  if (!hasCurrentSelection) {
    provisioningForm.value.manualStepKey = availableSteps[0].key;
  }
}

function applySuggestedSimulatorHost() {
  modbusSimulatorForm.value.host = suggestedSimulatorHost.value;
}

function syncFormFromAsset(asset: ApiInventoryAssetPayload) {
  const currentSite = asset.site ? sites.value.find((site) => site.id === asset.site?.id) ?? null : null;
  const ipcAlloyContract = resolveIpcAlloyContract(
    asset.provisioning_vars.ipc_alloy_mimir_tenant,
    asset.provisioning_vars.ipc_alloy_retention_profile,
  );
  onboardingForm.value = {
    useExistingSite: Boolean(asset.site),
    siteId: currentSite ? String(currentSite.id) : scopedSite.value ? String(scopedSite.value.id) : "",
    siteCode: currentSite?.code ?? "",
    siteName: currentSite?.name ?? "",
    city: currentSite?.city ?? "",
    hostname: asset.hostname ?? "",
    inventoryHostname: asset.inventory_hostname ?? "",
    managementIp: asset.management_ip ?? asset.ip_address ?? "",
    teltonikaRouterIp: asset.teltonika_router_ip ?? "",
    managementInterface: asset.management_interface ?? "enp3s0",
    uplinkInterface: asset.uplink_interface ?? "enp2s0",
    gatewayIp: asset.gateway_ip ?? "",
    wireguardAddress: asset.wireguard_address ?? "",
    wireguardEndpoint: asset.provisioning_vars.network_wireguard_endpoint ?? "",
    wireguardPeerPublicKey: asset.provisioning_vars.network_wireguard_peer_public_key ?? "",
    wireguardPrivateKey: asset.provisioning_vars.network_wireguard_private_key ?? "",
    remoteUnlockBrokerUrl: asset.provisioning_vars.remote_unlock_broker_url ?? DEFAULT_REMOTE_UNLOCK_BROKER_URL,
    notes: asset.notes,
    edgeAgentModbusHost: asset.provisioning_vars.edge_agent_modbus_host ?? DEFAULT_EDGE_AGENT_MODBUS_HOST,
    edgeAgentNatsUrl: normalizeEdgeAgentNatsUrl(asset.provisioning_vars.edge_agent_nats_url),
    edgeAgentProbeNatsUrl: asset.provisioning_vars.edge_agent_probe_nats_url ?? "",
    edgeAgentProbeMonitoringUrl: asset.provisioning_vars.edge_agent_probe_monitoring_url ?? "",
    ipcAlloyMimirRemoteWriteUrl: asset.provisioning_vars.ipc_alloy_mimir_remote_write_url ?? "",
    ipcAlloyScrapeInterval: asset.provisioning_vars.ipc_alloy_scrape_interval ?? "",
    ipcAlloyScrapeTimeout: asset.provisioning_vars.ipc_alloy_scrape_timeout ?? "",
    ipcAlloyTenant: ipcAlloyContract.tenant,
    ipcAlloyRetentionProfile: ipcAlloyContract.retentionProfile,
  };
}

function selectAsset(asset: ApiInventoryAssetPayload) {
  selectedAssetId.value = asset.id;
  resetVaultSeedInputs();
  syncFormFromAsset(asset);
}

function selectJob(job: ApiProvisioningJobPayload) {
  selectedJobId.value = job.id;
}

function mergeProvisioningJob(job: ApiProvisioningJobPayload) {
  if (!jobsState.value) {
    return;
  }
  const existingIndex = jobsState.value.jobs.findIndex((item) => item.id === job.id);
  if (existingIndex >= 0) {
    jobsState.value.jobs.splice(existingIndex, 1, job);
    return;
  }
  jobsState.value.jobs.unshift(job);
}

const LIVE_JOB_POLL_INTERVAL_MS = 1500;
let liveJobPollTimer: number | null = null;
let liveJobPollJobId: number | null = null;
let liveJobPollInFlight = false;

function stopLiveJobPolling() {
  if (liveJobPollTimer !== null) {
    window.clearInterval(liveJobPollTimer);
    liveJobPollTimer = null;
  }
  liveJobPollJobId = null;
}

function startLiveJobPolling(jobId: number) {
  if (liveJobPollTimer !== null && liveJobPollJobId === jobId) {
    return;
  }
  stopLiveJobPolling();
  liveJobPollJobId = jobId;
  liveJobPollTimer = window.setInterval(async () => {
    if (liveJobPollInFlight) {
      return;
    }
    liveJobPollInFlight = true;
    try {
      const refreshed = await refreshProvisioningJob(jobId);
      if (!refreshed || refreshed.status !== "running" || selectedJobId.value !== jobId) {
        stopLiveJobPolling();
      }
    } catch {
      // Ignore transient polling failures while the current playbook step is still streaming.
    } finally {
      liveJobPollInFlight = false;
    }
  }, LIVE_JOB_POLL_INTERVAL_MS);
}

async function loadData() {
  loading.value = true;
  errorMessage.value = null;
  try {
    const [sitesResponse, assetsResponse, jobsResponse] = await Promise.all([
      fetchSites(),
      fetchInventoryAssets(),
      fetchProvisioningJobs(),
    ]);
    sites.value = sitesResponse.sites;
    assets.value = assetsResponse.assets;
    jobsState.value = jobsResponse;
    const workflowKeys = new Set(jobsResponse.workflow_catalog.map((workflow) => workflow.key));
    if (!workflowKeys.has(provisioningForm.value.workflowKey)) {
      provisioningForm.value.workflowKey = jobsResponse.default_workflow_key ?? jobsResponse.workflow_catalog[0]?.key ?? "";
    }
    syncManualStepSelection();

    if (!scanForm.value.siteId && scopedSite.value) {
      scanForm.value.siteId = String(scopedSite.value.id);
    }
    if (!selectedAsset.value && visibleAssets.value.length) {
      selectAsset(visibleAssets.value[0]);
    }
    if (!selectedJob.value && visibleJobs.value.length) {
      selectJob(visibleJobs.value[0]);
    }
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

async function refreshProvisioningJob(jobId: number) {
  const refreshed = await fetchProvisioningJob(jobId);
  mergeProvisioningJob(refreshed);
  if (refreshed) {
    selectJob(refreshed);
  }
  return refreshed;
}

async function waitForProvisioningJobTransition(
  job: ApiProvisioningJobPayload,
  options?: {
    timeoutMs?: number;
    intervalMs?: number;
  },
) {
  const timeoutMs = options?.timeoutMs ?? 120000;
  const intervalMs = options?.intervalMs ?? 3000;
  const baselineMarker = jobProgressMarker(job);
  const deadline = Date.now() + timeoutMs;
  let latestJob = job;

  while (Date.now() < deadline) {
    await delay(intervalMs);
    const refreshed = await refreshProvisioningJob(job.id);
    if (!refreshed) {
      return latestJob;
    }
    latestJob = refreshed;
    if (jobProgressMarker(refreshed) !== baselineMarker) {
      return refreshed;
    }
    if (["failed", "succeeded"].includes(refreshed.status)) {
      return refreshed;
    }
    if (nextRunnableStepForJob(refreshed)) {
      return refreshed;
    }
  }

  return latestJob;
}

async function runProvisioningJobWithLiveUpdates(
  job: ApiProvisioningJobPayload,
  pollIntervalMs = 1500,
  stepKey?: string,
): Promise<ApiProvisioningJobPayload> {
  let settled = false;
  let runResult: ApiProvisioningJobPayload | null = null;
  let runError: unknown = null;

  const runPromise = runProvisioningJob(job.id, stepKey ? { step_key: stepKey } : undefined).then(
    (result) => {
      settled = true;
      runResult = result;
      return result;
    },
    (error) => {
      settled = true;
      runError = error;
      return null;
    },
  );

  while (!settled) {
    await delay(pollIntervalMs);
    try {
      const refreshed = await refreshProvisioningJob(job.id);
      if (refreshed) {
        job = refreshed;
      }
    } catch {
      // Ignore transient polling failures while the step is still executing.
    }
  }

  await runPromise;

  if (runResult) {
    mergeProvisioningJob(runResult);
    return runResult;
  }

  throw runError instanceof Error ? runError : new Error("Execution du job interrompue sans retour exploitable.");
}

async function continueProvisioningChain(job: ApiProvisioningJobPayload) {
  let currentJob = job;
  const maxIterations = Math.max((currentJob.context.workflow?.steps?.length ?? 0) + 4, 6);
  let iteration = 0;

  while (["prepared", "running", "failed"].includes(currentJob.status)) {
    iteration += 1;
    if (iteration > maxIterations) {
      throw new Error(
        `Le job #${currentJob.id} n'avance plus. Consulte les logs affiches ci-dessous pour identifier le dernier etat connu.`,
      );
    }

    const nextStep = nextRunnableStepForJob(currentJob);
    if (!nextStep) {
      if (currentJob.status !== "running") {
        break;
      }

      const baselineMarker = jobProgressMarker(currentJob);
      noticeMessage.value = `Le job #${currentJob.id} termine une etape deja lancee. Attente de la reprise automatique.`;
      currentJob = await waitForProvisioningJobTransition(currentJob);
      selectJob(currentJob);

      if (currentJob.status === "failed") {
        throw new Error(
          currentJob.error_message ??
            `Le job #${currentJob.id} a echoue pendant une reprise automatique. Consulte les logs affiches dans la section Jobs.`,
        );
      }
      if (currentJob.status === "succeeded") {
        noticeMessage.value = `Provisionnement termine pour ${selectedAsset.value?.inventory_hostname ?? selectedAsset.value?.hostname ?? "cet IPC"}.`;
        break;
      }
      if (jobProgressMarker(currentJob) === baselineMarker) {
        throw new Error(
          `Le job #${currentJob.id} n'a pas evolue apres une attente de reprise. Verifie les logs du job et la connectivite entre le navigateur et la VM control-panel.`,
        );
      }
      continue;
    }

    const previousCompletedSteps = completedWorkflowStepsForJob(currentJob);
    const previousProgressMarker = jobProgressMarker(currentJob);
    noticeMessage.value = `Execution de l'etape ${nextStep.order ?? "?"}: ${nextStep.label}`;
    await delay(350);

    try {
      const executed = await runProvisioningJobWithLiveUpdates(currentJob);
      await loadData();
      currentJob = jobsState.value?.jobs.find((item) => item.id === executed.id) ?? executed;
      selectJob(currentJob);
    } catch (error) {
      currentJob = await waitForProvisioningJobTransition(currentJob);
      selectJob(currentJob);

      if (currentJob.status === "failed") {
        throw new Error(
          currentJob.error_message ??
            `Le job #${currentJob.id} a echoue sur ${nextStep.playbook_name}. Consulte les logs affiches dans la section Jobs.`,
        );
      }

      if (
        currentJob.status === "succeeded" ||
        completedWorkflowStepsForJob(currentJob) > previousCompletedSteps ||
        jobProgressMarker(currentJob) !== previousProgressMarker
      ) {
        noticeMessage.value = `Connexion interrompue pendant ${nextStep.label}, mais le job #${currentJob.id} a repris sa progression.`;
      } else {
        throw error;
      }
    }

    if (currentJob.status === "failed") {
      throw new Error(
        currentJob.error_message ??
          `Le job #${currentJob.id} a echoue sur ${nextStep.playbook_name}. Consulte les logs affiches dans la section Jobs.`,
      );
    }

    const currentCompletedSteps = completedWorkflowStepsForJob(currentJob);
    if (currentJob.status !== "succeeded" && currentCompletedSteps <= previousCompletedSteps) {
      throw new Error(
        `Le job #${currentJob.id} n'a pas progresse apres l'execution de ${nextStep.playbook_name}. Verifie les logs du job et la configuration du runner.`,
      );
    }

    if (currentJob.status === "succeeded") {
      noticeMessage.value = `Provisionnement termine pour ${selectedAsset.value?.inventory_hostname ?? selectedAsset.value?.hostname ?? "cet IPC"}.`;
      break;
    }
  }

  return currentJob;
}

async function submitScan() {
  actionKey.value = "scan";
  errorMessage.value = null;
  noticeMessage.value = null;
  try {
    const response = await requestInventoryScan({
      site_id: toInt(scanForm.value.siteId),
      target_ip: scanForm.value.targetIp,
      teltonika_router_ip: scanForm.value.teltonikaRouterIp || undefined,
      target_label: scanForm.value.targetLabel || undefined,
      ssh_username: scanForm.value.sshUsername || undefined,
      ssh_port: toInt(scanForm.value.sshPort) ?? undefined,
      downstream_probe_ip: scanForm.value.downstreamProbeIp || undefined,
      asset_type: "industrial_pc",
    });
    const probeMode =
      typeof response.scan.summary?.probe_mode === "string" ? response.scan.summary.probe_mode : "inconnu";
    noticeMessage.value = `Scan termine en mode ${probeMode}. MAC detectee: ${response.asset.mac_address ?? "n/a"}.`;
    await loadData();
    const asset = assets.value.find((item) => item.id === response.asset.id);
    if (asset) {
      selectAsset(asset);
    }
    scanForm.value.targetIp = "";
    scanForm.value.targetLabel = "";
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    actionKey.value = null;
  }
}

async function submitRegistration() {
  if (!selectedAsset.value) {
    errorMessage.value = "Selectionne d'abord un candidat.";
    return;
  }
  actionKey.value = `register-${selectedAsset.value.id}`;
  errorMessage.value = null;
  noticeMessage.value = null;
  try {
    const nextProvisioningVars: Record<string, string> = {
      ...(selectedAsset.value.provisioning_vars ?? {}),
      remote_unlock_transport_mode: "wireguard",
      remote_unlock_management_interface: onboardingForm.value.managementInterface,
      remote_unlock_uplink_interface: onboardingForm.value.uplinkInterface,
      edge_agent_modbus_host: onboardingForm.value.edgeAgentModbusHost,
      edge_agent_nats_url: normalizeEdgeAgentNatsUrl(onboardingForm.value.edgeAgentNatsUrl),
    };

    setOptionalProvisioningVar(
      nextProvisioningVars,
      "remote_unlock_broker_url",
      onboardingForm.value.remoteUnlockBrokerUrl,
    );
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "network_wireguard_endpoint",
      onboardingForm.value.wireguardEndpoint,
    );
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "network_wireguard_peer_public_key",
      onboardingForm.value.wireguardPeerPublicKey,
    );
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "network_wireguard_private_key",
      onboardingForm.value.wireguardPrivateKey,
    );
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "edge_agent_probe_nats_url",
      onboardingForm.value.edgeAgentProbeNatsUrl,
    );
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "edge_agent_probe_monitoring_url",
      onboardingForm.value.edgeAgentProbeMonitoringUrl,
    );
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "ipc_alloy_mimir_remote_write_url",
      onboardingForm.value.ipcAlloyMimirRemoteWriteUrl,
    );
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "ipc_alloy_scrape_interval",
      onboardingForm.value.ipcAlloyScrapeInterval,
    );
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "ipc_alloy_scrape_timeout",
      onboardingForm.value.ipcAlloyScrapeTimeout,
    );
    const ipcAlloyContract = resolveIpcAlloyContract(
      onboardingForm.value.ipcAlloyTenant,
      onboardingForm.value.ipcAlloyRetentionProfile,
    );
    onboardingForm.value.ipcAlloyTenant = ipcAlloyContract.tenant;
    onboardingForm.value.ipcAlloyRetentionProfile = ipcAlloyContract.retentionProfile;
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "ipc_alloy_mimir_tenant",
      ipcAlloyContract.tenant,
    );
    setOptionalProvisioningVar(
      nextProvisioningVars,
      "ipc_alloy_retention_profile",
      ipcAlloyContract.retentionProfile,
    );

    const payload: AssetRegistrationPayload = {
      site_id: onboardingForm.value.useExistingSite ? toInt(onboardingForm.value.siteId) : null,
      site_code: onboardingForm.value.useExistingSite ? undefined : onboardingForm.value.siteCode,
      site_name: onboardingForm.value.useExistingSite ? undefined : onboardingForm.value.siteName,
      city: onboardingForm.value.city || undefined,
      hostname: onboardingForm.value.hostname,
      inventory_hostname: onboardingForm.value.inventoryHostname,
      management_ip: onboardingForm.value.managementIp || undefined,
      teltonika_router_ip: onboardingForm.value.teltonikaRouterIp || undefined,
      management_interface: onboardingForm.value.managementInterface || undefined,
      uplink_interface: onboardingForm.value.uplinkInterface || undefined,
      gateway_ip: onboardingForm.value.gatewayIp || undefined,
      wireguard_address: onboardingForm.value.wireguardAddress || undefined,
      notes: onboardingForm.value.notes || undefined,
      provisioning_vars: nextProvisioningVars,
    };
    const asset = await registerInventoryAsset(selectedAsset.value.id, payload);
    noticeMessage.value = `IPC ${asset.inventory_hostname ?? asset.hostname ?? asset.id} enregistre.`;
    await loadData();
    const refreshed = assets.value.find((item) => item.id === asset.id);
    if (refreshed) {
      selectAsset(refreshed);
    }
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    actionKey.value = null;
  }
}

async function submitPrepareJob(dispatchMode: "auto" | "manual" = provisioningForm.value.dispatchMode) {
  if (!selectedAsset.value) {
    errorMessage.value = "Aucun IPC selectionne.";
    return null;
  }
  if (selectedAsset.value.registration_status === "discovered") {
    errorMessage.value = "Enregistre d'abord l'IPC avant de lancer le provisionnement complet.";
    return null;
  }
  const requiresVaultSeed =
    dispatchMode === "manual"
      ? selectedManualStepDefinition.value?.playbook_name === "remote-unlock-seed-vault-secret.yml"
      : selectedWorkflowRequiresVaultSeed.value;
  if (requiresVaultSeed && !provisioningForm.value.remoteUnlockVaultSecretValue.trim()) {
    errorMessage.value =
      "Renseigne d'abord le secret LUKS a publier dans Vault pour que le workflow soit autonome.";
    return null;
  }
  errorMessage.value = null;
  try {
    const job = await prepareProvisioningJob({
      asset_id: selectedAsset.value.id,
      workflow_key: selectedWorkflowKeyForLaunch.value || undefined,
      dispatch_mode: dispatchMode,
      inventory_group: provisioningForm.value.inventoryGroup || "cascadya_ipc",
      remote_unlock_vault_secret_value: requiresVaultSeed
        ? provisioningForm.value.remoteUnlockVaultSecretValue.trim()
        : undefined,
      remote_unlock_vault_secret_confirm_overwrite: requiresVaultSeed
        ? provisioningForm.value.remoteUnlockVaultSecretConfirmOverwrite
        : undefined,
    });
    resetVaultSeedInputs();
    await loadData();
    const refreshed = jobsState.value?.jobs.find((item) => item.id === job.id);
    if (refreshed) {
      selectJob(refreshed);
      return refreshed;
    }
    selectJob(job);
    return job;
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
    return null;
  }
}

async function submitLaunchProvisioning() {
  if (!selectedAsset.value) {
    errorMessage.value = "Aucun IPC selectionne.";
    return;
  }
  if (selectedAsset.value.registration_status === "discovered") {
    errorMessage.value = "Enregistre d'abord l'IPC avant de lancer le provisionnement complet.";
    return;
  }

  if (isManualDispatchMode.value) {
    const manualStep = selectedManualStepDefinition.value;
    if (!manualStep) {
      errorMessage.value = "Selectionne d'abord un playbook a executer en mode manuel.";
      return;
    }

    actionKey.value = `launch-${selectedAsset.value.id}`;
    errorMessage.value = null;
    noticeMessage.value = null;

    try {
      let currentJob = selectedAssetManualJob.value;
      if (currentJob) {
        currentJob = (await refreshProvisioningJob(currentJob.id)) ?? currentJob;
        selectJob(currentJob);
      } else {
        const preparedJob = await submitPrepareJob("manual");
        if (!preparedJob) {
          return;
        }
        currentJob = preparedJob;
        noticeMessage.value = `Job manuel #${currentJob.id} initialise pour ${manualStep.label}.`;
      }

      const executed = await runProvisioningJobWithLiveUpdates(currentJob, 1500, manualStep.key);
      await loadData();
      currentJob = jobsState.value?.jobs.find((item) => item.id === executed.id) ?? executed;
      selectJob(currentJob);

      const executedStep =
        normalizedWorkflowStepsForJob(currentJob).find((step) => step.key === manualStep.key) ?? null;
      if (currentJob.status === "failed" || executedStep?.status === "failed") {
        throw new Error(
          currentJob.error_message ??
            executedStep?.error_message ??
            `Le playbook ${manualStep.playbook_name} a echoue. Consulte les logs du job #${currentJob.id}.`,
        );
      }

      noticeMessage.value = `Playbook manuel execute: ${manualStep.label} (job #${currentJob.id}).`;
    } catch (error) {
      errorMessage.value = toErrorMessage(error);
    } finally {
      actionKey.value = null;
    }
    return;
  }

  actionKey.value = `launch-${selectedAsset.value.id}`;
  errorMessage.value = null;
  noticeMessage.value = null;

  try {
    const previousActiveJob = selectedAssetAutoJob.value;
    if (executionMode.value !== "mock" && previousActiveJob) {
      const resumableJob = (await refreshProvisioningJob(previousActiveJob.id)) ?? previousActiveJob;
      selectJob(resumableJob);
      noticeMessage.value = `Reprise du job #${resumableJob.id} a partir de l'etape en attente.`;
      await continueProvisioningChain(resumableJob);
      return;
    }

    const preparedJob = await submitPrepareJob();
    if (!preparedJob) {
      return;
    }
    const job = preparedJob;
    noticeMessage.value =
      executionMode.value === "mock" && previousActiveJob
        ? `Nouveau cycle initialise. L'ancien job #${previousActiveJob.id} a ete supersede automatiquement.`
        : `Workflow ${job.context.workflow?.label ?? selectedWorkflow.value?.label ?? job.playbook_name} initialise.`;
    await continueProvisioningChain(job);
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    actionKey.value = null;
  }
}

async function submitCancelJob(job = selectedJob.value) {
  if (!job) {
    errorMessage.value = "Aucun job selectionne.";
    return;
  }
  if (!canManageProvisioningJobs.value) {
    errorMessage.value = "Le role courant ne permet pas d'abandonner un job.";
    return;
  }
  if (!["prepared", "running", "failed"].includes(job.status)) {
    errorMessage.value = `Le job #${job.id} n'est plus annulable (statut ${job.status}).`;
    return;
  }

  const confirmed = window.confirm(
    job.execution_mode === "real"
      ? `Abandonner le job #${job.id} ? Cela liberera l'IPC dans le dashboard. Si un ansible-playbook tourne encore sur la VM, un redemarrage du service peut rester necessaire pour le couper.`
      : `Abandonner le job #${job.id} et le sortir de la file active ?`,
  );
  if (!confirmed) {
    return;
  }

  actionKey.value = `cancel-job-${job.id}`;
  errorMessage.value = null;
  noticeMessage.value = null;
  try {
    const cancelled = await cancelProvisioningJob(job.id);
    await loadData();
    const refreshed = jobsState.value?.jobs.find((item) => item.id === cancelled.id) ?? cancelled;
    selectJob(refreshed);
    noticeMessage.value =
      cancelled.execution_mode === "real"
        ? `Job #${cancelled.id} abandonne. La file active est liberee pour repartir de zero.`
        : `Job #${cancelled.id} abandonne.`;
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    actionKey.value = null;
  }
}

async function submitDeleteJob(job = selectedJob.value) {
  if (!job) {
    errorMessage.value = "Aucun job selectionne.";
    return;
  }
  if (!canManageProvisioningJobs.value) {
    errorMessage.value = "Le role courant ne permet pas de supprimer un job.";
    return;
  }

  const confirmed = window.confirm(
    `Supprimer le job #${job.id} de l'historique ? Cette action retire la trace du cycle du dashboard, mais n'efface pas d'eventuels changements deja appliques sur l'IPC.`,
  );
  if (!confirmed) {
    return;
  }

  actionKey.value = `delete-job-${job.id}`;
  errorMessage.value = null;
  noticeMessage.value = null;
  try {
    const deleted = await deleteProvisioningJob(job.id);
    const deletedJobId = deleted.deleted_job_id;
    await loadData();
    if (selectedJobId.value === deletedJobId) {
      selectedJobId.value = null;
    }
    const replacementJob = visibleJobs.value.find((item) => item.id !== deletedJobId) ?? null;
    if (replacementJob) {
      selectJob(replacementJob);
    }
    noticeMessage.value = `Job #${deleted.deleted_job_id} supprime de l'historique.`;
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    actionKey.value = null;
  }
}

async function submitDeleteAsset() {
  if (!selectedAsset.value) {
    errorMessage.value = "Aucun asset selectionne.";
    return;
  }
  if (!canDeleteSelectedAsset.value) {
    errorMessage.value = "Le role courant ne permet pas cette suppression.";
    return;
  }

  const assetLabel = selectedAsset.value.inventory_hostname ?? selectedAsset.value.hostname ?? `asset-${selectedAsset.value.id}`;
  const confirmed = window.confirm(
    `Supprimer ${assetLabel} de l'inventaire ? Les jobs termines resteront visibles, mais seront detaches de cet asset.`,
  );
  if (!confirmed) {
    return;
  }

  actionKey.value = `delete-${selectedAsset.value.id}`;
  errorMessage.value = null;
  noticeMessage.value = null;
  try {
    const deletedAssetId = selectedAsset.value.id;
    const response = await deleteInventoryAsset(deletedAssetId);
    noticeMessage.value =
      response.detached_job_count > 0
        ? `Asset ${response.deleted_asset_label} supprime. ${response.detached_job_count} job(s) historique(s) ont ete detaches.`
        : `Asset ${response.deleted_asset_label} supprime.`;
    selectedAssetId.value = null;
    await loadData();
    const nextAsset = assets.value.find((item) => item.id !== deletedAssetId) ?? null;
    if (nextAsset) {
      selectAsset(nextAsset);
    }
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    actionKey.value = null;
  }
}

watch(
  () => [selectedJobId.value, selectedJob.value?.status ?? null, actionKey.value] as const,
  ([jobId, jobStatus, currentAction]) => {
    const activeLaunch = typeof currentAction === "string" && currentAction.startsWith("launch-");
    if (jobId && jobStatus === "running" && !activeLaunch) {
      startLiveJobPolling(jobId);
      return;
    }
    stopLiveJobPolling();
  },
  { immediate: true },
);

watch(
  () => [selectedWorkflowKey.value, selectedWorkflow.value?.steps.length ?? 0] as const,
  () => {
    syncManualStepSelection();
  },
  { immediate: true },
);

watch(
  () => [onboardingForm.value.ipcAlloyTenant, onboardingForm.value.ipcAlloyRetentionProfile] as const,
  ([tenant, retentionProfile]) => {
    const contract = resolveIpcAlloyContract(tenant, retentionProfile);
    if (onboardingForm.value.ipcAlloyTenant !== contract.tenant) {
      onboardingForm.value.ipcAlloyTenant = contract.tenant;
    }
    if (onboardingForm.value.ipcAlloyRetentionProfile !== contract.retentionProfile) {
      onboardingForm.value.ipcAlloyRetentionProfile = contract.retentionProfile;
    }
  },
  { immediate: true },
);

onMounted(loadData);
onUnmounted(stopLiveJobPolling);
</script>

<template>
  <section class="stack-card">
    <header class="page-heading">
      <div>
        <p class="muted-2 uppercase">Scan -> onboarding -> provisioning</p>
        <h1>{{ scopedSite ? `Provisioning - ${scopedSite.name}` : "Provisioning center" }}</h1>
        <p class="muted page-copy">
          Le scan capture l'identite reseau de l'IPC, puis l'operateur choisit soit un deroulement complet du
          workflow, soit le lancement cible de certains playbooks selon le besoin terrain.
        </p>
      </div>
      <div class="mode-box">
        <StatusBadge :label="executionMode" :tone="executionMode === 'mock' ? 'warning' : 'healthy'" />
        <p class="muted mono">{{ playbookRoot ?? "playbook root non configure" }}</p>
      </div>
    </header>

    <div class="summary-strip">
      <div class="summary-box">
        <strong>{{ discoveredCount }}</strong>
        <span>candidat(s) a onboarder</span>
      </div>
      <div class="summary-box">
        <strong>{{ registeredCount }}</strong>
        <span>ipc enregistres</span>
      </div>
      <div class="summary-box">
        <strong>{{ visibleJobs.length }}</strong>
        <span>job(s) visibles</span>
      </div>
    </div>

    <p v-if="executionMode === 'mock'" class="banner banner-warning">
      L'execution reste en mode mock. La preparation du contexte est reelle, mais le runner Ansible final reste a
      brancher proprement.
    </p>
    <p v-if="errorMessage" class="banner banner-error">{{ errorMessage }}</p>
    <p v-if="noticeMessage" class="banner banner-success">{{ noticeMessage }}</p>

    <section class="grid-2">
      <article class="surface-card">
        <h2>1. Scanner un nouvel IPC</h2>
        <form class="form-grid" @submit.prevent="submitScan">
          <label class="field">
            <span>Site existant</span>
            <select v-model="scanForm.siteId">
              <option value="">Aucun</option>
              <option v-for="site in sites" :key="site.id" :value="String(site.id)">
                {{ site.name }} ({{ site.code }})
              </option>
            </select>
          </label>
          <label class="field">
            <span>IP cible</span>
            <input v-model="scanForm.targetIp" type="text" placeholder="192.168.10.109" required />
          </label>
          <label class="field">
            <span>IP routeur Teltonika</span>
            <input v-model="scanForm.teltonikaRouterIp" type="text" placeholder="192.168.10.1" />
          </label>
          <label class="field">
            <span>Label operateur</span>
            <input v-model="scanForm.targetLabel" type="text" placeholder="Nouvel IPC" />
          </label>
          <label class="field">
            <span>Utilisateur SSH</span>
            <input v-model="scanForm.sshUsername" type="text" placeholder="cascadya" />
          </label>
          <label class="field">
            <span>Port SSH</span>
            <input v-model="scanForm.sshPort" type="text" placeholder="22" />
          </label>
          <label class="field field-wide">
            <span>IP aval a sonder depuis l'IPC</span>
            <input v-model="scanForm.downstreamProbeIp" type="text" placeholder="192.168.50.1" />
          </label>
          <button class="action-button" type="submit" :disabled="actionKey === 'scan' || loading">
            {{ actionKey === "scan" ? "Scan..." : "Lancer le scan" }}
          </button>
        </form>
      </article>

      <article class="surface-card">
        <h2>2. Enregistrer le candidat selectionne</h2>
        <p v-if="selectedAsset" class="muted">
          MAC {{ selectedAsset.mac_address ?? "---" }} | Mgmt {{ selectedAsset.management_ip ?? "---" }} |
          {{ selectedAsset.vendor ?? "---" }} {{ selectedAsset.model ?? "" }}
        </p>
        <p v-else class="muted">Selectionne un candidat dans la table.</p>
        <div v-if="selectedAsset" class="inline-actions">
          <button
            class="secondary-button danger-button"
            type="button"
            :disabled="!canDeleteSelectedAsset || actionKey === `delete-${selectedAsset.id}`"
            @click="submitDeleteAsset"
          >
            {{ actionKey === `delete-${selectedAsset.id}` ? "Suppression..." : "Supprimer cet asset" }}
          </button>
        </div>

        <form v-if="selectedAsset" class="form-grid" @submit.prevent="submitRegistration">
          <div class="mode-toggle">
            <label><input v-model="onboardingForm.useExistingSite" :value="true" type="radio" /> site existant</label>
            <label :class="{ disabled: !canCreateSite }">
              <input v-model="onboardingForm.useExistingSite" :value="false" type="radio" :disabled="!canCreateSite" />
              nouveau site
            </label>
          </div>

          <label v-if="onboardingForm.useExistingSite" class="field">
            <span>Site</span>
            <select v-model="onboardingForm.siteId">
              <option value="">Selectionner</option>
              <option v-for="site in sites" :key="site.id" :value="String(site.id)">
                {{ site.name }} ({{ site.code }})
              </option>
            </select>
          </label>
          <label v-if="!onboardingForm.useExistingSite" class="field">
            <span>Code site</span>
            <input v-model="onboardingForm.siteCode" type="text" placeholder="SITE-44" />
          </label>
          <label v-if="!onboardingForm.useExistingSite" class="field">
            <span>Nom site</span>
            <input v-model="onboardingForm.siteName" type="text" placeholder="Ouest Consigne" />
          </label>
          <label class="field">
            <span>Hostname</span>
            <input v-model="onboardingForm.hostname" type="text" required />
          </label>
          <label class="field">
            <span>Inventory hostname</span>
            <input v-model="onboardingForm.inventoryHostname" type="text" required />
          </label>
          <label class="field">
            <span>Management IP</span>
            <input v-model="onboardingForm.managementIp" type="text" />
          </label>
          <label class="field">
            <span>Routeur Teltonika</span>
            <input v-model="onboardingForm.teltonikaRouterIp" type="text" />
          </label>
          <label class="field">
            <span>Interface management</span>
            <input v-model="onboardingForm.managementInterface" type="text" />
          </label>
          <label class="field">
            <span>Interface uplink</span>
            <input v-model="onboardingForm.uplinkInterface" type="text" />
          </label>
          <label class="field">
            <span>Gateway</span>
            <input v-model="onboardingForm.gatewayIp" type="text" />
          </label>
          <label class="field">
            <span>WireGuard</span>
            <input v-model="onboardingForm.wireguardAddress" type="text" />
          </label>
          <label class="field">
            <span>WireGuard endpoint (auto si vide)</span>
            <input v-model="onboardingForm.wireguardEndpoint" type="text" placeholder="auto depuis le profil broker du control panel" />
          </label>
          <label class="field">
            <span>WireGuard broker public key (auto si vide)</span>
            <input v-model="onboardingForm.wireguardPeerPublicKey" type="text" placeholder="auto depuis le profil broker du control panel" />
          </label>
          <label class="field">
            <span>WireGuard IPC private key (auto si vide)</span>
            <input v-model="onboardingForm.wireguardPrivateKey" type="text" placeholder="generee automatiquement si absente" />
          </label>
          <label class="field">
            <span>remote_unlock_broker_url (auto si vide)</span>
            <input v-model="onboardingForm.remoteUnlockBrokerUrl" type="text" placeholder="auto depuis le profil broker du control panel" />
          </label>
          <label class="field">
            <span>edge_agent_modbus_host</span>
            <input v-model="onboardingForm.edgeAgentModbusHost" type="text" />
          </label>
          <label class="field">
            <span>edge_agent_nats_url</span>
            <input v-model="onboardingForm.edgeAgentNatsUrl" type="text" />
          </label>
          <label class="field">
            <span>edge_agent_probe_nats_url (optionnel)</span>
            <input
              v-model="onboardingForm.edgeAgentProbeNatsUrl"
              type="text"
              placeholder="URL joignable depuis le control panel pour le test E2E"
            />
          </label>
          <label class="field">
            <span>edge_agent_probe_monitoring_url (optionnel)</span>
            <input
              v-model="onboardingForm.edgeAgentProbeMonitoringUrl"
              type="text"
              placeholder="URL /connz joignable depuis le control panel"
            />
          </label>
          <label class="field">
            <span>ipc_alloy_mimir_remote_write_url (auto si vide)</span>
            <input
              v-model="onboardingForm.ipcAlloyMimirRemoteWriteUrl"
              type="text"
              :placeholder="DEFAULT_IPC_ALLOY_MIMIR_REMOTE_WRITE_URL"
            />
          </label>
          <label class="field">
            <span>ipc_alloy_scrape_interval (auto si vide)</span>
            <input
              v-model="onboardingForm.ipcAlloyScrapeInterval"
              type="text"
              :placeholder="DEFAULT_IPC_ALLOY_SCRAPE_INTERVAL"
            />
          </label>
          <label class="field">
            <span>ipc_alloy_scrape_timeout (auto si vide)</span>
            <input
              v-model="onboardingForm.ipcAlloyScrapeTimeout"
              type="text"
              :placeholder="DEFAULT_IPC_ALLOY_SCRAPE_TIMEOUT"
            />
          </label>
          <label class="field">
            <span>ipc_alloy_mimir_tenant</span>
            <select v-model="onboardingForm.ipcAlloyTenant">
              <option v-for="tenant in IPC_ALLOY_TENANT_OPTIONS" :key="tenant" :value="tenant">
                {{ tenant }}
              </option>
            </select>
            <span class="muted">
              Tenant Mimir cible. Le `retention_profile` est aligne automatiquement sur ce choix.
            </span>
          </label>
          <label class="field">
            <span>ipc_alloy_retention_profile (aligne automatiquement)</span>
            <input v-model="onboardingForm.ipcAlloyRetentionProfile" type="text" readonly />
          </label>
          <label class="field field-wide">
            <span>Notes</span>
            <textarea v-model="onboardingForm.notes" rows="3" />
          </label>
          <button class="action-button" type="submit" :disabled="actionKey === `register-${selectedAsset.id}`">
            {{ actionKey === `register-${selectedAsset.id}` ? "Enregistrement..." : "Enregistrer l'IPC" }}
          </button>
        </form>
      </article>
    </section>

    <section class="surface-card">
      <h2>Assets detectes / connus</h2>
      <div class="table-shell">
        <table class="detail-table">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Mgmt IP</th>
              <th>MAC</th>
              <th>Site</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="asset in visibleAssets"
              :key="asset.id"
              :class="{ selected: asset.id === selectedAssetId }"
              @click="selectAsset(asset)"
            >
              <td>
                <strong>{{ asset.inventory_hostname ?? asset.hostname ?? `asset-${asset.id}` }}</strong>
                <span class="muted">{{ asset.vendor ?? "---" }} {{ asset.model ?? "" }}</span>
              </td>
              <td class="mono">{{ asset.management_ip ?? asset.ip_address ?? "---" }}</td>
              <td class="mono">{{ asset.mac_address ?? "---" }}</td>
              <td>{{ asset.site?.name ?? "Non rattache" }}</td>
              <td><StatusBadge :label="asset.registration_status" :tone="statusTone(asset.registration_status)" compact /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="grid-2">
      <article class="surface-card">
        <h2>3 bis. Synchroniser le modbus simulator</h2>
        <p class="muted page-copy compact-copy">
          Cette utilite ne lance pas un playbook Ansible. Elle prepare les commandes WSL a executer pour pousser le
          sous-arbre <span class="mono">{{ MODBUS_SIMULATOR_REPO_ROOT }}</span> vers le simulateur Modbus raccorde a
          l'IPC, puis redemarrer <span class="mono">{{ modbusSimulatorForm.serviceName }}</span>.
        </p>
        <div class="workflow-card">
          <p class="muted-2 uppercase">Cible recommandee</p>
          <p class="muted">
            <template v-if="selectedAssetLabel">
              IPC selectionne: <span class="mono">{{ selectedAssetLabel }}</span>
            </template>
            <template v-else>
              Aucun IPC selectionne pour suggerer l'hote Modbus.
            </template>
          </p>
          <p class="muted">
            edge_agent_modbus_host suggere:
            <span class="mono">{{ suggestedSimulatorHost }}</span>
          </p>
          <button class="secondary-button" type="button" @click="applySuggestedSimulatorHost">
            Reprendre cette IP dans l'outil
          </button>
        </div>
        <form class="form-grid">
          <label class="field">
            <span>IP simulateur</span>
            <input v-model="modbusSimulatorForm.host" type="text" placeholder="192.168.50.2" />
          </label>
          <label class="field">
            <span>Utilisateur SSH</span>
            <input v-model="modbusSimulatorForm.sshUser" type="text" placeholder="cascadya" />
          </label>
          <label class="field">
            <span>Dossier distant</span>
            <input v-model="modbusSimulatorForm.remoteDir" type="text" placeholder="/home/cascadya/simulator_sbc" />
          </label>
          <label class="field">
            <span>Service systemd</span>
            <input v-model="modbusSimulatorForm.serviceName" type="text" placeholder="modbus-serveur.service" />
          </label>
          <div class="workflow-card field-wide">
            <p class="muted-2 uppercase">Sous-arbre versionne</p>
            <ul class="preview-list">
              <li><span class="mono">src/</span> runtime Python du simulateur</li>
              <li><span class="mono">systemd/</span> unite de service du simulateur</li>
              <li><span class="mono">scripts/</span> helper de sync WSL -> simulateur</li>
            </ul>
            <p class="muted mono">script helper: {{ MODBUS_SIMULATOR_SYNC_SCRIPT }}</p>
          </div>
        </form>
      </article>

      <article class="surface-card">
        <h2>Commandes WSL</h2>
        <p class="banner banner-warning">
          Ces commandes sont a lancer depuis ton WSL ou un shell ayant acces au repo <span class="mono">control_plane</span>.
          Le navigateur affiche juste la recette operateur.
        </p>
        <div class="command-stack">
          <details class="surface-card command-card" open>
            <summary>Sync helper recommande</summary>
            <pre class="console"><code>{{ modbusSimulatorSyncCommand }}</code></pre>
          </details>
          <details class="surface-card command-card">
            <summary>Fallback manuel rsync + scp + systemd</summary>
            <pre class="console"><code>{{ modbusSimulatorManualCommand }}</code></pre>
          </details>
          <details class="surface-card command-card">
            <summary>Verification distante</summary>
            <pre class="console"><code>{{ modbusSimulatorVerifyCommand }}</code></pre>
          </details>
        </div>
      </article>
    </section>

    <section class="grid-2">
      <article class="surface-card">
        <h2>4. Executer le provisioning</h2>
        <form class="form-grid" @submit.prevent="submitLaunchProvisioning">
          <div class="mode-toggle mode-toggle-provisioning field-wide">
            <button
              class="mode-chip"
              :class="{ selected: !isManualDispatchMode }"
              type="button"
              @click="provisioningForm.dispatchMode = 'auto'"
            >
              Mode auto
            </button>
            <button
              class="mode-chip"
              :class="{ selected: isManualDispatchMode }"
              type="button"
              @click="provisioningForm.dispatchMode = 'manual'"
            >
              Mode manuel
            </button>
          </div>
          <label class="field">
            <span>Workflow</span>
            <select v-model="provisioningForm.workflowKey">
              <option v-for="workflow in workflowCatalog" :key="workflow.key" :value="workflow.key">
                {{ workflow.label }} - {{ workflow.key }}
              </option>
            </select>
          </label>
          <label class="field">
            <span>Groupe inventory</span>
            <input v-model="provisioningForm.inventoryGroup" type="text" placeholder="cascadya_ipc" />
          </label>
          <label v-if="isManualDispatchMode" class="field">
            <span>Playbook cible</span>
            <select v-model="provisioningForm.manualStepKey">
              <option v-for="step in selectedWorkflow?.steps ?? []" :key="step.key" :value="step.key">
                {{ step.order ?? "?" }}. {{ step.label }} - {{ step.playbook_name }}
              </option>
            </select>
          </label>
          <div v-if="selectedWorkflow" class="workflow-card field-wide">
            <p class="muted-2 uppercase">{{ isManualDispatchMode ? "Workflow de reference" : "Workflow complet" }}</p>
            <h3>{{ selectedWorkflow.label }}</h3>
            <p class="muted">{{ selectedWorkflow.description }}</p>
            <p v-if="isManualDispatchMode && selectedManualStepDefinition" class="muted">
              Le mode manuel prepare le meme bundle d'artefacts, puis n'execute que le playbook cible :
              <span class="mono">{{ selectedManualStepDefinition.playbook_name }}</span>.
            </p>
            <p class="muted mono">
              playbook root: {{ playbookRoot ?? "non configure, preview uniquement" }}
            </p>
            <ol class="workflow-list">
              <li v-for="step in selectedWorkflow.steps" :key="step.key" class="workflow-step">
                <strong>{{ step.label }}</strong>
                <span class="muted mono">{{ step.playbook_name }}</span>
                <span class="muted">
                  {{ workflowPhaseLabel(step.phase) }} - {{ workflowScopeLabel(step.scope) }}
                </span>
              </li>
            </ol>
            <p v-for="note in selectedWorkflow.notes" :key="note" class="muted workflow-note">
              {{ note }}
            </p>
          </div>
          <div v-if="isManualDispatchMode && selectedManualStepDefinition" class="workflow-card field-wide">
            <p class="muted-2 uppercase">Step manuel selectionne</p>
            <h3>{{ selectedManualStepDefinition.label }}</h3>
            <p class="muted mono">{{ selectedManualStepDefinition.playbook_name }}</p>
            <p class="muted">
              {{ workflowPhaseLabel(selectedManualStepDefinition.phase) }} -
              {{ workflowScopeLabel(selectedManualStepDefinition.scope) }}
            </p>
          </div>
          <label v-if="selectedOperationRequiresVaultSeed" class="field field-wide">
            <span>Secret LUKS pour Vault</span>
            <input
              v-model="provisioningForm.remoteUnlockVaultSecretValue"
              type="password"
              autocomplete="new-password"
              placeholder="passphrase /data a publier pour cet IPC"
            />
            <span class="muted">
              Le workflow seed automatiquement le secret s'il est absent. Si le secret existe deja,
              il est reutilise tel quel si la valeur correspond deja. En cas de valeur differente,
              le job s'arretera sauf si tu confirmes explicitement l'ecrasement.
            </span>
          </label>
          <label v-if="selectedOperationRequiresVaultSeed" class="field field-wide">
            <span>Confirmation d'ecrasement</span>
            <span class="field-checkbox">
              <input v-model="provisioningForm.remoteUnlockVaultSecretConfirmOverwrite" type="checkbox" />
              <span>J'autorise l'ecrasement du secret Vault existant pour cet IPC.</span>
            </span>
          </label>
          <p v-if="selectedAsset?.registration_status === 'discovered'" class="banner banner-warning field-wide">
            Cet asset est encore au statut `discovered`. Termine d'abord l'enregistrement de l'IPC avant de lancer le provisioning.
          </p>
          <div v-if="selectedAssetLaunchJob" class="field-wide stack-inline">
            <p class="banner banner-warning">
              <template v-if="isManualDispatchMode">
                Cet IPC a deja un job manuel ouvert (#{{ selectedAssetLaunchJob.id }}). Un nouveau clic reutilisera ce job pour lancer uniquement le playbook selectionne.
              </template>
              <template v-else-if="executionMode === 'mock'">
                Cet IPC a deja un job non termine (#{{ selectedAssetLaunchJob.id }}). Un nouveau clic relancera un cycle complet et supersedera automatiquement cet ancien job.
              </template>
              <template v-else>
                Un job de provisioning reel est deja en cours pour cet IPC (#{{ selectedAssetLaunchJob.id }}). Un nouveau clic reprendra la chaine a partir de la prochaine etape disponible. Abandonne-le seulement si tu veux repartir proprement de zero.
              </template>
            </p>
            <div v-if="canManageProvisioningJobs" class="inline-actions inline-actions-start">
              <button
                class="secondary-button"
                type="button"
                :disabled="actionKey === `cancel-job-${selectedAssetLaunchJob.id}`"
                @click="submitCancelJob(selectedAssetLaunchJob)"
              >
                {{ actionKey === `cancel-job-${selectedAssetLaunchJob.id}` ? "Abandon..." : `Abandonner le job #${selectedAssetLaunchJob.id}` }}
              </button>
              <button
                v-if="selectedAssetLaunchJob.status !== 'running'"
                class="secondary-button danger-button"
                type="button"
                :disabled="actionKey === `delete-job-${selectedAssetLaunchJob.id}`"
                @click="submitDeleteJob(selectedAssetLaunchJob)"
              >
                {{ actionKey === `delete-job-${selectedAssetLaunchJob.id}` ? "Suppression..." : `Supprimer le job #${selectedAssetLaunchJob.id}` }}
              </button>
            </div>
          </div>
          <p v-if="!canLaunchProvisioning" class="banner banner-warning field-wide">
            Le role courant doit avoir `provision:prepare` et `provision:run` pour lancer le provisioning.
          </p>
          <button
            class="action-button"
            type="submit"
            :disabled="launchButtonDisabled"
          >
            {{ launchButtonLabel }}
          </button>
        </form>
      </article>

      <article class="surface-card">
        <h2>5. Etat d'avancement</h2>
        <div v-if="selectedJob" class="job-actions">
          <p class="mono">job #{{ selectedJob.id }} - {{ selectedJobWorkflow?.label ?? selectedJob.playbook_name }}</p>
          <StatusBadge :label="selectedJob.status" :tone="statusTone(selectedJob.status)" />
          <p class="muted">
            {{ selectedJobProgress?.completed_steps ?? 0 }}/{{ selectedJobProgress?.total_steps ?? selectedJobSteps.length }} etapes validees
          </p>
          <div v-if="canManageProvisioningJobs" class="inline-actions inline-actions-start job-toolbar">
            <button
              v-if="selectedJobCanBeCancelled"
              class="secondary-button"
              type="button"
              :disabled="actionKey === `cancel-job-${selectedJob.id}`"
              @click="submitCancelJob(selectedJob)"
            >
              {{ actionKey === `cancel-job-${selectedJob.id}` ? "Abandon..." : "Abandonner ce job" }}
            </button>
            <button
              v-if="selectedJobCanBeDeleted"
              class="secondary-button danger-button"
              type="button"
              :disabled="actionKey === `delete-job-${selectedJob.id}`"
              @click="submitDeleteJob(selectedJob)"
            >
              {{ actionKey === `delete-job-${selectedJob.id}` ? "Suppression..." : "Supprimer de l'historique" }}
            </button>
          </div>
          <p v-if="nextRunnableStep" class="muted">
            Prochaine etape: {{ nextRunnableStep.order ?? "?" }} - {{ nextRunnableStep.label }}
          </p>
          <p v-else-if="selectedJob.status === 'succeeded'" class="muted">
            Workflow termine. L'IPC est passe a l'etat final cible pour ce prototype.
          </p>
          <p v-else-if="selectedJob.status === 'cancelled'" class="muted">
            Workflow abandonne. Tu peux repartir de zero ou supprimer ce job de l'historique.
          </p>
          <p v-else-if="selectedJob.status === 'superseded'" class="muted">
            Workflow remplace par un cycle plus recent.
          </p>
          <p v-else class="muted">
            Aucune etape executable n'est actuellement disponible.
          </p>
        </div>
        <p v-else class="muted">Aucun job lance pour l'instant.</p>
      </article>
    </section>

    <section class="surface-card">
      <h2>Jobs</h2>
      <div class="table-shell">
        <table class="detail-table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Site</th>
              <th>Mode</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="job in visibleJobs"
              :key="job.id"
              :class="{ selected: job.id === selectedJobId }"
              @click="selectJob(job)"
            >
              <td><strong>#{{ job.id }}</strong> <span class="muted mono">{{ job.playbook_name }}</span></td>
              <td>{{ job.site?.name ?? "Sans site" }}</td>
              <td>{{ job.execution_mode }} / {{ job.dispatch_mode }}</td>
              <td><StatusBadge :label="job.status" :tone="statusTone(job.status)" compact /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="selectedJob" class="job-detail">
        <div v-if="selectedJobWorkflow" class="surface-card">
          <p class="muted-2 uppercase">Workflow du job</p>
          <h3>{{ selectedJobWorkflow.label }}</h3>
          <p class="muted">{{ selectedJobWorkflow.description }}</p>
          <p class="muted mono">
            ready_for_real_execution={{ selectedJobReady ? "true" : "false" }} -
            {{ selectedJobProgress?.completed_steps ?? 0 }}/{{ selectedJobProgress?.total_steps ?? selectedJobSteps.length }} etapes validees
          </p>
          <ol class="workflow-list">
            <li
              v-for="step in selectedJobWorkflow.steps"
              :key="step.key"
              class="workflow-step job-step"
              :class="`job-step-${workflowStepStatus(step)}`"
            >
              <div class="job-step-header">
                <strong>{{ step.order ?? "?" }}. {{ step.label }}</strong>
                <div class="job-step-status-block">
                  <div class="job-step-status-line">
                    <span v-if="step.status === 'succeeded'" class="step-check" aria-hidden="true">&#10003;</span>
                    <span class="step-status">{{ workflowStepStatusLabel(step) }}</span>
                  </div>
                  <span v-if="workflowStepDurationLabel(step)" class="step-duration muted mono">
                    {{ workflowStepDurationLabel(step) }}
                  </span>
                </div>
              </div>
              <span class="muted mono">{{ step.playbook_name }}</span>
              <span class="muted mono">{{ step.playbook_path ?? step.command ?? "---" }}</span>
              <span v-if="workflowStepTimestampMeta(step)" class="muted mono">
                {{ workflowStepTimestampMeta(step)?.label }}: {{ workflowStepTimestampMeta(step)?.value }}
              </span>
              <span v-if="step.error_message" class="step-error">{{ step.error_message }}</span>
            </li>
          </ol>
        </div>
        <pre class="console"><code>{{ selectedJob.command_preview }}</code></pre>
        <pre class="console"><code>{{ selectedJob.logs.join("\n") }}</code></pre>
      </div>
      <div v-if="selectedJobArtifacts" class="artifact-grid">
        <details v-if="selectedJobArtifacts.wazuh_agent" class="surface-card">
          <summary>Inventory Wazuh agent</summary>
          <p class="muted mono">{{ selectedJobArtifacts.wazuh_agent.inventory_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.wazuh_agent.inventory_preview }}</code></pre>
        </details>
        <details v-if="selectedJobArtifacts.wazuh_agent" class="surface-card">
          <summary>Variables Wazuh agent</summary>
          <p class="muted mono">{{ selectedJobArtifacts.wazuh_agent.vars_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.wazuh_agent.vars_preview }}</code></pre>
        </details>
        <details v-if="selectedJobArtifacts.ipc_alloy" class="surface-card">
          <summary>Inventory IPC Alloy</summary>
          <p class="muted mono">{{ selectedJobArtifacts.ipc_alloy.inventory_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.ipc_alloy.inventory_preview }}</code></pre>
        </details>
        <details v-if="selectedJobArtifacts.ipc_alloy" class="surface-card">
          <summary>Variables IPC Alloy</summary>
          <p class="muted mono">{{ selectedJobArtifacts.ipc_alloy.vars_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.ipc_alloy.vars_preview }}</code></pre>
        </details>
        <details v-if="selectedJobArtifacts.edge_agent" class="surface-card">
          <summary>Inventory edge-agent</summary>
          <p class="muted mono">{{ selectedJobArtifacts.edge_agent.inventory_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.edge_agent.inventory_preview }}</code></pre>
        </details>
        <details v-if="selectedJobArtifacts.edge_agent" class="surface-card">
          <summary>Variables edge-agent</summary>
          <p class="muted mono">{{ selectedJobArtifacts.edge_agent.vars_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.edge_agent.vars_preview }}</code></pre>
        </details>
        <details v-if="selectedJobArtifacts.remote_unlock" class="surface-card">
          <summary>Inventory remote-unlock</summary>
          <p class="muted mono">{{ selectedJobArtifacts.remote_unlock.inventory_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.remote_unlock.inventory_preview }}</code></pre>
        </details>
        <details v-if="selectedJobArtifacts.remote_unlock" class="surface-card">
          <summary>Variables remote-unlock</summary>
          <p class="muted mono">{{ selectedJobArtifacts.remote_unlock.vars_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.remote_unlock.vars_preview }}</code></pre>
        </details>
        <details v-if="selectedJobArtifacts.remote_unlock_broker" class="surface-card">
          <summary>Inventory broker remote-unlock</summary>
          <p class="muted mono">{{ selectedJobArtifacts.remote_unlock_broker.inventory_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.remote_unlock_broker.inventory_preview }}</code></pre>
        </details>
        <details v-if="selectedJobArtifacts.remote_unlock_broker" class="surface-card">
          <summary>Variables broker remote-unlock</summary>
          <p class="muted mono">{{ selectedJobArtifacts.remote_unlock_broker.vars_path }}</p>
          <pre class="console"><code>{{ selectedJobArtifacts.remote_unlock_broker.vars_preview }}</code></pre>
        </details>
      </div>
    </section>
  </section>
</template>

<style scoped>
.uppercase { text-transform: uppercase; letter-spacing: 0.12em; font-size: 0.76rem; }
.page-copy { margin-top: 0.7rem; max-width: 60rem; }
.compact-copy { max-width: none; }
.summary-strip, .grid-2, .job-detail, .artifact-grid { display: grid; gap: 1rem; }
.command-stack { display: grid; gap: 0.9rem; }
.inline-actions { display: flex; justify-content: flex-end; margin: 0.75rem 0 1rem; }
.inline-actions-start { justify-content: flex-start; }
.stack-inline { display: grid; gap: 0.75rem; }
.job-toolbar { margin: 0; }
.summary-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-2, .job-detail { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.artifact-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 1rem; }
.summary-box, .surface-card, .mode-box {
  padding: 1rem 1.2rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(13, 16, 21, 0.96), rgba(9, 11, 15, 0.94));
}
.summary-box strong { display: block; font-size: 1.5rem; }
.banner { padding: 0.95rem 1.15rem; border-radius: 1rem; }
.banner-warning { background: rgba(93, 78, 28, 0.38); color: var(--amber); }
.banner-error { background: rgba(136, 46, 46, 0.36); color: #ffb4a7; }
.banner-success { background: rgba(44, 94, 72, 0.34); color: #a7ebc9; }
.danger-button { border-color: rgba(214, 94, 94, 0.45); color: #ffb4a7; }
.danger-button:hover { border-color: rgba(214, 94, 94, 0.75); background: rgba(214, 94, 94, 0.12); }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.85rem; }
.field { display: grid; gap: 0.4rem; }
.field span { color: var(--muted); font-size: 0.92rem; }
.field input, .field select, .field textarea {
  width: 100%; min-height: 2.8rem; padding: 0.78rem 0.92rem; border-radius: 0.95rem;
  border: 1px solid var(--line); background: rgba(255, 255, 255, 0.04); color: var(--text); font: inherit;
}
.field select {
  background: #050608;
  color: #f5f7fb;
}
.field select option {
  background: #050608;
  color: #f5f7fb;
}
.field-wide { grid-column: 1 / -1; }
.field-checkbox { display: inline-flex; align-items: flex-start; gap: 0.65rem; }
.field-checkbox input { width: auto; min-height: 1rem; margin-top: 0.2rem; padding: 0; }
.mode-toggle { grid-column: 1 / -1; display: flex; gap: 1rem; color: var(--muted); }
.mode-toggle label { display: inline-flex; align-items: center; gap: 0.5rem; }
.mode-toggle label.disabled { opacity: 0.55; }
.mode-toggle-provisioning { align-items: center; }
.mode-chip {
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
  color: var(--muted);
  border-radius: 999px;
  padding: 0.72rem 1rem;
  cursor: pointer;
  font: inherit;
}
.mode-chip.selected {
  color: var(--text);
  border-color: rgba(103, 176, 255, 0.55);
  background: rgba(103, 176, 255, 0.14);
}
.workflow-card { border: 1px solid var(--line); border-radius: 1rem; padding: 1rem; background: rgba(255, 255, 255, 0.03); }
.workflow-list { margin: 0.9rem 0 0; padding-left: 1.2rem; display: grid; gap: 0.65rem; }
.workflow-step { display: grid; gap: 0.15rem; }
.workflow-note { margin-top: 0.7rem; }
.preview-list { margin: 0.75rem 0 0; padding-left: 1.2rem; display: grid; gap: 0.35rem; color: var(--muted); }
.command-card { padding: 0; overflow: hidden; }
.command-card summary { cursor: pointer; padding: 1rem 1.2rem; font-weight: 600; }
.command-card .console { border-radius: 0; border-left: none; border-right: none; border-bottom: none; }
.job-step { border: 1px solid var(--line); border-radius: 0.9rem; padding: 0.8rem 0.9rem; background: rgba(255, 255, 255, 0.02); list-style: none; margin-left: -1.2rem; }
.job-step-header { display: flex; align-items: center; gap: 0.6rem; justify-content: space-between; flex-wrap: wrap; }
.job-step-status-block { display: grid; justify-items: end; gap: 0.1rem; }
.job-step-status-line { display: inline-flex; align-items: center; gap: 0.45rem; }
.job-step-ready { border-color: rgba(255, 191, 102, 0.45); background: rgba(255, 191, 102, 0.08); }
.job-step-running { border-color: rgba(103, 176, 255, 0.45); background: rgba(103, 176, 255, 0.08); }
.job-step-succeeded { border-color: rgba(71, 171, 118, 0.5); background: rgba(71, 171, 118, 0.12); }
.job-step-locked { opacity: 0.6; }
.job-step-failed { border-color: rgba(214, 94, 94, 0.5); background: rgba(214, 94, 94, 0.1); }
.step-check { display: inline-flex; align-items: center; justify-content: center; width: 1.4rem; height: 1.4rem; border-radius: 999px; background: rgba(71, 171, 118, 0.18); color: #8ee0a8; border: 1px solid rgba(71, 171, 118, 0.5); font-weight: 700; }
.step-status { font-size: 0.84rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }
.step-duration { font-size: 0.8rem; }
.step-error { color: #ffb4a7; }
.table-shell { overflow: hidden; border-radius: var(--radius-xl); border: 1px solid var(--line); }
.detail-table thead th { padding: 1rem 1.15rem; color: var(--muted); border-bottom: 1px solid var(--line); }
.detail-table tbody tr { cursor: pointer; }
.detail-table tbody tr.selected { background: rgba(82, 117, 176, 0.18); }
.detail-table tbody td { padding: 1rem 1.15rem; border-bottom: 1px solid var(--line); vertical-align: top; }
.detail-table tbody tr:last-child td { border-bottom: none; }
.job-actions { display: grid; gap: 0.75rem; }
.console {
  margin: 0; min-height: 12rem; max-height: 24rem; overflow: auto; padding: 1rem;
  border-radius: 1rem; border: 1px solid var(--line); background: rgba(6, 7, 8, 0.92);
  color: var(--muted); font-family: var(--font-mono); white-space: pre-wrap;
}
.artifact-grid details summary { cursor: pointer; color: var(--text); font-weight: 600; }
@media (max-width: 960px) {
  .summary-strip, .grid-2, .job-detail, .artifact-grid, .form-grid { grid-template-columns: 1fr; }
  .table-shell { overflow-x: auto; }
  .detail-table { min-width: 820px; }
}
</style>
