<template>
  <p
    v-if="changed"
    class="version-note"
    data-testid="reuse-version-review"
  >
    Using current strategy v{{ selectedStrategy?.strategy_version }} (saved
    {{
      store.reuseSource?.strategyVersion == null
        ? 'version unknown'
        : `v${store.reuseSource.strategyVersion}`
    }}).
  </p>
</template>
<script setup lang="ts">
import { computed } from 'vue';
import { useCreation } from './creationContext';
const { store, selectedStrategy } = useCreation();
const changed = computed(
  () =>
    store.reuseSource &&
    selectedStrategy.value &&
    store.reuseSource.strategyId === selectedStrategy.value.strategy_id &&
    store.reuseSource.strategyVersion !==
      selectedStrategy.value.strategy_version,
);
</script>
<style scoped>
.version-note {
  margin: 0 0 var(--design-space-md);
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
</style>
