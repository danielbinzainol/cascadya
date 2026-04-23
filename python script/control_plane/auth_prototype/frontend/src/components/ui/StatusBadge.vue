<script setup lang="ts">
import { computed } from "vue";

import type { BadgeTone } from "@/types/controlPlane";

const props = withDefaults(
  defineProps<{
    label: string;
    tone?: BadgeTone;
    compact?: boolean;
  }>(),
  {
    tone: "neutral",
    compact: false,
  },
);

const classes = computed(() => [`tone-${props.tone}`, props.compact ? "compact" : ""]);
</script>

<template>
  <span class="status-badge" :class="classes">{{ label }}</span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.15rem;
  padding: 0.42rem 0.95rem;
  border-radius: 999px;
  border: 1px solid transparent;
  font-family: var(--font-ui);
  font-size: 0.96rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.compact {
  min-height: 1.8rem;
  padding: 0.3rem 0.72rem;
  font-size: 0.85rem;
}

.tone-neutral {
  background: var(--pill-neutral-bg);
  color: var(--text);
  border-color: var(--line-strong);
}

.tone-healthy,
.tone-active,
.tone-done,
.tone-pass {
  background: var(--pill-green-bg);
  color: var(--green);
  border-color: rgba(128, 211, 71, 0.2);
}

.tone-degraded {
  background: var(--pill-amber-bg);
  color: var(--amber);
  border-color: rgba(236, 184, 72, 0.2);
}

.tone-provisioning,
.tone-warning,
.tone-slow {
  background: var(--pill-gold-bg);
  color: var(--gold);
  border-color: rgba(198, 153, 57, 0.2);
}

.tone-waiting,
.tone-pending {
  background: var(--pill-neutral-bg);
  color: var(--muted);
  border-color: var(--line);
}

.tone-running,
.tone-operator,
.tone-provisioning_manager {
  background: var(--pill-blue-bg);
  color: var(--blue);
  border-color: rgba(122, 168, 255, 0.18);
}

.tone-admin {
  background: var(--pill-red-bg);
  color: var(--red-soft);
  border-color: rgba(255, 139, 125, 0.18);
}

.tone-viewer {
  background: var(--pill-neutral-bg);
  color: var(--muted);
  border-color: var(--line);
}
</style>
