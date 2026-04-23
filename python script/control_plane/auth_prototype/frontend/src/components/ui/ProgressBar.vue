<script setup lang="ts">
import { computed } from "vue";

import type { BadgeTone } from "@/types/controlPlane";

const props = withDefaults(
  defineProps<{
    value: number;
    max: number;
    tone?: BadgeTone;
  }>(),
  {
    tone: "healthy",
  },
);

const ratio = computed(() => {
  if (props.max <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(0, (props.value / props.max) * 100));
});
</script>

<template>
  <div class="progress-track">
    <div class="progress-fill" :class="`tone-${tone}`" :style="{ width: `${ratio}%` }" />
  </div>
</template>

<style scoped>
.progress-track {
  position: relative;
  width: 100%;
  height: 0.9rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(245, 241, 230, 0.9);
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
}

.tone-healthy,
.tone-active,
.tone-pass {
  background: linear-gradient(90deg, rgba(143, 219, 80, 0.98), rgba(121, 198, 65, 0.98));
}

.tone-warning,
.tone-provisioning,
.tone-degraded,
.tone-slow {
  background: linear-gradient(90deg, rgba(226, 176, 67, 0.98), rgba(199, 151, 46, 0.98));
}

.tone-running {
  background: linear-gradient(90deg, rgba(125, 171, 255, 0.98), rgba(90, 138, 233, 0.98));
}

.tone-pending,
.tone-waiting,
.tone-neutral {
  background: linear-gradient(90deg, rgba(164, 160, 153, 0.96), rgba(124, 121, 116, 0.96));
}
</style>

