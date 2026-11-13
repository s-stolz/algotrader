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
        <details class="request-details">
          <summary>Saved request and execution settings</summary>
          <dl>
            <dt>Run ID</dt
            ><dd class="technical-value">{{ selectedRun.run_id }}</dd>
            <dt>Strategy parameters</dt>
            <dd class="technical-value">{{
              JSON.stringify(selectedRun.request.strategy.parameters)
            }}</dd>
            <dt>Engine</dt><dd>{{ selectedRun.request.engine }}</dd>
            <dt>Data granularity</dt
            ><dd>{{ selectedRun.request.data_granularity }}</dd>
            <dt>Allowed Directions</dt>
            <dd>{{ selectedRun.request.execution.allowed_directions }}</dd>
            <dt>Daily schedule · UTC (start / last entry / exit)</dt>
            <dd>{{
              scheduleLabel(selectedRun.request.execution.daily_schedule)
            }}</dd>
            <dt>Execution settings</dt>
            <dd class="technical-value">{{
              JSON.stringify(selectedRun.request.execution)
            }}</dd>
            <dt>Submitted</dt
            ><dd>{{ formatTimestamp(selectedRun.submitted_at_ms) }}</dd>
            <dt>Started</dt
            ><dd>{{ formatTimestamp(selectedRun.started_at_ms) }}</dd>
            <dt>Completed</dt
            ><dd>{{ formatTimestamp(selectedRun.completed_at_ms) }}</dd>
          </dl>
        </details>
      </template>
    </div>
  </section>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue';
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';

import BacktestOverview from '@/components/Backtest/BacktestOverview.vue';
import { scheduleLabel } from '@/types/backtest/schedule';
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
function formatTimestamp(timestamp: number | null | undefined): string {
  return timestamp == null ? '—' : new Date(timestamp).toISOString();
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
.request-details {
  margin-top: var(--design-space-xl);
  padding: var(--design-space-lg);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  background: var(--design-color-inset);
}
.request-details summary {
  cursor: pointer;
  color: var(--design-color-body);
}
.request-details dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--design-space-sm) var(--design-space-xl);
  font-size: var(--design-text-secondary);
}
.request-details dt {
  color: var(--design-color-muted);
}
.request-details dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.technical-value {
  font-family: var(--design-font-mono);
  font-size: var(--design-text-id);
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
