<script setup lang="ts">
import type { BadgeTone } from "@/types/controlPlane";

withDefaults(
  defineProps<{
    title: string;
    value: string;
    subtitle: string;
    tone?: BadgeTone;
  }>(),
  {
    tone: "neutral",
  },
);
</script>

<template>
  <section class="metric-card" :class="`tone-${tone}`">
    <p class="metric-title">{{ title }}</p>
    <p class="metric-value">{{ value }}</p>
    <p class="metric-subtitle">{{ subtitle }}</p>
  </section>
</template>

<style scoped>
.metric-card {
  min-height: 10.6rem;
  padding: 1.7rem 1.9rem;
  border-radius: var(--radius-xl);
  background: linear-gradient(180deg, rgba(34, 35, 31, 0.96), rgba(29, 30, 27, 0.92));
  border: 1px solid var(--line);
  box-shadow: var(--shadow-panel);
}

.metric-title {
  margin: 0;
  color: var(--muted);
  font-size: 1.12rem;
}

.metric-value {
  margin: 1rem 0 0;
  color: var(--text);
  font-size: clamp(2rem, 2vw + 1.35rem, 3rem);
  font-weight: 600;
  line-height: 1.02;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.metric-subtitle {
  margin: 0.85rem 0 0;
  color: var(--muted-2);
  font-size: 1rem;
}

.tone-healthy .metric-value,
.tone-active .metric-value {
  color: var(--green);
}

.tone-warning .metric-value,
.tone-slow .metric-value,
.tone-provisioning .metric-value {
  color: var(--gold);
}
</style>

