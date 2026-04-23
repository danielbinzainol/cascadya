<script setup lang="ts">
import StatusBadge from "@/components/ui/StatusBadge.vue";
import type { BadgeTone } from "@/types/controlPlane";

withDefaults(
  defineProps<{
    title: string;
    status?: string;
    statusTone?: BadgeTone;
    accentTone?: BadgeTone;
  }>(),
  {
    status: "",
    statusTone: "neutral",
    accentTone: "healthy",
  },
);
</script>

<template>
  <section class="panel-card" :class="`accent-${accentTone}`">
    <header class="panel-head">
      <h3>{{ title }}</h3>
      <StatusBadge v-if="status" :label="status" :tone="statusTone" />
    </header>
    <div class="panel-body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.panel-card {
  position: relative;
  overflow: hidden;
  min-height: 14rem;
  padding: 1.8rem 2rem;
  border-radius: var(--radius-xl);
  background: linear-gradient(180deg, rgba(47, 47, 43, 0.96), rgba(43, 43, 39, 0.92));
  border: 1px solid var(--line);
  box-shadow: var(--shadow-panel);
}

.panel-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 0.35rem;
  background: var(--line-strong);
}

.accent-healthy::before,
.accent-active::before {
  background: linear-gradient(180deg, rgba(128, 211, 71, 0.98), rgba(70, 149, 35, 0.96));
}

.accent-warning::before,
.accent-provisioning::before,
.accent-degraded::before {
  background: linear-gradient(180deg, rgba(215, 167, 63, 0.98), rgba(124, 90, 21, 0.96));
}

.accent-running::before {
  background: linear-gradient(180deg, rgba(121, 168, 255, 0.98), rgba(46, 84, 150, 0.96));
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.panel-head h3 {
  margin: 0;
  color: var(--text);
  font-size: 1.25rem;
}

.panel-body {
  margin-top: 1.6rem;
  display: grid;
  gap: 0.9rem;
  color: var(--muted);
  font-size: 1.08rem;
}
</style>

