<script setup lang="ts">
const props = defineProps<{
  values: number[];
  warning?: boolean;
}>();
</script>

<template>
  <div class="sparkline">
    <span
      v-for="(value, index) in props.values"
      :key="index"
      class="spark"
      :class="{ warning: props.warning }"
      :style="{ height: `${10 + value * 4}px` }"
    />
  </div>
</template>

<style scoped>
.sparkline {
  display: flex;
  align-items: end;
  gap: 0.32rem;
  min-height: 2.6rem;
}

.spark {
  width: 0.58rem;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(158, 226, 88, 1), rgba(113, 186, 52, 1));
}

.spark.warning {
  background: linear-gradient(180deg, rgba(228, 181, 77, 1), rgba(184, 136, 36, 1));
}
</style>
