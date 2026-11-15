<template>
  <section
    v-show="page === 'analysis'"
    class="current-backtest"
    aria-label="Current Backtest"
  >
    <BacktestOverview
      ref="overview"
      @runs-state="receiveRunsState"
      @heatmap-state="receiveHeatmapState"
      :backtest-id="selectedBacktestId"
      @members="receiveMembers"
      @cancelled="refreshWorkspace"
      @unavailable="redirectUnavailableBacktest"
    />
    <div
      v-if="selectedBacktestId"
      class="table-panel"
    >
      <div class="section-heading"><h2>Runs</h2></div>

      <BaseAsyncState
        v-if="runsState !== 'ready'"
        :kind="runsState"
        :label="runsState === 'loading' ? 'Loading runs' : 'Runs unavailable'"
        :message="heatmapReadError ?? 'Couldn’t load runs'"
        :retry="runsState === 'error'"
        @retry="overview?.refresh()"
      />
      <BaseAsyncState
        v-else-if="detailError || overlayStore.error"
        kind="error"
        compact
        label="Run unavailable"
        message="Couldn’t load this run."
        :retry="!!detailError"
        @retry="workspace.retrySelectedRun()"
      />
      <template v-if="currentRows.length">
        <BacktestComparison
          :inspection="workspace.inspection"
          :comparison="comparison"
        >
          <ParameterHeatmap
            v-if="heatmapSnapshot"
            :key="selectedBacktestId!"
            :saved="heatmapSnapshot"
            :pending="heatmapPending"
            :read-error="heatmapReadError"
            :selected-ids="workspace.inspection.selectedComparisonIds.value"
            @retry="overview?.refresh()"
            @inspect="inspectCell"
          />
        </BacktestComparison>
      </template>
      <template v-if="selectedRun">
        <BaseAsyncState
          v-if="selectedRun.error_message"
          kind="error"
          compact
          label="Run failed"
          :message="selectedRun.error_message"
        />
      </template>
    </div>
  </section>
</template>
<script setup lang="ts">
import { ref, shallowRef, watch, nextTick } from 'vue';
import ParameterHeatmap from './heatmap/ParameterHeatmap.vue';
import type { Backtest, BacktestRun } from '@/types/backtesterContracts';
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';

import BacktestOverview from '@/components/Backtest/BacktestOverview.vue';
import BacktestComparison from '@/views/workspace/comparison/BacktestComparison.vue';
import type { BacktestWorkspace } from '@/views/workspace/useBacktestWorkspace';
import type { WorkspaceComparison } from '@/views/workspace/comparison/useWorkspaceComparison';
const props = defineProps<{
  workspace: BacktestWorkspace;
  comparison: WorkspaceComparison;
}>();
const {
  page,
  selectedBacktestId,
  selectedRun,
  receiveMembers,
  refreshWorkspace,
  redirectUnavailableBacktest,
  detailError,
  overlayStore,
} = props.workspace;
const { currentRows } = props.workspace.inspection;
const overview = ref<InstanceType<typeof BacktestOverview> | null>(null);
const heatmapSnapshot = shallowRef<{
  backtest: Backtest;
  runs: BacktestRun[];
} | null>(null);
const heatmapPending = ref(false);
const heatmapReadError = ref<string | null>(null);
function receiveHeatmapState(
  id: string,
  snapshot: typeof heatmapSnapshot.value,
  pending: boolean,
  error: string | null,
) {
  if (id !== selectedBacktestId.value) return;
  heatmapSnapshot.value = snapshot;
  heatmapPending.value = pending;
  heatmapReadError.value = error;
}
async function inspectCell(run: BacktestRun) {
  if (run.status !== 'succeeded') {
    props.workspace.selectRun(run);
    return;
  }
  const adding =
    !props.workspace.inspection.selectedComparisonIds.value.includes(
      run.run_id,
    );
  props.workspace.inspection.toggleComparison(run);
  if (adding) {
    await nextTick();
    document
      .querySelector('[data-testid="workspace-analysis"]')
      ?.scrollIntoView?.({
        behavior: 'smooth',
        block: 'nearest',
      });
  }
}
const runsState = ref<'loading' | 'error' | 'ready'>('loading');
watch(
  selectedBacktestId,
  () => {
    runsState.value = 'loading';
    heatmapSnapshot.value = null;
    heatmapReadError.value = null;
  },
  { flush: 'sync' },
);
function receiveRunsState(id: string, state: 'loading' | 'error' | 'ready') {
  if (id === selectedBacktestId.value) runsState.value = state;
}
</script>
<style scoped>
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--design-space-xl);
}
.table-panel {
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  background: var(--design-color-panel);
  padding: var(--design-space-xl);
  overflow: hidden;
}
.section-heading h2 {
  margin: 0;
  font-size: var(--design-text-heading);
  font-weight: 600;
}
.current-backtest {
  margin-top: var(--design-space-xl);
}
@media (max-width: 700px) {
  .table-panel {
    padding: var(--design-space-lg);
  }
  .section-heading {
    align-items: flex-start;
  }
}
</style>
