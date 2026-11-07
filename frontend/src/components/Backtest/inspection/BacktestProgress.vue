<template>
  <template v-if="selectedBacktest">
    <div class="progress-panel">
      <div class="progress-heading">
        <div
          ><strong
            >{{ selectedBacktest.settled_count }}
            <span>/ {{ selectedBacktest.total_count }}</span></strong
          ><span class="progress-label">runs settled</span></div
        >
        <span class="progress-percent"
          >{{ progressPercent }}<small>%</small></span
        >
      </div>
      <div
        class="progress-track"
        role="progressbar"
        aria-label="Settled runs"
        :aria-valuenow="selectedBacktest.settled_count"
        :aria-valuemin="0"
        :aria-valuemax="selectedBacktest.total_count"
        :aria-valuetext="
          `${selectedBacktest.settled_count} / ` +
          `${selectedBacktest.total_count} settled; ` +
          `${selectedBacktest.executed_count} executed`
        "
      >
        <span
          v-for="outcome in outcomes"
          :key="outcome.status"
          :class="outcome.status"
          :style="{
            width: `${(outcome.count / selectedBacktest.total_count) * 100}%`,
          }"
        />
      </div>
    </div>
  </template>
</template>
<script setup lang="ts">
import type { BacktestInspection } from './useBacktestInspection';
const props = defineProps<{ inspection: BacktestInspection }>();
const { selectedBacktest, progressPercent, outcomes } = props.inspection;
</script>
<style scoped>
.progress-panel {
  margin: 0 var(--design-space-xl) var(--design-space-lg);
}
.progress-heading {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--design-space-md);
  margin-bottom: var(--design-space-lg);
}
.progress-heading strong {
  font-size: var(--design-text-body);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.progress-heading strong span {
  font-size: var(--design-text-body);
  color: var(--design-color-muted);
  font-weight: 400;
}
.progress-label {
  margin-left: var(--design-space-md);
  color: var(--design-color-muted);
}
.progress-percent {
  color: var(--design-color-body);
  font-size: var(--design-text-body);
  font-variant-numeric: tabular-nums;
}
.progress-percent small {
  color: var(--design-color-muted);
  font-size: var(--design-text-body);
  margin-left: var(--design-space-xs);
}
.progress-track {
  height: 12px;
  display: flex;
  overflow: hidden;
  border-radius: var(--design-radius-panel);
  background: var(--design-color-disabled);
}
.progress-track span {
  transition: width 0.35s ease;
}
.progress-track .succeeded {
  background: var(--design-color-positive);
}
.progress-track .failed {
  background: var(--design-color-error);
}
.progress-track .cancelled {
  background: var(--design-color-muted);
}
.progress-track .running {
  background: repeating-linear-gradient(
    120deg,
    var(--design-color-info) 0,
    var(--design-color-info) 5px,
    var(--design-color-selected) 5px,
    var(--design-color-selected) 10px
  );
}
.progress-track .cancelling {
  background: var(--design-color-warning);
}
@media (prefers-reduced-motion: reduce) {
  .progress-track span {
    transition: none;
  }
}
@media (max-width: 600px) {
  .progress-panel {
    margin: 0 var(--design-space-lg) var(--design-space-lg);
  }
  .progress-label {
    display: block;
    margin: var(--design-space-xs) 0 0;
    font-size: var(--design-text-secondary);
  }
}
</style>
