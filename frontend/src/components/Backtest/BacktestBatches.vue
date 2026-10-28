<template>
  <section
    v-if="batchId"
    aria-label="Backtest Batch"
    class="batch-history"
  >
    <p
      v-if="detailError"
      class="notice error"
      role="alert"
    >
      Live status unavailable.
      {{
        selectedBatch
          ? 'Showing the last saved snapshot.'
          : 'Retrying automatically.'
      }}
      {{ detailError }}
    </p>
    <p
      v-if="!selectedBatch && !detailError"
      class="loading"
      role="status"
      >Loading parameter sweep…</p
    >
    <section
      v-if="selectedBatch"
      aria-label="Accepted Batch"
      class="batch-detail"
    >
      <header class="sweep-header">
        <div>
          <div class="eyebrow">PARAMETER SWEEP</div>
          <h3
            ><ExperimentName
              kind="batch"
              :experiment-id="selectedBatch.batch_id"
              :name="selectedBatch.name"
          /></h3>
          <p class="context"
            >Version {{ selectedBatch.strategy_metadata.strategy_version }}
            <span aria-hidden="true">·</span>
            {{ selectedBatch.markets.join(', ') }}
            <span aria-hidden="true">·</span>
            {{ selectedBatch.timeframes.join(', ') }}</p
          >
        </div>
        <div class="header-actions">
          <div
            v-if="selectedBatch.started_at_ms !== null"
            class="elapsed"
          >
            <span>{{ isTerminal ? 'Total time' : 'Time since start' }}</span
            ><strong>{{ elapsed }}</strong>
          </div>
          <span
            class="status-badge"
            :class="detailError ? 'unknown' : selectedBatch.status"
            role="status"
          >
            <span class="status-dot" />{{
              detailError ? 'Status unknown' : statusLabel
            }}
          </span>
          <template v-if="canControl">
            <n-button
              size="small"
              :disabled="controlPending"
              @click="control(canPause ? 'pause' : 'resume')"
            >
              <template #icon
                ><n-icon :component="canPause ? PauseOutline : PlayOutline"
              /></template>
              {{ canPause ? 'Pause Batch' : 'Resume Batch' }}
            </n-button>
            <n-button
              size="small"
              quaternary
              type="error"
              :disabled="controlPending"
              data-testid="workspace-cancel-batch"
              @click="control('cancel')"
              >Cancel Batch</n-button
            >
          </template>
        </div>
      </header>

      <BatchProgress :inspection="inspection" />
      <p
        v-if="selectedBatch.outcome_counts.failed > 0"
        class="notice warning"
        role="status"
      >
        {{ selectedBatch.outcome_counts.failed }} run{{
          selectedBatch.outcome_counts.failed === 1 ? '' : 's'
        }}
        failed. Successful results remain available in Results below.
      </p>
      <p
        v-if="controlPending"
        class="notice"
        role="status"
        >Applying batch command…</p
      >
      <p
        v-if="controlError"
        class="notice error"
        role="alert"
        >{{ controlError }}</p
      >
      <p
        v-if="members && members.length === 0"
        class="notice error"
        role="alert"
        >Accepted Batch has no members.</p
      >

      <BatchSavedDetails :inspection="inspection" />
    </section>
  </section>
</template>

<script setup lang="ts">
import { NButton, NIcon } from 'naive-ui';
import { PauseOutline, PlayOutline } from '@vicons/ionicons5';
import type { BacktestRun } from '@/types/backtesterContracts';
import ExperimentName from './ExperimentName.vue';
import BatchProgress from './batch/BatchProgress.vue';
import BatchSavedDetails from './batch/BatchSavedDetails.vue';
import { useBatchInspection } from './batch/useBatchInspection';
const emit = defineEmits<{
  members: [batchId: string, runs: BacktestRun[]];
  cancelled: [];
}>();
const props = defineProps<{ batchId: string | null }>();
const inspection = useBatchInspection(props, {
  members: (batchId, runs) => emit('members', batchId, runs),
  cancelled: () => emit('cancelled'),
});
const {
  selectedBatch,
  members,
  detailError,
  controlPending,
  controlError,
  isTerminal,
  elapsed,
  statusLabel,
  canControl,
  canPause,
  control,
} = inspection;
</script>
<style scoped>
.batch-history {
  margin-bottom: var(--design-space-xl);
  color: var(--design-color-body);
  font-size: var(--design-text-body);
}
.batch-detail {
  background: var(--design-color-panel);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  overflow: hidden;
}
.sweep-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--design-space-xl);
  padding: var(--design-space-xl) var(--design-space-xl);
}
.eyebrow {
  display: flex;
  align-items: center;
  gap: var(--design-space-md);
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
  font-weight: 600;
  letter-spacing: 1.5px;
}
.eyebrow span {
  color: var(--design-color-muted);
  font-size: var(--design-text-id);
  font-family: var(--design-font-mono);
  letter-spacing: 0;
}
h3 {
  margin: var(--design-space-sm) 0;
  font-size: var(--design-text-heading);
  line-height: 1.3;
  font-weight: 600;
}
p {
  margin: 0;
}
.context {
  display: flex;
  flex-wrap: wrap;
  gap: var(--design-space-sm);
  color: var(--design-color-muted);
}
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--design-space-sm);
  align-items: center;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--design-space-sm);
  border: 1px solid currentColor;
  border-radius: var(--design-radius-control);
  padding: var(--design-space-sm) var(--design-space-md);
  font-size: var(--design-text-secondary);
  color: var(--design-color-info);
  background: var(--design-color-inset);
}
.status-dot {
  display: inline-block;
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: var(--design-radius-circle);
  background: currentColor;
}
.status-badge.completed {
  color: var(--design-color-positive);
  border-color: var(--design-color-border);
  background: var(--design-color-inset);
}
.status-badge.pausing,
.status-badge.paused,
.status-badge.cancelling,
.status-badge.unknown {
  color: var(--design-color-warning);
  border-color: var(--design-color-border);
  background: var(--design-color-inset);
}
.status-badge.cancelled {
  color: var(--design-color-muted);
  border-color: var(--design-color-border);
  background: var(--design-color-inset);
}
.elapsed {
  display: inline-flex;
  align-items: baseline;
  gap: var(--design-space-sm);
  white-space: nowrap;
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
.elapsed strong {
  color: var(--design-color-body);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.notice {
  margin: var(--design-space-md) var(--design-space-xl);
  padding: var(--design-space-md) var(--design-space-lg);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  line-height: 1.6;
}
.notice.error {
  color: var(--design-color-error);
  background: var(--design-color-inset);
  border-color: var(--design-color-border);
}
.notice.warning {
  color: var(--design-color-warning);
  background: var(--design-color-inset);
  border-color: var(--design-color-border);
}
.loading {
  padding: var(--design-space-xl);
  color: var(--design-color-muted);
}
@media (max-width: 600px) {
  .sweep-header {
    padding: var(--design-space-lg);
  }
  .notice {
    margin: var(--design-space-md) var(--design-space-lg);
  }
}
</style>
