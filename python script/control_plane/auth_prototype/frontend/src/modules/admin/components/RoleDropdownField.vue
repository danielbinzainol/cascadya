<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import StatusBadge from "@/components/ui/StatusBadge.vue";
import { statusTone } from "@/mocks/controlPlane";
import type { RbacRoleCatalogEntry, RoleName } from "@/types/controlPlane";

const props = withDefaults(
  defineProps<{
    modelValue: RoleName[];
    options: RbacRoleCatalogEntry[];
    disabled?: boolean;
    placeholder?: string;
  }>(),
  {
    disabled: false,
    placeholder: "Choisir des roles",
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: RoleName[]): void;
}>();

const rootRef = ref<HTMLElement | null>(null);
const isOpen = ref(false);

const selectedSummary = computed(() => {
  if (props.modelValue.length === 0) {
    return props.placeholder;
  }
  if (props.modelValue.length <= 2) {
    return props.modelValue.join(", ");
  }
  return `${props.modelValue.length} roles selectionnes`;
});

function isSelected(roleName: RoleName) {
  return props.modelValue.includes(roleName);
}

function toggleOpen() {
  if (props.disabled) {
    return;
  }
  isOpen.value = !isOpen.value;
}

function toggleRole(roleName: RoleName) {
  if (props.disabled) {
    return;
  }
  const nextValues = isSelected(roleName)
    ? props.modelValue.filter((value) => value !== roleName)
    : [...props.modelValue, roleName];
  emit("update:modelValue", nextValues);
}

function handleDocumentClick(event: MouseEvent) {
  const rootElement = rootRef.value;
  if (!rootElement) {
    return;
  }
  if (event.target instanceof Node && !rootElement.contains(event.target)) {
    isOpen.value = false;
  }
}

onMounted(() => {
  document.addEventListener("click", handleDocumentClick);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleDocumentClick);
});
</script>

<template>
  <div ref="rootRef" class="dropdown-shell" :class="{ 'dropdown-shell-open': isOpen }">
    <button
      class="dropdown-trigger"
      type="button"
      :disabled="disabled"
      :aria-expanded="isOpen ? 'true' : 'false'"
      @click="toggleOpen"
    >
      <span class="dropdown-copy">
        <span class="dropdown-label">{{ selectedSummary }}</span>
        <span class="dropdown-meta">{{ modelValue.length }} role(s)</span>
      </span>
      <span class="dropdown-chevron">{{ isOpen ? "Fermer" : "Choisir" }}</span>
    </button>

    <div v-if="isOpen" class="dropdown-panel">
      <label
        v-for="role in options"
        :key="role.name"
        class="dropdown-option"
        :class="{ 'dropdown-option-selected': isSelected(role.name) }"
      >
        <input
          type="checkbox"
          :checked="isSelected(role.name)"
          :disabled="disabled"
          @change="toggleRole(role.name)"
        />
        <div class="dropdown-option-copy">
          <div class="dropdown-option-heading">
            <StatusBadge :label="role.name" :tone="statusTone(role.name)" compact />
            <span class="helper-text">{{ role.permissions.length }} permissions</span>
          </div>
          <p class="dropdown-description">{{ role.description }}</p>
        </div>
      </label>
    </div>
  </div>
</template>

<style scoped>
.dropdown-shell {
  position: relative;
}

.dropdown-trigger {
  width: 100%;
  min-height: 3rem;
  padding: 0.8rem 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  text-align: left;
  transition:
    border-color 150ms ease,
    background 150ms ease,
    transform 150ms ease;
}

.dropdown-trigger:hover:enabled,
.dropdown-shell-open .dropdown-trigger {
  border-color: rgba(122, 168, 255, 0.32);
  background: rgba(82, 117, 176, 0.14);
}

.dropdown-trigger:disabled {
  opacity: 0.55;
}

.dropdown-copy {
  min-width: 0;
  display: grid;
  gap: 0.15rem;
}

.dropdown-label {
  color: var(--text);
  font-weight: 600;
}

.dropdown-meta,
.dropdown-chevron {
  color: var(--muted);
  font-size: 0.86rem;
}

.dropdown-panel {
  position: absolute;
  z-index: 20;
  top: calc(100% + 0.45rem);
  left: 0;
  right: 0;
  display: grid;
  gap: 0.65rem;
  padding: 0.8rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(10, 12, 15, 0.98);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.35);
}

.dropdown-option {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.75rem;
  align-items: start;
  padding: 0.8rem 0.9rem;
  border-radius: 0.95rem;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.025);
}

.dropdown-option:hover {
  border-color: var(--line);
  background: rgba(255, 255, 255, 0.04);
}

.dropdown-option-selected {
  border-color: rgba(122, 168, 255, 0.28);
  background: rgba(82, 117, 176, 0.12);
}

.dropdown-option input {
  margin-top: 0.25rem;
}

.dropdown-option-copy {
  display: grid;
  gap: 0.35rem;
}

.dropdown-option-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem;
}

.dropdown-description {
  margin: 0;
  color: var(--text);
  line-height: 1.45;
}

.helper-text {
  color: var(--muted);
}
</style>
