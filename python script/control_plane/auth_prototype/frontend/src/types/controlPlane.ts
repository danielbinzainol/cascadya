export type Permission =
  | "audit:read"
  | "dashboard:read"
  | "inventory:read"
  | "inventory:scan"
  | "provision:prepare"
  | "provision:run"
  | "provision:cancel"
  | "site:read"
  | "site:write"
  | "user:read"
  | "user:write"
  | "role:assign";

export type RoleName = "viewer" | "operator" | "provisioning_manager" | "admin";

export type DemoProfileKey = "admin" | "provisioning_manager" | "operator" | "viewer";

export type BadgeTone =
  | "neutral"
  | "healthy"
  | "active"
  | "degraded"
  | "warning"
  | "critical"
  | "provisioning"
  | "waiting"
  | "running"
  | "pending"
  | "done"
  | "pass"
  | "slow"
  | "viewer"
  | "operator"
  | "provisioning_manager"
  | "admin";

export interface SessionUser {
  id: number;
  keycloakUuid: string | null;
  username: string;
  displayName: string;
  email: string;
  roles: RoleName[];
  permissions: Permission[];
  isActive: boolean;
  authSource: "oidc" | "legacy";
}

export interface ApiSessionUserPayload {
  id: number;
  keycloak_uuid: string | null;
  username: string;
  email: string;
  display_name: string;
  roles: RoleName[];
  permissions: Permission[];
  is_active: boolean;
  auth_source: "oidc" | "legacy";
}

export interface UiConfig {
  dashboards: {
    wazuhUrl: string | null;
  };
}

export interface ApiUiConfigPayload {
  dashboards: {
    wazuh: {
      url: string | null;
    };
  };
}

export interface ApiAlertsSourcePayload {
  kind: string;
  configured: boolean;
  healthy: boolean;
  message: string;
}

export interface ApiLiveAlertPayload {
  id: string;
  title: string;
  summary: string;
  source: "Wazuh";
  severity: "critical" | "warning" | "degraded" | "info";
  priority: 1 | 2 | 3 | 4;
  state: "new";
  raised_at: string;
  company: string;
  site_label: string;
  region: string;
  owner_hint: string;
  next_step: string;
  tags: string[];
}

export interface ApiLiveAlertsPayload {
  source: ApiAlertsSourcePayload;
  alerts: ApiLiveAlertPayload[];
  generated_at: string;
}

export interface DashboardMetric {
  title: string;
  value: string;
  subtitle: string;
  tone: BadgeTone;
}

export interface ApiAdminUserPayload {
  id: number;
  keycloak_uuid: string | null;
  username: string;
  email: string;
  display_name: string;
  roles: RoleName[];
  permissions: Permission[];
  is_active: boolean;
  last_login_at: string | null;
  auth_source: "oidc" | "legacy";
}

export interface AdminUserRecord {
  id: number;
  keycloakUuid: string | null;
  username: string;
  email: string;
  displayName: string;
  firstName: string;
  lastName: string;
  roles: RoleName[];
  permissions: Permission[];
  isActive: boolean;
  lastLoginAt: string | null;
  lastLoginLabel: string;
  authSource: "oidc" | "legacy";
}

export interface RbacPermissionCatalogEntry {
  name: Permission;
  description: string;
}

export interface RbacRoleCatalogEntry {
  name: RoleName;
  description: string;
  permissions: Permission[];
}

export interface RbacCatalogPayload {
  permissions: RbacPermissionCatalogEntry[];
  roles: RbacRoleCatalogEntry[];
}

export interface SiteReferencePayload {
  id: number;
  code: string;
  name: string;
}

export interface JobReferencePayload {
  id: number;
  status: string;
  playbook_name: string;
  created_at: string;
  finished_at: string | null;
}

export interface ScanReferencePayload {
  id: number;
  status: string;
  target_ip: string;
  created_at: string;
  finished_at: string | null;
}

export interface ApiSitePayload {
  id: number;
  code: string;
  name: string;
  customer_name: string;
  country: string;
  city: string;
  timezone: string;
  address_line1: string;
  notes: string;
  is_active: boolean;
  status: string;
  asset_count: number;
  active_asset_count: number;
  last_scan: ScanReferencePayload | null;
  last_job: JobReferencePayload | null;
  created_at: string;
  updated_at: string;
}

export interface ApiInventoryAssetPayload {
  id: number;
  site: SiteReferencePayload | null;
  discovered_by_scan_id: number | null;
  asset_type: string;
  registration_status: string;
  hostname: string | null;
  inventory_hostname: string | null;
  naming_slug: string | null;
  ip_address: string | null;
  management_ip: string | null;
  teltonika_router_ip: string | null;
  mac_address: string | null;
  serial_number: string | null;
  vendor: string | null;
  model: string | null;
  firmware_version: string | null;
  status: string;
  source: string;
  management_interface: string | null;
  uplink_interface: string | null;
  gateway_ip: string | null;
  wireguard_address: string | null;
  notes: string;
  provisioning_vars: Record<string, string>;
  first_seen_at: string | null;
  last_seen_at: string | null;
  latest_job: JobReferencePayload | null;
  created_at: string;
  updated_at: string;
}

export interface ScanAssetReferencePayload {
  id: number;
  hostname: string | null;
  inventory_hostname: string | null;
  management_ip: string | null;
  mac_address: string | null;
  registration_status: string;
}

export interface ApiInventoryScanPayload {
  id: number;
  site: SiteReferencePayload | null;
  requested_by_user_id: number | null;
  status: string;
  trigger_type: string;
  source: string;
  target_label: string;
  target_ip: string;
  teltonika_router_ip: string | null;
  started_at: string | null;
  finished_at: string | null;
  summary: Record<string, unknown>;
  error_message: string | null;
  discovered_assets: ScanAssetReferencePayload[];
  created_at: string;
  updated_at: string;
}

export interface ApiProvisioningWorkflowStepPayload {
  key: string;
  label: string;
  playbook_name: string;
  inventory_kind: string;
  scope: string;
  phase: string;
  order?: number;
  status?: "locked" | "ready" | "running" | "succeeded" | "failed";
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  playbook_path?: string;
  playbook_exists?: boolean;
  inventory_path?: string;
  vars_path?: string;
  command?: string;
}

export interface ApiProvisioningWorkflowPayload {
  key: string;
  label: string;
  description: string;
  notes: string[];
  steps: ApiProvisioningWorkflowStepPayload[];
}

export interface ApiProvisioningArtifactBundlePayload {
  inventory_path: string;
  vars_path: string;
  inventory_preview: string;
  vars_preview: string;
}

export interface ApiProvisioningArtifactsPayload {
  edge_agent?: ApiProvisioningArtifactBundlePayload;
  ipc_alloy?: ApiProvisioningArtifactBundlePayload;
  wazuh_agent?: ApiProvisioningArtifactBundlePayload;
  remote_unlock_broker?: ApiProvisioningArtifactBundlePayload;
  remote_unlock?: ApiProvisioningArtifactBundlePayload;
}

export interface ApiProvisioningProgressPayload {
  completed_steps: number;
  total_steps: number;
  next_step_key: string | null;
  next_step_label: string | null;
}

export interface ApiProvisioningJobContextPayload {
  site?: SiteReferencePayload | null;
  asset?: ApiInventoryAssetPayload;
  workflow?: ApiProvisioningWorkflowPayload;
  artifacts?: ApiProvisioningArtifactsPayload;
  progress?: ApiProvisioningProgressPayload;
  playbook_root?: string | null;
  ready_for_real_execution?: boolean;
  runner?: {
    dispatch_mode?: "auto" | "manual";
    ansible_config_path?: string | null;
    readiness_reasons?: string[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ApiProvisioningJobPayload {
  id: number;
  site: SiteReferencePayload | null;
  asset_id: number | null;
  requested_by_user_id: number | null;
  status: string;
  execution_mode: string;
  dispatch_mode: "auto" | "manual";
  playbook_name: string;
  inventory_group: string;
  command_preview: string;
  context: ApiProvisioningJobContextPayload;
  logs: string[];
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiE2EHopPayload {
  key: string;
  label: string;
  latency_ms: number | null;
  source: string;
}

export interface ApiE2EConnectionPayload {
  cid: number | null;
  name: string | null;
  ip: string | null;
  lang: string | null;
  version: string | null;
  subscriptions: number | null;
  in_msgs: number | null;
  out_msgs: number | null;
  in_bytes: number | null;
  out_bytes: number | null;
  pending_bytes: number | null;
  uptime: string | null;
  idle: string | null;
  rtt: string | null;
  rtt_ms: number | null;
}

export interface ApiE2EMonitoringVarzPayload {
  server_id: string | null;
  server_name: string | null;
  version: string | null;
  host: string | null;
  port: number | null;
  connections: number | null;
  total_connections: number | null;
  routes: number | null;
  slow_consumers: number | null;
  in_msgs: number | null;
  out_msgs: number | null;
  in_bytes: number | null;
  out_bytes: number | null;
}

export interface ApiE2EMonitoringPayload {
  url: string | null;
  available: boolean;
  warnings: string[];
  healthz: Record<string, unknown> | null;
  varz: ApiE2EMonitoringVarzPayload | null;
  connections: {
    control_panel_probe: ApiE2EConnectionPayload | null;
    gateway_modbus: ApiE2EConnectionPayload | null;
    telemetry_publisher: ApiE2EConnectionPayload | null;
    ems_light_bridge?: ApiE2EConnectionPayload | null;
  };
}

export interface ApiE2EProbeSummaryPayload {
  round_trip_ms: number | null;
  control_plane_total_ms?: number | null;
  active_request_reply_ms?: number | null;
  transport_overhead_ms?: number | null;
  probe_internal_overhead_ms?: number | null;
  probe_nats_connect_ms?: number | null;
  probe_monitoring_fetch_ms?: number | null;
  broker_proxy_handler_ms?: number | null;
  control_panel_to_broker_active_ms?: number | null;
  broker_proxy_internal_ms?: number | null;
  broker_to_ipc_active_ms?: number | null;
  modbus_simulator_round_trip_ms?: number | null;
  reconstructed_active_total_ms?: number | null;
  probe_connection_rtt_ms: number | null;
  gateway_connection_rtt_ms: number | null;
  telemetry_connection_rtt_ms: number | null;
  ems_light_connection_rtt_ms?: number | null;
  reply_status: string | null;
  reply_value: number | null;
}

export interface ApiE2EProbePayload {
  tested_at: string;
  flow_key?: "ems_site" | "ems_light";
  flow_label?: string | null;
  probe_mode?: "direct_nats" | "broker_proxy";
  round_trip_label?: string | null;
  monitoring_visibility?: "control_plane_direct" | "broker_internal" | null;
  request_id: string;
  asset_name: string;
  nats_url: string | null;
  monitoring_url: string | null;
  subject: string;
  request_payload: Record<string, unknown> | null;
  reply_payload: Record<string, unknown> | null;
  summary: ApiE2EProbeSummaryPayload;
  hops: ApiE2EHopPayload[];
  monitoring: ApiE2EMonitoringPayload;
  warnings: string[];
}

export interface ApiE2EMeasurementSamplePayload {
  index: number;
  tested_at: string | null;
  request_id: string | null;
  values: Record<string, number | null>;
}

export interface ApiE2EMeasurementStatPayload {
  key: string;
  label: string;
  count: number;
  min_ms: number | null;
  avg_ms: number | null;
  median_ms: number | null;
  p95_ms: number | null;
  max_ms: number | null;
  stddev_ms: number | null;
}

export interface ApiE2EMeasurementBatchPayload {
  requested_count: number;
  completed_count: number;
  representative_index: number;
  flow_key: "ems_site" | "ems_light";
  sample_interval_seconds?: number | null;
  samples: ApiE2EMeasurementSamplePayload[];
  stats: ApiE2EMeasurementStatPayload[];
}

export interface ApiE2ETestPayload {
  site: SiteReferencePayload | null;
  asset: ApiInventoryAssetPayload | null;
  probe: ApiE2EProbePayload;
  measurement_batch?: ApiE2EMeasurementBatchPayload | null;
}

export interface ApiBrokerOrderSummaryPayload {
  action: string | null;
  order_id: number | null;
  direction: string | null;
  execute_at: string | null;
  target: string | null;
}

export interface ApiBrokerOrderPayload {
  sequence: number;
  observed_at: string;
  subject: string;
  reply_subject: string | null;
  size_bytes: number;
  payload: unknown;
  payload_is_json: boolean;
  summary: ApiBrokerOrderSummaryPayload;
}

export interface ApiOrdersFeedPayload {
  status: string;
  subject: string;
  connected: boolean;
  started_at: string;
  last_message_at: string | null;
  total_seen: number;
  retained: number;
  max_items: number;
  warnings: string[];
  orders: ApiBrokerOrderPayload[];
}

export interface ApiOrdersDispatchPayload {
  status: string;
  request_id: string;
  subject: string;
  tested_at: string;
  round_trip_ms: number | null;
  request_payload: Record<string, unknown>;
  reply_payload: Record<string, unknown>;
}

export interface CentralService {
  name: string;
  status: string;
  summary: string;
  details: string;
  heartbeat: string;
}

export interface SiteSummary {
  siteId: string;
  name: string;
  city: string;
  code: string;
  sector: string;
  capacityMw: number;
  status: string;
  emsSiteStatus: string;
  routesOk: number;
  routesTotal: number;
  lastHeartbeat: string;
  lastJobSummary: string;
}

export interface SiteServiceCard {
  name: string;
  status: string;
  lines: string[];
}

export interface SiteAlert {
  severity: "warning" | "critical";
  message: string;
  timestampLabel: string;
}

export interface RouteSnapshot {
  route: string;
  subject: string;
  publisher: string;
  subscriber: string;
  rate: string;
  status: string;
}

export interface AssetSnapshot {
  assetType: string;
  manufacturer: string;
  model: string;
  powerLabel: string;
  modbusLabel: string;
}

export interface SiteDetail {
  siteId: string;
  services: SiteServiceCard[];
  alerts: SiteAlert[];
  routes: RouteSnapshot[];
  assets: AssetSnapshot[];
  lastProvisioningCompletionRatio: number;
}

export interface ProvisioningStep {
  title: string;
  category: "config" | "deploy" | "verify";
  durationLabel: string;
  status: "done" | "running" | "pending" | "will wait";
}

export interface ProvisioningJob {
  siteId: string;
  jobId: string;
  siteName: string;
  triggeredBy: string;
  startedAgoLabel: string;
  startedAtLabel: string;
  status: "running" | "done";
  completedSteps: number;
  totalSteps: number;
  steps: ProvisioningStep[];
  logs: string[];
}

export interface HopSnapshot {
  label: string;
  latencyMs: number;
  tone: BadgeTone;
}

export interface E2ERow {
  dateLabel: string;
  totalMs: number;
  cpCore: number;
  coreSite: number;
  modbus: number;
  siteLight: number;
  lightRte: number;
  sparkline: number[];
  status: "pass" | "slow";
}

export interface E2EReport {
  siteId: string;
  titleLabel: string;
  trail: HopSnapshot[];
  waterfall: HopSnapshot[];
  latest: E2ERow;
  history: E2ERow[];
  trendLabel: string;
  p95Label: string;
  lastTestLabel: string;
  chartMaxMs: number;
  slaMs: number;
}

export interface ManagedUserSnapshot {
  id: number;
  displayName: string;
  email: string;
  roles: RoleName[];
  isActive: boolean;
  authSource: "oidc";
  lastLoginLabel: string;
}

export interface RoleDefinition {
  label: string;
  permissions: Permission[];
}

export interface MockControlPlaneState {
  centralServices: CentralService[];
  sites: SiteSummary[];
  siteDetails: Record<string, SiteDetail>;
  provisioningJobs: Record<string, ProvisioningJob>;
  e2eReports: Record<string, E2EReport>;
  adminUsers: ManagedUserSnapshot[];
}
