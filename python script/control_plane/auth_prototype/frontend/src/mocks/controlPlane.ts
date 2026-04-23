import type {
  BadgeTone,
  DemoProfileKey,
  E2EReport,
  E2ERow,
  ManagedUserSnapshot,
  MockControlPlaneState,
  Permission,
  ProvisioningJob,
  RoleDefinition,
  RoleName,
  SessionUser,
  SiteDetail,
  SiteSummary,
} from "@/types/controlPlane";

const ALL_PERMISSIONS: Permission[] = [
  "audit:read",
  "dashboard:read",
  "inventory:read",
  "inventory:scan",
  "provision:prepare",
  "provision:run",
  "provision:cancel",
  "site:read",
  "site:write",
  "user:read",
  "user:write",
  "role:assign",
];

export const roleCatalog: Record<RoleName, RoleDefinition> = {
  viewer: {
    label: "Viewer",
    permissions: ["dashboard:read", "inventory:read", "site:read"],
  },
  operator: {
    label: "Operator",
    permissions: ["dashboard:read", "inventory:read", "inventory:scan", "site:read"],
  },
  provisioning_manager: {
    label: "Provisioning manager",
    permissions: [
      "dashboard:read",
      "inventory:read",
      "inventory:scan",
      "provision:prepare",
      "provision:run",
      "provision:cancel",
      "site:read",
    ],
  },
  admin: {
    label: "Admin",
    permissions: ALL_PERMISSIONS,
  },
};

export const demoProfiles: Record<DemoProfileKey, SessionUser> = {
  admin: {
    id: 2,
    keycloakUuid: "14d06982-70f3-45f9-a09c-035753af5ecb",
    username: "daniel.binzainol@cascadya.com",
    displayName: "Daniel Bin Zainol",
    email: "daniel.binzainol@cascadya.com",
    roles: ["admin"],
    permissions: roleCatalog.admin.permissions,
    isActive: true,
    authSource: "oidc",
  },
  provisioning_manager: {
    id: 8,
    keycloakUuid: "b9154b58-5397-40c6-bd1c-0d9e5197d511",
    username: "ops.provisioning@cascadya.com",
    displayName: "Ops Provisioning",
    email: "ops.provisioning@cascadya.com",
    roles: ["provisioning_manager"],
    permissions: roleCatalog.provisioning_manager.permissions,
    isActive: true,
    authSource: "oidc",
  },
  operator: {
    id: 3,
    keycloakUuid: "0dbd0f05-8732-44b0-a14a-30250dd9ac06",
    username: "luc.payen@cascadya.com",
    displayName: "Luc Payen",
    email: "luc.payen@cascadya.com",
    roles: ["operator"],
    permissions: roleCatalog.operator.permissions,
    isActive: true,
    authSource: "oidc",
  },
  viewer: {
    id: 4,
    keycloakUuid: "ce2e007a-4f17-4cec-be09-73f936fc1b59",
    username: "mahmoud.kchouk@cascadya.com",
    displayName: "Mahmoud KCHOUK",
    email: "mahmoud.kchouk@cascadya.com",
    roles: ["viewer"],
    permissions: roleCatalog.viewer.permissions,
    isActive: true,
    authSource: "oidc",
  },
};

const sites: SiteSummary[] = [
  {
    siteId: "ouest-consigne",
    name: "Ouest Consigne",
    city: "Carquefou",
    code: "44",
    sector: "Lavage bouteilles",
    capacityMw: 2.5,
    status: "active",
    emsSiteStatus: "healthy",
    routesOk: 6,
    routesTotal: 6,
    lastHeartbeat: "12s ago",
    lastJobSummary: "12/12 steps completed - 2026-03-15 14:30 UTC - triggered by operator.luc@cascadya.com",
  },
  {
    siteId: "usine-nord",
    name: "Usine Nord",
    city: "Dunkerque",
    code: "59",
    sector: "Fours industriels",
    capacityMw: 6,
    status: "active",
    emsSiteStatus: "degraded",
    routesOk: 4,
    routesTotal: 6,
    lastHeartbeat: "3m ago",
    lastJobSummary: "No active job",
  },
  {
    siteId: "verrerie-est",
    name: "Verrerie Est",
    city: "Troyes",
    code: "10",
    sector: "Fusion verre",
    capacityMw: 4,
    status: "active",
    emsSiteStatus: "healthy",
    routesOk: 6,
    routesTotal: 6,
    lastHeartbeat: "18s ago",
    lastJobSummary: "Last validation green",
  },
  {
    siteId: "papeterie-vosges",
    name: "Papeterie Vosges",
    city: "Epinal",
    code: "88",
    sector: "Papier recycle",
    capacityMw: 8,
    status: "active",
    emsSiteStatus: "healthy",
    routesOk: 6,
    routesTotal: 6,
    lastHeartbeat: "5s ago",
    lastJobSummary: "No active job",
  },
  {
    siteId: "laiterie-bretagne",
    name: "Laiterie Bretagne",
    city: "Rennes",
    code: "35",
    sector: "Process laitier",
    capacityMw: 3,
    status: "provisioning",
    emsSiteStatus: "waiting",
    routesOk: 0,
    routesTotal: 6,
    lastHeartbeat: "---",
    lastJobSummary: "Provisioning prepared - awaiting operator run",
  },
];

const centralServices = [
  {
    name: "ems-core",
    status: "healthy",
    summary: "Config v43 synced",
    details: "Gere 12 sites",
    heartbeat: "Dernier heartbeat il y a 12s",
  },
  {
    name: "ems-light",
    status: "healthy",
    summary: "Config v18 synced",
    details: "IEC 104 active - RTE connected",
    heartbeat: "Dernier heartbeat il y a 8s",
  },
];

function buildStandardRoutes(siteId: string, routesOk: number, status: string) {
  const routeStatus = status === "degraded" ? "degraded" : "healthy";
  return [
    {
      route: "telemetry_power",
      subject: `cascadya/${siteId}/telemetry/power`,
      publisher: "ems-site",
      subscriber: "ems-core",
      rate: "60/min",
      status: routeStatus,
    },
    {
      route: "setpoint_command",
      subject: `cascadya/${siteId}/command/setpoint`,
      publisher: "ems-core",
      subscriber: "ems-site",
      rate: routesOk < 6 ? "8/min" : "12/min",
      status: routeStatus,
    },
    {
      route: "capacity_update",
      subject: `cascadya/${siteId}/command/capacity-update`,
      publisher: "control-plane",
      subscriber: "ems-site",
      rate: "0/min",
      status: routeStatus,
    },
    {
      route: "rte_signal",
      subject: `cascadya/${siteId}/telemetry/rte-signal`,
      publisher: "ems-light",
      subscriber: "ems-core",
      rate: "2/min",
      status: routeStatus,
    },
    {
      route: "heartbeat",
      subject: `cascadya/${siteId}/heartbeat/ems-site`,
      publisher: "ems-site",
      subscriber: "control-plane",
      rate: routesOk < 6 ? "1/min" : "2/min",
      status: routeStatus,
    },
  ];
}

function buildSiteDetail(site: SiteSummary): SiteDetail {
  if (site.siteId === "ouest-consigne") {
    return {
      siteId: site.siteId,
      services: [
        {
          name: "ems-site",
          status: "healthy",
          lines: ["Config v3 synced", "Modbus connected", "Buffer 0 msg pending", "HB 12s ago"],
        },
      ],
      alerts: [
        {
          severity: "warning",
          message: "Config drift ems-site : applied v2, desired v3 (drift 35 min)",
          timestampLabel: "09:30 UTC",
        },
      ],
      routes: buildStandardRoutes(site.siteId, site.routesOk, site.emsSiteStatus),
      assets: [
        {
          assetType: "Chaudiere electrique",
          manufacturer: "PARAT Halvorsen",
          model: "IEH 6MW",
          powerLabel: "6 000 kW",
          modbusLabel: "192.168.1.100:502",
        },
        {
          assetType: "Capteur pression",
          manufacturer: "Endress+Hauser",
          model: "PMC51",
          powerLabel: "---",
          modbusLabel: "192.168.1.100:502 reg 30010",
        },
      ],
      lastProvisioningCompletionRatio: 1,
    };
  }

  if (site.siteId === "laiterie-bretagne") {
    return {
      siteId: site.siteId,
      services: [
        {
          name: "ems-site",
          status: "waiting",
          lines: ["Config staged", "Edge PC not yet online", "Vault cert pending", "HB ---"],
        },
      ],
      alerts: [
        {
          severity: "warning",
          message: "Provisioning running - waiting ems-site first heartbeat before route validation",
          timestampLabel: "10:06 UTC",
        },
      ],
      routes: buildStandardRoutes(site.siteId, site.routesOk, "waiting"),
      assets: [
        {
          assetType: "Chaudiere electrique",
          manufacturer: "PARAT Halvorsen",
          model: "IEH 3MW",
          powerLabel: "3 000 kW",
          modbusLabel: "reserved - pending deploy",
        },
      ],
      lastProvisioningCompletionRatio: 7 / 12,
    };
  }

  return {
    siteId: site.siteId,
    services: [
      {
        name: "ems-site",
        status: site.emsSiteStatus,
        lines: ["Config synced", `Status ${site.emsSiteStatus}`, `${site.routesOk}/${site.routesTotal} routes healthy`, `HB ${site.lastHeartbeat}`],
      },
    ],
    alerts:
      site.emsSiteStatus === "degraded"
        ? [
            {
              severity: "warning",
              message: "One central path is degraded and needs operator review.",
              timestampLabel: "11:12 UTC",
            },
          ]
        : [],
    routes: buildStandardRoutes(site.siteId, site.routesOk, site.emsSiteStatus),
    assets: [
      {
        assetType: "Edge controller",
        manufacturer: "Beckhoff",
        model: "CX52x0",
        powerLabel: "---",
        modbusLabel: "10.42.x.x:502",
      },
      {
        assetType: "Power meter",
        manufacturer: "Siemens",
        model: "PAC3200",
        powerLabel: "---",
        modbusLabel: "10.42.x.x:502 reg 41001",
      },
    ],
    lastProvisioningCompletionRatio: site.status === "provisioning" ? 0.66 : 1,
  };
}

const baseHistory: E2ERow[] = [
  {
    dateLabel: "18/03 10:06",
    totalMs: 847,
    cpCore: 57,
    coreSite: 180,
    modbus: 95,
    siteLight: 210,
    lightRte: 305,
    sparkline: [4, 5, 5, 6, 5, 5, 4],
    status: "pass",
  },
  {
    dateLabel: "17/03 22:00",
    totalMs: 912,
    cpCore: 62,
    coreSite: 195,
    modbus: 88,
    siteLight: 245,
    lightRte: 322,
    sparkline: [5, 5, 6, 5, 4, 5, 5],
    status: "pass",
  },
  {
    dateLabel: "17/03 14:00",
    totalMs: 780,
    cpCore: 48,
    coreSite: 165,
    modbus: 92,
    siteLight: 198,
    lightRte: 277,
    sparkline: [4, 4, 5, 4, 4, 4, 4],
    status: "pass",
  },
  {
    dateLabel: "16/03 22:00",
    totalMs: 1420,
    cpCore: 55,
    coreSite: 380,
    modbus: 102,
    siteLight: 410,
    lightRte: 473,
    sparkline: [5, 6, 7, 5, 6, 7, 6],
    status: "slow",
  },
  {
    dateLabel: "16/03 14:00",
    totalMs: 820,
    cpCore: 50,
    coreSite: 172,
    modbus: 90,
    siteLight: 205,
    lightRte: 303,
    sparkline: [4, 4, 4, 5, 4, 4, 5],
    status: "pass",
  },
];

function buildE2EReport(siteId: string, titleLabel: string, latest: E2ERow): E2EReport {
  return {
    siteId,
    titleLabel,
    trail: [
      { label: "control plane", latencyMs: 12, tone: "running" },
      { label: "ems-core", latencyMs: 180, tone: "neutral" },
      { label: "ems-site", latencyMs: 95, tone: "neutral" },
      { label: "modbus", latencyMs: 210, tone: "neutral" },
      { label: "ems-light", latencyMs: 305, tone: "neutral" },
      { label: "rte ack", latencyMs: 45, tone: "neutral" },
    ],
    waterfall: [
      { label: "CP -> NATS", latencyMs: 12, tone: "running" },
      { label: "NATS -> ems-core", latencyMs: 45, tone: "running" },
      { label: "ems-core -> ems-site", latencyMs: latest.coreSite, tone: "running" },
      { label: "ems-site -> modbus write", latencyMs: latest.modbus, tone: "healthy" },
      { label: "ems-site -> ems-light (ack)", latencyMs: latest.siteLight, tone: "running" },
      { label: "ems-light -> rte ack", latencyMs: latest.lightRte, tone: latest.status === "slow" ? "warning" : "healthy" },
    ],
    latest,
    history: baseHistory,
    trendLabel: latest.status === "slow" ? "watch" : "stable",
    p95Label: "p95: 920 ms",
    lastTestLabel: "10:06 UTC",
    chartMaxMs: 2500,
    slaMs: 2000,
  };
}

const provisioningJobs: Record<string, ProvisioningJob> = {
  "laiterie-bretagne": {
    siteId: "laiterie-bretagne",
    jobId: "job abc-123",
    siteName: "Laiterie Bretagne",
    triggeredBy: "operator.luc@cascadya.com",
    startedAgoLabel: "started 2 min ago",
    startedAtLabel: "10:00 UTC",
    status: "running",
    completedSteps: 7,
    totalSteps: 12,
    steps: [
      { title: "Create NATS subjects + streams", category: "config", durationLabel: "1.8s", status: "done" },
      { title: "Generate Vault PKI cert", category: "config", durationLabel: "3.2s", status: "done" },
      { title: "Generate config ems-site", category: "config", durationLabel: "0.4s", status: "done" },
      { title: "Patch config ems-core (+laiterie-bretagne)", category: "config", durationLabel: "0.6s", status: "done" },
      { title: "Patch config ems-light (+laiterie-bretagne, CA=13)", category: "config", durationLabel: "0.5s", status: "done" },
      { title: "Push config ems-core (v43 -> v44)", category: "deploy", durationLabel: "0.1s", status: "done" },
      { title: "Push config ems-light (v18 -> v19)", category: "deploy", durationLabel: "0.1s", status: "done" },
      { title: "Verify central services hot reload", category: "deploy", durationLabel: "running", status: "running" },
      { title: "Stage ems-site edge PC", category: "deploy", durationLabel: "---", status: "pending" },
      { title: "Wait ems-site first heartbeat", category: "verify", durationLabel: "---", status: "will wait" },
      { title: "Validate NATS routing", category: "verify", durationLabel: "---", status: "pending" },
      { title: "Test E2E setpoint", category: "verify", durationLabel: "---", status: "pending" },
    ],
    logs: [
      "10:00:01 OK Created stream TELEMETRY_laiterie-bretagne",
      "10:00:02 OK Created stream COMMAND_laiterie-bretagne",
      "10:00:03 OK Verified permissions for NATS account cascadya",
      "10:00:04 OK Issued cert ems-site.laiterie-bretagne.cascadya.local (TTL 30d)",
      "10:00:07 OK AppRole secret_id generated (TTL 1h)",
      "10:00:08 OK Config ems-site v1 generated (hash: sha256:e4f2...)",
      "10:00:08 OK Config ems-core v44 patched (+laiterie-bretagne)",
      "10:00:09 OK Config ems-light v19 patched (CA=13)",
      "10:00:10 OK Reload request sent to ems-core",
      "10:00:11 OK Reload request sent to ems-light",
      "10:00:14 ... Waiting for ems-core hot reload proof",
      "10:00:16 ... Waiting for ems-light hot reload proof",
    ],
  },
};

const e2eReports: Record<string, E2EReport> = {
  "ouest-consigne": buildE2EReport("ouest-consigne", "Test E2E setpoint - Ouest Consigne", baseHistory[0]),
};

const adminUsers: ManagedUserSnapshot[] = [
  {
    id: 2,
    displayName: "Daniel Bin Zainol",
    email: "daniel.binzainol@cascadya.com",
    roles: ["admin"],
    isActive: true,
    authSource: "oidc",
    lastLoginLabel: "just now",
  },
  {
    id: 3,
    displayName: "Luc Payen",
    email: "luc.payen@cascadya.com",
    roles: ["operator"],
    isActive: true,
    authSource: "oidc",
    lastLoginLabel: "9 min ago",
  },
  {
    id: 4,
    displayName: "Mahmoud KCHOUK",
    email: "mahmoud.kchouk@cascadya.com",
    roles: ["viewer"],
    isActive: true,
    authSource: "oidc",
    lastLoginLabel: "14 min ago",
  },
  {
    id: 5,
    displayName: "Dominique Rakowski",
    email: "dominique.rakowski@cascadya.com",
    roles: ["operator"],
    isActive: true,
    authSource: "oidc",
    lastLoginLabel: "21 min ago",
  },
  {
    id: 6,
    displayName: "Loris Amabile",
    email: "loris.amabile@cascadya.com",
    roles: ["viewer"],
    isActive: true,
    authSource: "oidc",
    lastLoginLabel: "never",
  },
];

const siteDetails = Object.fromEntries(sites.map((site) => [site.siteId, buildSiteDetail(site)])) as Record<string, SiteDetail>;

const defaultProvisioningJob: ProvisioningJob = {
  siteId: "ouest-consigne",
  jobId: "job last-green",
  siteName: "Ouest Consigne",
  triggeredBy: "operator.luc@cascadya.com",
  startedAgoLabel: "completed 12 days ago",
  startedAtLabel: "2026-03-15 14:30 UTC",
  status: "done",
  completedSteps: 12,
  totalSteps: 12,
  steps: [
    { title: "Config generated", category: "config", durationLabel: "0.9s", status: "done" },
    { title: "Central patches applied", category: "config", durationLabel: "1.1s", status: "done" },
    { title: "Central services reloaded", category: "deploy", durationLabel: "2.4s", status: "done" },
    { title: "Edge PC staged", category: "deploy", durationLabel: "17.2s", status: "done" },
    { title: "Heartbeat validated", category: "verify", durationLabel: "8.0s", status: "done" },
    { title: "E2E setpoint validated", category: "verify", durationLabel: "0.9s", status: "done" },
  ],
  logs: [
    "14:30:01 OK Provisioning job started",
    "14:30:15 OK Central config reloaded",
    "14:30:29 OK ems-site first heartbeat seen",
    "14:30:41 OK NATS routes healthy",
    "14:30:48 OK E2E setpoint under SLA",
  ],
};

const defaultE2EReport = buildE2EReport("default", "Test E2E setpoint", baseHistory[1]);

export const mockControlPlane: MockControlPlaneState = {
  centralServices,
  sites,
  siteDetails,
  provisioningJobs,
  e2eReports,
  adminUsers,
};

export function getProvisioningJob(siteId: string): ProvisioningJob {
  const site = sites.find((entry) => entry.siteId === siteId);
  const job = mockControlPlane.provisioningJobs[siteId];
  if (job) {
    return job;
  }
  return {
    ...defaultProvisioningJob,
    siteId,
    siteName: site?.name ?? defaultProvisioningJob.siteName,
  };
}

export function getE2EReport(siteId: string): E2EReport {
  const site = sites.find((entry) => entry.siteId === siteId);
  const report = mockControlPlane.e2eReports[siteId];
  if (report) {
    return report;
  }
  return {
    ...defaultE2EReport,
    siteId,
    titleLabel: `Test E2E setpoint - ${site?.name ?? "Site"}`,
  };
}

export function statusTone(status: string): BadgeTone {
  const normalized = status.toLowerCase();
  if (normalized === "healthy" || normalized === "done" || normalized === "pass" || normalized === "succeeded") {
    return "healthy";
  }
  if (normalized === "active") {
    return "active";
  }
  if (normalized === "online" || normalized === "registered") {
    return "healthy";
  }
  if (normalized === "running") {
    return "running";
  }
  if (normalized === "prepared") {
    return "pending";
  }
  if (normalized === "discovered" || normalized === "requested") {
    return "waiting";
  }
  if (normalized === "degraded") {
    return "degraded";
  }
  if (normalized === "provisioning") {
    return "provisioning";
  }
  if (normalized === "waiting") {
    return "waiting";
  }
  if (normalized === "pending") {
    return "pending";
  }
  if (normalized === "superseded") {
    return "warning";
  }
  if (normalized === "failed" || normalized === "offline" || normalized === "cancelled" || normalized === "inactive") {
    return "critical";
  }
  if (normalized === "will wait" || normalized === "slow") {
    return "warning";
  }
  if (normalized === "admin") {
    return "admin";
  }
  if (normalized === "operator") {
    return "operator";
  }
  if (normalized === "provisioning_manager") {
    return "provisioning_manager";
  }
  if (normalized === "viewer") {
    return "viewer";
  }
  return "neutral";
}
