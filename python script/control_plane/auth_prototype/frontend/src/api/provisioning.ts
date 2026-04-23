import { apiClient } from "@/api/client";
import type {
  ApiE2ETestPayload,
  ApiInventoryAssetPayload,
  ApiInventoryScanPayload,
  ApiProvisioningJobPayload,
  ApiProvisioningWorkflowPayload,
  ApiSitePayload,
} from "@/types/controlPlane";

export interface SitesResponse {
  sites: ApiSitePayload[];
}

export interface InventoryAssetsResponse {
  assets: ApiInventoryAssetPayload[];
}

export interface InventoryScansResponse {
  scans: ApiInventoryScanPayload[];
}

export interface InventoryScanRequestPayload {
  site_id?: number | null;
  target_ip: string;
  teltonika_router_ip?: string;
  target_label?: string;
  ssh_username?: string;
  ssh_port?: number;
  downstream_probe_ip?: string;
  asset_type?: string;
}

export interface InventoryScanCreateResponse {
  scan: ApiInventoryScanPayload;
  asset: ApiInventoryAssetPayload;
}

export interface AssetRegistrationPayload {
  site_id?: number | null;
  site_code?: string;
  site_name?: string;
  customer_name?: string;
  country?: string;
  city?: string;
  timezone?: string;
  address_line1?: string;
  site_notes?: string;
  hostname: string;
  inventory_hostname: string;
  naming_slug?: string;
  management_ip?: string;
  teltonika_router_ip?: string;
  management_interface?: string;
  uplink_interface?: string;
  gateway_ip?: string;
  wireguard_address?: string;
  notes?: string;
  provisioning_vars: Record<string, string>;
}

export interface ProvisioningJobsResponse {
  execution_mode: string;
  playbook_root: string | null;
  default_workflow_key: string | null;
  workflow_catalog: ApiProvisioningWorkflowPayload[];
  jobs: ApiProvisioningJobPayload[];
}

export interface ProvisioningJobCreatePayload {
  asset_id: number;
  workflow_key?: string;
  playbook_name?: string;
  dispatch_mode?: "auto" | "manual";
  inventory_group?: string;
  remote_unlock_vault_secret_value?: string;
  remote_unlock_vault_secret_confirm_overwrite?: boolean;
}

export interface ProvisioningJobRunPayload {
  step_key?: string;
}

export interface DeleteInventoryAssetResponse {
  status: string;
  deleted_asset_id: number;
  deleted_asset_label: string;
  deleted_registration_status: string;
  site_id: number | null;
  discovered_by_scan_id: number | null;
  detached_job_count: number;
  detached_job_ids: number[];
}

export interface DeleteProvisioningJobResponse {
  status: string;
  deleted_job_id: number;
  deleted_job_label: string;
  deleted_job_status: string;
  site_id: number | null;
  asset_id: number | null;
}

export interface E2ETestRequestPayload {
  asset_id?: number | null;
  site_id?: number | null;
  flow_key?: "ems_site" | "ems_light";
  sample_count?: number;
  sample_interval_seconds?: number;
}

function buildQuery(params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      return;
    }
    query.set(key, String(value));
  });
  const queryString = query.toString();
  return queryString ? `?${queryString}` : "";
}

export function fetchSites() {
  return apiClient<SitesResponse>("/api/sites");
}

export function fetchSite(siteId: number) {
  return apiClient<ApiSitePayload>(`/api/sites/${siteId}`);
}

export function fetchInventoryAssets(params?: { siteId?: number | null; registrationStatus?: string | null }) {
  const query = buildQuery({
    site_id: params?.siteId,
    registration_status: params?.registrationStatus,
  });
  return apiClient<InventoryAssetsResponse>(`/api/inventory/assets${query}`);
}

export function fetchInventoryScans(params?: { siteId?: number | null }) {
  const query = buildQuery({
    site_id: params?.siteId,
  });
  return apiClient<InventoryScansResponse>(`/api/inventory/scans${query}`);
}

export function requestInventoryScan(payload: InventoryScanRequestPayload) {
  return apiClient<InventoryScanCreateResponse>("/api/inventory/scans", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function registerInventoryAsset(assetId: number, payload: AssetRegistrationPayload) {
  return apiClient<ApiInventoryAssetPayload>(`/api/inventory/assets/${assetId}/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function deleteInventoryAsset(assetId: number) {
  return apiClient<DeleteInventoryAssetResponse>(`/api/inventory/assets/${assetId}`, {
    method: "DELETE",
  });
}

export function fetchProvisioningJobs(params?: { siteId?: number | null }) {
  const query = buildQuery({
    site_id: params?.siteId,
  });
  return apiClient<ProvisioningJobsResponse>(`/api/provisioning/jobs${query}`);
}

export function fetchProvisioningJob(jobId: number) {
  return apiClient<ApiProvisioningJobPayload>(`/api/provisioning/jobs/${jobId}`);
}

export function prepareProvisioningJob(payload: ProvisioningJobCreatePayload) {
  return apiClient<ApiProvisioningJobPayload>("/api/provisioning/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function runProvisioningJob(jobId: number, payload?: ProvisioningJobRunPayload) {
  return apiClient<ApiProvisioningJobPayload>(`/api/provisioning/jobs/${jobId}/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload ?? {}),
  });
}

export function cancelProvisioningJob(jobId: number) {
  return apiClient<ApiProvisioningJobPayload>(`/api/provisioning/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export function deleteProvisioningJob(jobId: number) {
  return apiClient<DeleteProvisioningJobResponse>(`/api/provisioning/jobs/${jobId}`, {
    method: "DELETE",
  });
}

export function runE2ETest(payload: E2ETestRequestPayload) {
  return apiClient<ApiE2ETestPayload>("/api/e2e/tests", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}
