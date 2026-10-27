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
            <dt>Run ID</dt><dd>{{ selectedRun.run_id }}</dd>
            <dt>Strategy parameters</dt>
            <dd>{{
              JSON.stringify(selectedRun.request.strategy.parameters)
            }}</dd>
            <dt>Engine</dt><dd>{{ selectedRun.request.engine }}</dd>
            <dt>Data granularity</dt
            ><dd>{{ selectedRun.request.data_granularity }}</dd>
            <dt>Allowed Directions</dt>
            <dd>{{ selectedRun.request.execution.allowed_directions }}</dd>
            <dt>Execution settings</dt>
            <dd>{{ JSON.stringify(selectedRun.request.execution) }}</dd>
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
  gap: 20px;
}
.section-heading p {
  margin: 6px 0 0;
  color: #8f9dab;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.table-panel {
  border: 1px solid var(--surface-border);
  border-radius: 12px;
  background: var(--surface-panel);
  padding: 22px;
  overflow: hidden;
}
.section-heading h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.current-backtest {
  margin-top: 24px;
}
.run-heading h2 {
  margin: 0 0 12px;
  font-size: 20px;
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
  gap: 12px;
  color: #9aafbf;
  font-size: 12px;
}
.request-details {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: var(--surface-inset);
}
.request-details summary {
  cursor: pointer;
  color: #b7c8d6;
}
.request-details dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 8px 20px;
  font-size: 12px;
}
.request-details dt {
  color: #8f9dab;
}
.request-details dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.run-error {
  color: #f1b1a8;
  padding: 12px 16px;
  border-radius: 6px;
  background: #35272b;
}
@media (max-width: 700px) {
  .table-panel {
    padding: 14px;
  }
  .section-heading {
    align-items: flex-start;
  }
}
</style>
