<template>
  <section
    class="run-progress"
    :aria-label="`Run #${ordinal} progress`"
  >
    <div
      class="milestone-track"
      role="progressbar"
      :aria-label="`Run #${ordinal}: execution stages`"
      :aria-valuenow="stageIndex"
      :aria-valuemin="0"
      :aria-valuemax="stages.length"
      :aria-valuetext="
        hasCounts
          ? `${processedCandles} of ${totalCandles} candles processed`
          : `${stageIndex} of ${stages.length} stages complete`
      "
    >
      <span
        class="milestone-fill"
        :style="{ width: `${fillPercent}%` }"
      />
      <span
        v-for="(item, index) in stages"
        :key="item.key"
        class="milestone-dot"
        :class="{ complete: index < stageIndex, current: index === stageIndex }"
        :style="{ left: `${(index / (stages.length - 1)) * 100}%` }"
        aria-hidden="true"
      />
    </div>
    <ol
      class="milestone-labels"
      aria-label="Execution stages"
    >
      <li
        v-for="(item, index) in stages"
        :key="item.key"
        :class="{ complete: index < stageIndex, current: index === stageIndex }"
        :aria-current="index === stageIndex ? 'step' : undefined"
        :style="{ left: `${(index / (stages.length - 1)) * 100}%` }"
      >
        {{ item.label }}
        <span
          v-if="item.key === 'simulating' && hasCounts"
          class="candle-count"
        >
          {{ processedCandles?.toLocaleString() }} /
          {{ totalCandles?.toLocaleString() }}
        </span>
      </li>
    </ol>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue';
import {
  BACKTEST_PROGRESS_STAGES,
  type BacktestProgressStage,
} from '@/types/backtestEventContracts';
const props = defineProps<{
  ordinal: number;
  stage: BacktestProgressStage;
  processedCandles?: number;
  totalCandles?: number;
}>();
const hasCounts = computed(
  () =>
    props.stage === 'simulating' &&
    props.processedCandles !== undefined &&
    (props.totalCandles ?? 0) > 0,
);
const stageLabels: Record<BacktestProgressStage, string> = {
  loading_data: 'Loading data',
  preparing_indicators: 'Preparing indicators',
  simulating: 'Simulating',
  calculating_results: 'Calculating results',
  saving: 'Saving',
};
const stages = BACKTEST_PROGRESS_STAGES.map((key) => ({
  key,
  label: stageLabels[key],
}));
const stageIndex = computed(() =>
  BACKTEST_PROGRESS_STAGES.indexOf(props.stage),
);
// Stage-only runs retain milestone feedback; candle counts interpolate simulation.
const fillPercent = computed(() => {
  const position = hasCounts.value
    ? stageIndex.value +
      Math.min(1, props.processedCandles! / props.totalCandles!)
    : props.totalCandles !== undefined && stageIndex.value >= 3
      ? stageIndex.value
      : Math.max(0, stageIndex.value - 1);
  return (position / (stages.length - 1)) * 100;
});
</script>
<style scoped>
.run-progress {
  margin-top: var(--design-space-lg);
}
.candle-count {
  display: block;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.milestone-track {
  position: relative;
  height: 4px;
  border-radius: var(--design-radius-panel);
  background: var(--design-color-disabled);
}
.milestone-fill {
  display: block;
  height: 100%;
  background: var(--design-color-interactive);
  border-radius: inherit;
  transition: width 250ms ease;
}
.milestone-dot {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 10px;
  height: 10px;
  box-sizing: border-box;
  border: 2px solid var(--design-color-border);
  border-radius: 50%;
  background: var(--design-color-panel);
}
.milestone-dot.complete {
  background: var(--design-color-interactive);
  border-color: var(--design-color-interactive);
}
.milestone-dot.current {
  border-color: var(--design-color-interactive);
}
.milestone-labels {
  position: relative;
  min-height: 3em;
  list-style: none;
  margin: var(--design-space-md) 0 0;
  padding: 0;
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
  line-height: 1.4;
}
.milestone-labels li {
  position: absolute;
  width: 20%;
  max-width: 140px;
  transform: translateX(-50%);
  text-align: center;
  overflow-wrap: anywhere;
}
.milestone-labels li:first-child {
  transform: none;
  text-align: left;
}
.milestone-labels li:last-child {
  transform: translateX(-100%);
  text-align: right;
}
.milestone-labels .complete {
  color: var(--design-color-body);
}
.milestone-labels .current {
  color: var(--design-color-interactive);
}
@media (max-width: 600px) {
  .milestone-labels {
    font-size: var(--design-text-id);
  }
}
@media (prefers-reduced-motion: reduce) {
  .milestone-fill {
    transition: none;
  }
}
</style>
