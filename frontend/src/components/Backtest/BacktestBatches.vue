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
  margin-bottom: 20px;
  color: #e3eaf0;
  font-size: 13px;
}
.batch-detail {
  background: var(--surface-panel);
  border: 1px solid var(--surface-border);
  border-radius: 14px;
  overflow: hidden;
}
.sweep-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
  padding: 24px 28px;
}
.eyebrow {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #9db1c2;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1.5px;
}
.eyebrow span {
  color: #98aaba;
  font:
    11px ui-monospace,
    monospace;
  letter-spacing: 0;
}
h3 {
  margin: 6px 0;
  font-size: 23px;
  line-height: 1.3;
  font-weight: 600;
}
p {
  margin: 0;
}
.context {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #a8b8c6;
}
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid #47627b;
  border-radius: 20px;
  padding: 6px 11px;
  font-size: 12px;
  color: #aecff3;
  background: #203347;
}
.status-dot {
  display: inline-block;
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.status-badge.completed {
  color: #91e0c1;
  border-color: #385e53;
  background: #203b34;
}
.status-badge.pausing,
.status-badge.paused,
.status-badge.cancelling,
.status-badge.unknown {
  color: #edc791;
  border-color: #645539;
  background: #383124;
}
.status-badge.cancelled {
  color: #b5c0cc;
  border-color: #4a5562;
  background: #2a323c;
}
.elapsed {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  white-space: nowrap;
  color: #9fb2c2;
  font-size: 12px;
}
.elapsed strong {
  color: #d9e5ed;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.notice {
  margin: 12px 28px;
  padding: 11px 14px;
  border: 1px solid #415266;
  border-radius: 7px;
  line-height: 1.6;
}
.notice.error {
  color: #ffc0c4;
  background: #342830;
  border-color: #67454d;
}
.notice.warning {
  color: #e9c797;
  background: #302c25;
  border-color: #534934;
}
.loading {
  padding: 24px;
  color: #acbdca;
}
@media (max-width: 600px) {
  .sweep-header {
    padding: 18px;
  }
  .notice {
    margin: 12px 18px;
  }
}
</style>
