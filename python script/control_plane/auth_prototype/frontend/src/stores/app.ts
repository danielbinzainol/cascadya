import { computed } from "vue";
import { defineStore } from "pinia";

import { getE2EReport, getProvisioningJob, mockControlPlane } from "@/mocks/controlPlane";
import type { DashboardMetric } from "@/types/controlPlane";

export const useAppStore = defineStore("app", () => {
  const centralServices = computed(() => mockControlPlane.centralServices);
  const sites = computed(() => mockControlPlane.sites);
  const adminUsers = computed(() => mockControlPlane.adminUsers);

  const dashboardMetrics = computed<DashboardMetric[]>(() => {
    const allSites = mockControlPlane.sites;
    const activeSites = allSites.filter((site) => site.status === "active").length;
    const provisioningSites = allSites.filter((site) => site.status === "provisioning").length;
    const healthyEmsSite = allSites.filter((site) => site.emsSiteStatus === "healthy").length;
    const degradedEmsSite = allSites.filter((site) => site.emsSiteStatus === "degraded").length;
    const routesOk = allSites.reduce((total, site) => total + site.routesOk, 0);
    const routesTotal = allSites.reduce((total, site) => total + site.routesTotal, 0);
    const routeIssues = allSites.filter((site) => site.routesOk < site.routesTotal).length;
    const totalCapacity = allSites.reduce((total, site) => total + site.capacityMw, 0);

    return [
      {
        title: "Sites actifs",
        value: String(activeSites),
        subtitle: `${provisioningSites} en provisioning`,
        tone: "neutral",
      },
      {
        title: "ems-site healthy",
        value: `${healthyEmsSite} / ${allSites.length}`,
        subtitle: `${degradedEmsSite} degraded`,
        tone: healthyEmsSite === allSites.length ? "healthy" : "warning",
      },
      {
        title: "Routes ok",
        value: `${routesOk} / ${routesTotal}`,
        subtitle: `${routeIssues} degraded`,
        tone: routeIssues === 0 ? "healthy" : "warning",
      },
      {
        title: "Capacite aFRR totale",
        value: `${totalCapacity.toFixed(1)} MW`,
        subtitle: `${allSites.length} sites`,
        tone: "neutral",
      },
    ];
  });

  function getSite(siteId: string) {
    return mockControlPlane.sites.find((site) => site.siteId === siteId) ?? mockControlPlane.sites[0];
  }

  function getSiteDetail(siteId: string) {
    return mockControlPlane.siteDetails[siteId] ?? mockControlPlane.siteDetails[mockControlPlane.sites[0].siteId];
  }

  return {
    centralServices,
    sites,
    adminUsers,
    dashboardMetrics,
    getSite,
    getSiteDetail,
    getProvisioningJob,
    getE2EReport,
  };
});
