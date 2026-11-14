<template>
  <section
    v-show="page === 'analysis'"
    class="current-backtest"
    aria-label="Current Backtest"
  >
    <BacktestOverview
      ref="overview"
      @runs-state="receiveRunsState"
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
        message="Couldn’t load runs"
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
        />
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
import { ref, watch } from 'vue';
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
const runsState = ref<'loading' | 'error' | 'ready'>('loading');
watch(
  selectedBacktestId,
  () => {
    runsState.value = 'loading';
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
