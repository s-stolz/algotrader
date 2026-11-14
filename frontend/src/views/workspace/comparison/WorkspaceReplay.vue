<template>
  <p
    v-if="compatibilityDifferences.length"
    data-testid="comparison-compatibility"
    role="note"
  >
    Compared runs differ in {{ compatibilityDifferences.join(', ') }}. Interpret
    their results in context.
  </p>
  <div
    v-if="selectedComparisonIds.length > 0"
    class="curve-inspection"
  >
    <ReplayLoading v-if="pendingReplayCount && !chartSeries.length" />
    <BaseAsyncState
      v-for="id in curveStatusIds"
      :key="id"
      :data-testid="`curve-status-${id}`"
      :compact="!!chartSeries.length"
      :kind="analysis[id]?.error ? 'error' : 'info'"
      :label="`${analysisRunName(id)} replay`"
      :message="
        analysis[id]?.error
          ? `${analysisRunName(id)} · Couldn’t load replay.`
          : `${analysisRunName(id)} · ${equityUnavailableReason(analysis[id]?.curve?.reason)}`
      "
      retry
      @retry="inspection.retryAnalysis(id)"
    />
    <EquityReplayCharts
      v-if="chartSeries.length"
      :series="chartSeries"
      :sampled="hasSampledCurve"
      :loading="pendingReplayCount > 0"
    />
  </div>
</template>
<script setup lang="ts">
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';
import ReplayLoading from './ReplayLoading.vue';

import EquityReplayCharts from '@/views/EquityReplayCharts.vue';
import { equityUnavailableReason } from '@/views/backtestWorkspaceRuns';
import { workspaceReplay } from '@/views/workspace/comparison/workspaceReplay';
import type { BacktestWorkspace } from '@/views/workspace/useBacktestWorkspace';
const props = defineProps<{ inspection: BacktestWorkspace['inspection'] }>();
const { selectedComparisonIds, analysis } = props.inspection;
const {
  pendingReplayCount,
  compatibilityDifferences,
  curveStatusIds,
  hasSampledCurve,
  chartSeries,
  analysisRunName,
} = workspaceReplay(props.inspection);
</script>
<style scoped>
.curve-inspection {
  width: 100%;
  margin-top: var(--design-space-xl);
}
</style>
