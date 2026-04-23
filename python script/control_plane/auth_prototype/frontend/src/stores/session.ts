import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { fetchCurrentUser, fetchUiConfig } from "@/api/auth";
import { ApiError } from "@/api/client";
import { demoProfiles } from "@/mocks/controlPlane";
import type {
  ApiSessionUserPayload,
  ApiUiConfigPayload,
  DemoProfileKey,
  Permission,
  SessionUser,
  UiConfig,
} from "@/types/controlPlane";

const AUTH_MODE = import.meta.env.VITE_AUTH_MODE === "mock" ? "mock" : "backend";
const defaultUiConfig: UiConfig = {
  dashboards: {
    wazuhUrl: null,
  },
};

function mapApiUser(payload: ApiSessionUserPayload): SessionUser {
  return {
    id: payload.id,
    keycloakUuid: payload.keycloak_uuid,
    username: payload.username,
    displayName: payload.display_name,
    email: payload.email,
    roles: payload.roles,
    permissions: payload.permissions,
    isActive: payload.is_active,
    authSource: payload.auth_source,
  };
}

function mapApiUiConfig(payload: ApiUiConfigPayload): UiConfig {
  return {
    dashboards: {
      wazuhUrl: payload.dashboards.wazuh.url,
    },
  };
}

export const useSessionStore = defineStore("session", () => {
  const ready = ref(false);
  const currentDemoProfileKey = ref<DemoProfileKey>("admin");
  const backendUser = ref<SessionUser | null>(AUTH_MODE === "mock" ? demoProfiles.admin : null);
  const backendUiConfig = ref<UiConfig>({ ...defaultUiConfig, dashboards: { ...defaultUiConfig.dashboards } });
  const redirectingToLogin = ref(false);
  const authError = ref<string | null>(null);
  const demoModeEnabled = computed(() => AUTH_MODE === "mock");

  const availableDemoProfiles = computed(() =>
    Object.entries(demoProfiles).map(([key, profile]) => ({
      key: key as DemoProfileKey,
      label: `${profile.displayName} (${profile.roles.join(", ")})`,
      profile,
    })),
  );

  const user = computed<SessionUser | null>(() =>
    demoModeEnabled.value ? demoProfiles[currentDemoProfileKey.value] : backendUser.value,
  );
  const uiConfig = computed<UiConfig>(() =>
    demoModeEnabled.value ? defaultUiConfig : backendUiConfig.value,
  );
  const wazuhDashboardUrl = computed(() => uiConfig.value.dashboards.wazuhUrl);
  const isAdmin = computed(() => user.value?.roles.includes("admin") ?? false);

  async function initialize(nextPath?: string) {
    if (ready.value) {
      return;
    }
    redirectingToLogin.value = false;
    authError.value = null;
    if (demoModeEnabled.value) {
      ready.value = true;
      return;
    }

    try {
      const [userPayload, uiConfigPayload] = await Promise.all([fetchCurrentUser(), fetchUiConfig()]);
      backendUser.value = mapApiUser(userPayload);
      backendUiConfig.value = mapApiUiConfig(uiConfigPayload);
      redirectingToLogin.value = false;
      ready.value = true;
    } catch (error) {
      if (error instanceof ApiError && error.statusCode === 401) {
        redirectToLogin(nextPath);
        return;
      }

      authError.value = error instanceof Error ? error.message : "Unable to initialize session";
      throw error;
    }
  }

  function redirectToLogin(nextPath?: string) {
    if (typeof window === "undefined") {
      return;
    }
    redirectingToLogin.value = true;
    const fallbackPath = `${window.location.pathname}${window.location.search}`;
    const destination = nextPath || fallbackPath || "/ui/app";
    window.location.assign(`/auth/login?next=${encodeURIComponent(destination)}`);
  }

  function setDemoProfile(profileKey: DemoProfileKey) {
    if (!demoModeEnabled.value) {
      return;
    }
    currentDemoProfileKey.value = profileKey;
    ready.value = true;
  }

  function hasPermission(permission: Permission) {
    return user.value?.permissions.includes(permission) ?? false;
  }

  function hasAnyPermission(permissions: Permission[]) {
    return permissions.some((permission) => hasPermission(permission));
  }

  return {
    ready,
    demoModeEnabled,
    redirectingToLogin,
    authError,
    currentDemoProfileKey,
    availableDemoProfiles,
    user,
    uiConfig,
    wazuhDashboardUrl,
    isAdmin,
    initialize,
    redirectToLogin,
    setDemoProfile,
    hasPermission,
    hasAnyPermission,
  };
});
