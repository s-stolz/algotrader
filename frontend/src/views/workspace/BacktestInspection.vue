<template>
  <section
    v-show="page === 'analysis'"
    class="current-backtest"
    aria-label="Current Backtest"
  >
    <BacktestBatches
      :batch-id="selectedBatchId"
      @members="receiveMembers"
      @cancelled="refreshWorkspace"
    />
    <div class="table-panel">
      <div
        v-if="selectedRun && !selectedBatchId"
        class="run-heading"
      >
        <h2 class="strategy-name">
          <ExperimentName
            v-if="!selectedRun.batch_id"
            kind="run"
            :experiment-id="selectedRun.run_id"
            :name="selectedRun.name"
          />
          <template v-else>{{ runName(selectedRun) }}</template>
        </h2>
        <div class="analysis-context">
          <n-tag
            size="small"
            :bordered="false"
            >Standalone run</n-tag
          >
          <span>{{ strategyVersion(selectedRun) }}</span>
          <span>{{ runMarket(selectedRun) }}</span
          ><span>{{ selectedRun.request.timeframe }}</span>
          <span
            >{{ formatUtcDate(selectedRun.request.start_ms) }} —
            {{ formatUtcDate(selectedRun.request.end_ms) }} UTC</span
          >
          <n-tag
            size="small"
            :type="
              selectedRun.status === 'succeeded'
                ? 'success'
                : selectedRun.status === 'failed'
                  ? 'error'
                  : 'info'
            "
            :bordered="false"
            >{{ selectedRun.status }}</n-tag
          >
        </div>
      </div>
      <div
        v-else
        class="section-heading"
      >
        <h2>Results</h2>
      </div>
      <p v-if="!selectedRunId && !selectedBatchId"
        >Select a saved run or Batch to inspect its request and results.</p
      >
      <p
        v-if="detailError"
        role="alert"
        >{{ detailError }}</p
      >
      <p
        v-if="overlayStore.error"
        role="alert"
        >{{ overlayStore.error }}</p
      >
      <template v-if="currentRows.length">
        <BacktestComparison
          :inspection="workspace.inspection"
          :comparison="comparison"
        />
      </template>
      <template v-if="selectedRun">
        <p
          v-if="selectedRun.error_message"
          class="run-error"
        >
          {{ selectedRun.error_message }}
        </p>
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
import { NTag } from 'naive-ui';
import BacktestBatches from '@/components/Backtest/BacktestBatches.vue';
import ExperimentName from '@/components/Backtest/ExperimentName.vue';
import {
  formatUtcDate,
  runName,
  runMarket,
  strategyVersion,
} from '../backtestWorkspaceRuns';
import BacktestComparison from './comparison/BacktestComparison.vue';
import type { BacktestWorkspace } from './useBacktestWorkspace';
import type { WorkspaceComparison } from './comparison/useWorkspaceComparison';
const props = defineProps<{
  workspace: BacktestWorkspace;
  comparison: WorkspaceComparison;
}>();
const {
  page,
  selectedBatchId,
  selectedRunId,
  selectedRun,
  receiveMembers,
  refreshWorkspace,
  detailError,
  overlayStore,
} = props.workspace;
const { currentRows } = props.workspace.inspection;
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
.section-heading p {
  margin: var(--design-space-sm) 0 0;
  color: var(--design-color-muted);
  font-size: var(--design-text-body);
  overflow-wrap: anywhere;
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
.run-heading h2 {
  margin: 0 0 var(--design-space-md);
  font-size: var(--design-text-heading);
  font-weight: 600;
  letter-spacing: -0.3px;
  overflow-wrap: anywhere;
}
.strategy-name {
  text-transform: capitalize;
}
.analysis-context {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--design-space-md);
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
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
.run-error {
  color: var(--design-color-error);
  padding: var(--design-space-md) var(--design-space-lg);
  border-radius: var(--design-radius-panel);
  background: var(--design-color-inset);
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
