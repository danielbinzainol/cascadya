<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute } from "vue-router";

import StatusBadge from "@/components/ui/StatusBadge.vue";
import { useSessionStore } from "@/stores/session";

const route = useRoute();
const session = useSessionStore();

const fromPath = computed(() => String(route.query.from ?? "/app"));
const neededPermission = computed(() => String(route.query.needed ?? "unknown"));
const roleBadges = computed(() => session.user?.roles ?? []);
const permissionsLabel = computed(() => session.user?.permissions.join(", ") ?? "Aucune permission chargee");
</script>

<template>
  <section class="forbidden-shell">
    <div class="forbidden-card">
      <p class="eyebrow">Access control</p>
      <h1>Acces refuse</h1>
      <p class="body">
        Cette page demande la permission <code>{{ neededPermission }}</code>. Le profil actif ne la possede pas.
      </p>

      <div class="badge-row">
        <StatusBadge
          v-for="role in roleBadges"
          :key="role"
          :label="role"
          :tone="role"
        />
      </div>

      <p class="muted permissions">
        Permissions actuelles :
        <span class="mono">{{ permissionsLabel }}</span>
      </p>

      <div class="actions">
        <RouterLink class="action-button" :to="{ name: 'dashboard' }">Retour dashboard</RouterLink>
        <RouterLink class="action-button" :to="fromPath">Reessayer la route</RouterLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.forbidden-shell {
  display: grid;
  place-items: center;
  min-height: 60vh;
}

.forbidden-card {
  width: min(100%, 56rem);
  padding: 2rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background:
    linear-gradient(180deg, rgba(17, 20, 24, 0.96), rgba(11, 13, 17, 0.94)),
    radial-gradient(circle at top right, rgba(255, 154, 139, 0.12), transparent 46%);
  box-shadow: var(--shadow-panel);
}

.eyebrow {
  color: var(--muted-2);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.76rem;
}

.forbidden-card h1 {
  margin-top: 0.9rem;
  font-size: clamp(2rem, 2vw + 1rem, 3rem);
}

.body {
  margin-top: 1rem;
  color: var(--muted);
  font-size: 1.08rem;
  line-height: 1.6;
}

.badge-row {
  display: flex;
  gap: 0.7rem;
  margin-top: 1.2rem;
  flex-wrap: wrap;
}

.permissions {
  margin-top: 1.1rem;
  line-height: 1.7;
}

.actions {
  display: flex;
  gap: 0.9rem;
  margin-top: 1.5rem;
  flex-wrap: wrap;
}
</style>
