import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import AppShell from "@/layouts/AppShell.vue";
import AdminView from "@/modules/admin/views/AdminView.vue";
import AlertsView from "@/modules/alerts/views/AlertsView.vue";
import ForbiddenView from "@/modules/admin/views/ForbiddenView.vue";
import DashboardView from "@/modules/dashboard/views/DashboardView.vue";
import E2EView from "@/modules/e2e/views/E2EView.vue";
import OrdersMonitorView from "@/modules/orders/views/OrdersMonitorView.vue";
import OrdersView from "@/modules/orders/views/OrdersView.vue";
import ProvisioningView from "@/modules/provisioning/views/ProvisioningView.vue";
import SiteDetailView from "@/modules/sites/views/SiteDetailView.vue";
import { pinia } from "@/stores/pinia";
import { useSessionStore } from "@/stores/session";
import type { Permission } from "@/types/controlPlane";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    component: AppShell,
    children: [
      {
        path: "",
        redirect: {
          name: "dashboard",
        },
      },
      {
        path: "app",
        name: "dashboard",
        component: DashboardView,
        meta: {
          title: "Dashboard",
          permission: "dashboard:read",
        },
      },
      {
        path: "sites/:siteId",
        name: "site-detail",
        component: SiteDetailView,
        meta: {
          title: "Site detail",
          permission: "site:read",
        },
      },
      {
        path: "alerts",
        name: "alerts-center",
        component: AlertsView,
        meta: {
          title: "Alertes",
          permission: "dashboard:read",
        },
      },
      {
        path: "provisioning",
        name: "provisioning-center",
        component: ProvisioningView,
        meta: {
          title: "Provisioning",
          permission: "provision:prepare",
        },
      },
      {
        path: "e2e",
        name: "e2e-center",
        component: E2EView,
        meta: {
          title: "Test E2E",
          permission: "inventory:scan",
        },
      },
      {
        path: "orders",
        name: "orders-center",
        component: OrdersView,
        meta: {
          title: "Orders",
          permission: "inventory:read",
        },
      },
      {
        path: "orders/monitor",
        name: "orders-monitor",
        component: OrdersMonitorView,
        meta: {
          title: "Modbus Monitor",
          permission: "inventory:scan",
        },
      },
      {
        path: "sites/:siteId/provisioning",
        name: "site-provisioning",
        component: ProvisioningView,
        meta: {
          title: "Provisioning",
          permission: "provision:prepare",
        },
      },
      {
        path: "sites/:siteId/e2e",
        name: "site-e2e",
        component: E2EView,
        meta: {
          title: "Test E2E",
          permission: "inventory:scan",
        },
      },
      {
        path: "admin",
        name: "admin",
        component: AdminView,
        meta: {
          title: "Admin",
          permission: "user:read",
        },
      },
      {
        path: "forbidden",
        name: "forbidden",
        component: ForbiddenView,
        meta: {
          title: "Acces refuse",
        },
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach(async (to) => {
  const session = useSessionStore(pinia);
  const basePath = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL.slice(0, -1)
    : import.meta.env.BASE_URL;
  await session.initialize(`${basePath}${to.fullPath}`);
  if (session.redirectingToLogin) {
    return false;
  }
  const requiredPermission = to.meta.permission as Permission | undefined;

  if (requiredPermission && !session.hasPermission(requiredPermission)) {
    return {
      name: "forbidden",
      query: {
        from: String(to.fullPath),
        needed: requiredPermission,
      },
    };
  }

  document.title = `Cascadya control plane - ${String(to.meta.title ?? "Application")}`;
  return true;
});

export default router;
