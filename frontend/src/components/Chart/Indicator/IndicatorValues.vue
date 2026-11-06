<template>
  <div
    class="indicator-values"
    :aria-label="`${indicator.info.name} values`"
  >
    <span
      v-for="output in outputs"
      :key="output.key"
      class="indicator-value"
      :style="{ color: readout?.[output.key]?.color ?? output.color }"
    >
      <span v-if="outputs.length > 1">{{ output.label }}: </span>
      {{ readout?.[output.key]?.text ?? '—' }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { IndicatorInstance } from './types';
import { getReadoutOutputs, type IndicatorReadout } from './indicatorReadout';

const props = defineProps<{
  indicator: IndicatorInstance;
  readout?: IndicatorReadout;
}>();
const outputs = computed(() => getReadoutOutputs(props.indicator));
</script>

<style scoped>
.indicator-values {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--design-space-xs) var(--design-space-md);
  min-width: 0;
  flex: 1 1 12rem;
  font-size: var(--design-text-secondary);
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}

.indicator-value {
  overflow-wrap: anywhere;
}
</style>
