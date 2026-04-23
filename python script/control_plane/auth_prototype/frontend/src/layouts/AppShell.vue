<script setup lang="ts">
import { computed, watch } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

import StatusBadge from "@/components/ui/StatusBadge.vue";
import { useSessionStore } from "@/stores/session";
import type { DemoProfileKey, Permission } from "@/types/controlPlane";

const router = useRouter();
const route = useRoute();
const session = useSessionStore();

const eyebrowLabel = computed(() => "Vue 3 control plane UI");

const sessionLabel = computed(() =>
  session.demoModeEnabled ? "Profil de demonstration" : "Session FastAPI / Keycloak",
);

const authSourceTone = computed(() => (session.user?.authSource === "oidc" ? "healthy" : "warning"));
const authSourceLabel = computed(() => session.user?.authSource ?? "unknown");

const navItems = computed(() => [
  { label: "Dashboard", to: { name: "dashboard" }, permission: "dashboard:read" as Permission },
  {
    label: "Alertes",
    to: { name: "alerts-center" },
    permission: "dashboard:read" as Permission,
  },
  {
    label: "Provisioning",
    to: { name: "provisioning-center" },
    permission: "provision:prepare" as Permission,
  },
  {
    label: "Test E2E",
    to: { name: "e2e-center" },
    permission: "inventory:scan" as Permission,
  },
  {
    label: "Orders",
    to: { name: "orders-center" },
    permission: "inventory:read" as Permission,
  },
  { label: "Admin", to: { name: "admin" }, permission: "user:read" as Permission },
]);

const visibleNavItems = computed(() =>
  navItems.value.filter((item) => session.hasPermission(item.permission)),
);

watch(
  () => session.currentDemoProfileKey,
  () => {
    if (!session.demoModeEnabled) {
      return;
    }
    const requiredPermission = route.meta.permission as Permission | undefined;
    if (requiredPermission && !session.hasPermission(requiredPermission)) {
      router.replace({
        name: "forbidden",
        query: {
          from: String(route.fullPath),
          needed: requiredPermission,
        },
      });
    }
  },
);
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand-block">
        <p class="eyebrow">{{ eyebrowLabel }}</p>
        <RouterLink class="brand" :to="{ name: 'dashboard' }">Cascadya control plane</RouterLink>
      </div>

      <nav class="nav-strip" aria-label="Primary">
        <RouterLink
          v-for="item in visibleNavItems"
          :key="item.label"
          class="nav-pill"
          :to="item.to"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="session-panel">
        <label class="session-label" for="session-profile">
          {{ sessionLabel }}
        </label>
        <select
          v-if="session.demoModeEnabled"
          id="session-profile"
          class="session-select"
          :value="session.currentDemoProfileKey"
          @change="session.setDemoProfile(($event.target as HTMLSelectElement).value as DemoProfileKey)"
        >
          <option
            v-for="profile in session.availableDemoProfiles"
            :key="profile.key"
            :value="profile.key"
          >
            {{ profile.label }}
          </option>
        </select>

        <div v-if="session.user" class="identity">
          <div class="identity-copy">
            <p class="identity-name">{{ session.user.displayName }}</p>
            <p class="identity-email">{{ session.user.email }}</p>
          </div>

          <div class="identity-badges">
            <StatusBadge :label="authSourceLabel" :tone="authSourceTone" compact />
            <StatusBadge
              :label="session.user.isActive ? 'active' : 'inactive'"
              :tone="session.user.isActive ? 'active' : 'waiting'"
              compact
            />
            <StatusBadge
              v-for="role in session.user.roles"
              :key="role"
              :label="role"
              :tone="role"
              compact
            />
          </div>
        </div>

        <form v-if="!session.demoModeEnabled" class="logout-form" method="post" action="/auth/logout">
          <button class="logout-button" type="submit">Se deconnecter</button>
        </form>
      </div>
    </header>

    <main class="view-stack">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  padding: 2rem;
}

.topbar {
  display: grid;
  grid-template-columns: minmax(0, 20rem) minmax(0, 1fr) minmax(18rem, 24rem);
  gap: 1.5rem;
  align-items: end;
  margin-bottom: 2.2rem;
}

.brand-block {
  display: grid;
  gap: 0.4rem;
}

.eyebrow {
  margin: 0;
  color: var(--muted-2);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.74rem;
}

.brand {
  color: var(--text);
  text-decoration: none;
  font-size: clamp(1.8rem, 1.4vw + 1.2rem, 2.55rem);
  font-weight: 600;
  line-height: 0.95;
}

.nav-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  justify-content: center;
}

.nav-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.9rem;
  padding: 0.7rem 1.1rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  color: var(--muted);
  background: rgba(255, 255, 255, 0.03);
  text-decoration: none;
  transition:
    transform 150ms ease,
    border-color 150ms ease,
    color 150ms ease,
    background 150ms ease;
}

.nav-pill.router-link-active {
  border-color: rgba(122, 168, 255, 0.34);
  color: var(--text);
  background: rgba(82, 117, 176, 0.2);
}

.nav-pill:hover {
  transform: translateY(-1px);
  border-color: var(--line-strong);
  color: var(--text);
}

.session-panel {
  justify-self: end;
  width: min(100%, 24rem);
  display: grid;
  gap: 0.7rem;
  padding: 1rem 1.1rem 1.05rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background:
    linear-gradient(180deg, rgba(17, 21, 27, 0.96), rgba(13, 16, 21, 0.92)),
    radial-gradient(circle at top right, rgba(122, 168, 255, 0.14), transparent 48%);
  box-shadow: var(--shadow-panel);
}

.session-label {
  color: var(--muted-2);
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.session-select {
  width: 100%;
  min-height: 2.8rem;
  padding: 0.75rem 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
  font: inherit;
}

.identity {
  display: grid;
  gap: 0.7rem;
}

.identity-copy {
  min-width: 0;
}

.identity-name,
.identity-email {
  margin: 0;
}

.identity-name {
  color: var(--text);
  font-size: 1rem;
  font-weight: 600;
}

.identity-email {
  color: var(--muted);
  font-size: 0.92rem;
}

.identity-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.logout-form {
  margin-top: 0.25rem;
}

.logout-button {
  width: 100%;
  min-height: 2.9rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 154, 139, 0.28);
  background: rgba(255, 154, 139, 0.1);
  color: var(--text);
  font: inherit;
  cursor: pointer;
  transition:
    border-color 150ms ease,
    transform 150ms ease,
    background 150ms ease;
}

.logout-button:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 154, 139, 0.44);
  background: rgba(255, 154, 139, 0.16);
}

.view-stack {
  animation: rise-in 300ms ease;
}

@media (max-width: 1200px) {
  .topbar {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .nav-strip {
    justify-content: flex-start;
  }

  .session-panel {
    justify-self: stretch;
    width: 100%;
  }
}
</style>
