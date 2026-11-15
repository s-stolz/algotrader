<script setup lang="ts">
import type { ReplaySeries } from '../../backtestComparison';
defineProps<{
  series: ReplaySeries[];
  colorForRun: (run: ReplaySeries) => string;
}>();
</script>
<template>
  <ul
    class="series-legend"
    aria-label="Compared runs"
  >
    <li
      v-for="run in series"
      :key="run.runId"
      :title="run.name"
    >
      <span
        class="series-swatch"
        :style="{ background: colorForRun(run) }"
      />
      <span :class="{ 'series-id': run.ordinal == null }">{{
        run.ordinal == null ? run.runId.slice(0, 8) : `#${run.ordinal + 1}`
      }}</span>
    </li>
  </ul>
</template>
<style scoped>
.series-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--design-space-sm) var(--design-space-xl);
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: var(--design-text-secondary);
  color: var(--design-color-body);
}
.series-legend li {
  display: flex;
  align-items: center;
  gap: var(--design-space-sm);
}
.series-id {
  font-family: var(--design-font-mono);
  font-size: var(--design-text-id);
}
.series-swatch {
  width: 16px;
  height: 3px;
  border-radius: var(--design-radius-panel);
}
</style>
