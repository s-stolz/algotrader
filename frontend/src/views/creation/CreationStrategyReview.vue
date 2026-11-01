<template>
  <BasePopover
    v-if="changed"
    trigger="hover"
    :show="open"
  >
    <template #trigger>
      <button
        type="button"
        class="version-info"
        data-testid="reuse-version-review"
        :aria-label="note"
        @mouseenter="open = true"
        @mouseleave="open = false"
        @focus="open = true"
        @blur="open = false"
        @click.prevent="open = true"
        @keydown.esc="open = false"
        >!</button
      >
    </template>
    {{ note }}
  </BasePopover>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue';
import BasePopover from '@/components/Common/BasePopover.vue';
import { useCreation } from './creationContext';
const open = ref(false);
const { store, selectedStrategy } = useCreation();
const changed = computed(
  () =>
    store.reuseSource &&
    selectedStrategy.value &&
    store.reuseSource.strategyId === selectedStrategy.value.strategy_id &&
    store.reuseSource.strategyVersion !==
      selectedStrategy.value.strategy_version,
);
const note = computed(() => {
  const saved = store.reuseSource?.strategyVersion;
  const current = selectedStrategy.value?.strategy_version;
  if (saved == null)
    return `The copied strategy version is unknown. Now using v${current}.`;
  return `Copied from v${saved}. Now using v${current} because v${saved} is unavailable.`;
});
</script>
<style scoped>
.version-info {
  width: 20px;
  height: 20px;
  padding: 0;
  border: 1px solid currentColor;
  border-radius: var(--design-radius-circle);
  background: transparent;
  color: var(--design-color-warning);
  font: inherit;
  font-size: var(--design-text-secondary);
  cursor: help;
}
.version-info:focus-visible {
  outline: 2px solid var(--design-color-interactive);
  outline-offset: 2px;
}
</style>
