<template>
  <p
    v-if="compatibilityDifferences.length"
    data-testid="comparison-compatibility"
    role="note"
  >
    Compared runs differ in {{ compatibilityDifferences.join(', ') }}. Interpret
    their results in context.
  </p>
  <p
    v-if="selectedComparisonIds.length === 0"
    role="status"
  >
    Select successful runs to inspect exact equity and drawdown.
  </p>
  <div
    v-else
    class="curve-inspection"
  >
    <ul
      v-if="curveStatusIds.length"
      class="curve-status"
    >
      <li
        v-for="id in curveStatusIds"
        :key="id"
        :data-testid="`curve-status-${id}`"
      >
        {{ analysisRunName(id) }}:
        <template v-if="analysis[id]?.error"
          >Exact Equity Replay read failed: {{ analysis[id]?.error }}. Saved
          metrics remain available.</template
        >
        <template
          v-else-if="analysis[id]?.curve?.availability === 'unavailable'"
          >Exact Equity Replay unavailable:
          {{ equityUnavailableReason(analysis[id]?.curve?.reason) }}. Saved
          metrics remain available.</template
        >
      </li>
    </ul>
    <EquityReplayCharts
      v-if="chartSeries.length"
      :series="chartSeries"
      :sampled="hasSampledCurve"
    />
  </div>
</template>
<script setup lang="ts">
import EquityReplayCharts from '../../EquityReplayCharts.vue';
import { equityUnavailableReason } from '../../backtestWorkspaceRuns';
import { workspaceReplay } from './workspaceReplay';
import type { BacktestWorkspace } from '../useBacktestWorkspace';
const props = defineProps<{ inspection: BacktestWorkspace['inspection'] }>();
const { selectedComparisonIds, analysis } = props.inspection;
const {
  compatibilityDifferences,
  curveStatusIds,
  hasSampledCurve,
  chartSeries,
  analysisRunName,
} = workspaceReplay(props.inspection);
</script>
<style scoped>
.curve-status {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: var(--design-space-sm) var(--design-space-xl);
  padding: 0;
  font-size: var(--design-text-secondary);
  color: var(--design-color-muted);
}
.curve-inspection {
  width: 100%;
  margin-top: var(--design-space-xl);
}
</style>
