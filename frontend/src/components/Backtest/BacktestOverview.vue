<template>
  <section
    v-if="backtestId"
    aria-label="Backtest"
    class="backtest-history"
  >
    <p
      v-if="detailError"
      class="notice error"
      role="alert"
    >
      Live status unavailable.
      {{
        selectedBacktest
          ? 'Showing the last saved snapshot.'
          : 'Retrying automatically.'
      }}
      {{ detailError }}
    </p>
    <p
      v-if="!selectedBacktest && !detailError"
      class="loading"
      role="status"
      >Loading backtest…</p
    >
    <section
      v-if="selectedBacktest"
      aria-label="Accepted Backtest"
      class="backtest-detail"
    >
      <header class="backtest-header">
        <div>
          <h3
            ><ExperimentName
              :experiment-id="selectedBacktest.backtest_id"
              :name="selectedBacktest.name"
          /></h3>
          <p class="context"
            >Version {{ selectedBacktest.strategy_metadata.strategy_version }}
            <span aria-hidden="true">·</span>
            {{ selectedBacktest.markets.join(', ') }}
            <span aria-hidden="true">·</span>
            {{ selectedBacktest.timeframes.join(', ') }}</p
          >
        </div>
        <div class="header-actions">
          <div
            v-if="selectedBacktest.started_at_ms !== null"
            class="elapsed"
          >
            <span>{{ isTerminal ? 'Total time' : 'Time since start' }}</span
            ><strong>{{ elapsed }}</strong>
          </div>
          <span
            class="status-badge"
            :class="detailError ? 'unknown' : selectedBacktest.status"
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
              {{ canPause ? 'Pause Backtest' : 'Resume Backtest' }}
            </n-button>
            <n-button
              size="small"
              quaternary
              type="error"
              :disabled="controlPending"
              data-testid="workspace-cancel-backtest"
              @click="control('cancel')"
              >Cancel Backtest</n-button
            >
          </template>
        </div>
      </header>

      <BacktestProgress :inspection="inspection" />
      <p
        v-if="selectedBacktest.outcome_counts.failed > 0"
        class="notice warning"
        role="status"
      >
        {{ selectedBacktest.outcome_counts.failed }} run{{
          selectedBacktest.outcome_counts.failed === 1 ? '' : 's'
        }}
        failed. Successful results remain available in Results below.
      </p>
      <p
        v-if="controlPending"
        class="notice"
        role="status"
        >Applying backtest command…</p
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
        >Accepted Backtest has no members.</p
      >

      <BacktestSavedDetails :inspection="inspection" />
    </section>
  </section>
</template>

<script setup lang="ts">
import { NButton, NIcon } from 'naive-ui';
import { PauseOutline, PlayOutline } from '@vicons/ionicons5';
import type { BacktestRun } from '@/types/backtesterContracts';
import ExperimentName from './ExperimentName.vue';
import BacktestProgress from './inspection/BacktestProgress.vue';
import BacktestSavedDetails from './inspection/BacktestSavedDetails.vue';
import { useBacktestInspection } from './inspection/useBacktestInspection';
const emit = defineEmits<{
  members: [backtestId: string, runs: BacktestRun[]];
  cancelled: [];
  unavailable: [backtestId: string];
}>();
const props = defineProps<{ backtestId: string | null }>();
const inspection = useBacktestInspection(props, {
  members: (backtestId, runs) => emit('members', backtestId, runs),
  cancelled: () => emit('cancelled'),
  unavailable: (backtestId) => emit('unavailable', backtestId),
});
const {
  selectedBacktest,
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
.backtest-history {
  margin-bottom: var(--design-space-xl);
  color: var(--design-color-body);
  font-size: var(--design-text-body);
}
.backtest-detail {
  background: var(--design-color-panel);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  overflow: hidden;
}
.backtest-header {
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
  .backtest-header {
    padding: var(--design-space-lg);
  }
  .notice {
    margin: var(--design-space-md) var(--design-space-lg);
  }
}
</style>
