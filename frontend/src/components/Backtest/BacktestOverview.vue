<template>
  <section
    v-if="backtestId"
    aria-label="Backtest"
    class="backtest-history"
  >
    <div
      v-if="!selectedBacktest || detailError"
      class="backtest-detail"
    >
      <BaseAsyncState
        :kind="detailError ? 'error' : 'loading'"
        :label="detailError ? 'Backtest unavailable' : 'Loading backtest'"
        :message="
          selectedBacktest
            ? 'Couldn’t refresh this backtest. Showing saved data.'
            : 'Couldn’t load this backtest.'
        "
        :retry="!!detailError"
        :retrying="inspection.membersPending.value"
        @retry="inspection.refresh()"
      />
    </div>
    <section
      v-if="selectedBacktest"
      aria-label="Accepted Backtest"
      class="backtest-detail"
    >
      <header class="backtest-header">
        <div class="title-row">
          <h3
            ><ExperimentName
              :experiment-id="selectedBacktest.backtest_id"
              :name="selectedBacktest.name"
          /></h3>
          <n-tag
            size="small"
            round
            :bordered="false"
            >Version
            {{ selectedBacktest.strategy_metadata.strategy_version }}</n-tag
          >
        </div>
        <div class="header-actions">
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

      <BacktestProgress
        v-if="!isTerminal"
        :inspection="inspection"
      />
      <BaseAsyncState
        v-if="controlPending || controlError"
        compact
        :kind="controlPending ? 'loading' : 'error'"
        label="Backtest action"
        message="Couldn’t update this backtest."
        :retry="!!controlError"
        @retry="inspection.retryControl()"
      />
      <BacktestSavedDetails :inspection="inspection" />
    </section>
  </section>
</template>

<script setup lang="ts">
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';

import { watch } from 'vue';
import { NButton, NIcon, NTag } from 'naive-ui';
import { PauseOutline, PlayOutline } from '@vicons/ionicons5';
import type { Backtest, BacktestRun } from '@/types/backtesterContracts';
import ExperimentName from '@/components/Backtest/ExperimentName.vue';
import BacktestProgress from '@/components/Backtest/inspection/BacktestProgress.vue';
import BacktestSavedDetails from '@/components/Backtest/inspection/BacktestSavedDetails.vue';
import { useBacktestInspection } from '@/components/Backtest/inspection/useBacktestInspection';
const emit = defineEmits<{
  members: [backtestId: string, runs: BacktestRun[]];
  'runs-state': [backtestId: string, state: 'loading' | 'error' | 'ready'];
  'heatmap-state': [
    backtestId: string,
    snapshot: { backtest: Backtest; runs: BacktestRun[] } | null,
    pending: boolean,
    error: string | null,
  ];
  cancelled: [];
  unavailable: [backtestId: string];
}>();
const props = defineProps<{ backtestId: string | null }>();
const inspection = useBacktestInspection(props, {
  members: (backtestId, runs) => emit('members', backtestId, runs),
  cancelled: () => emit('cancelled'),
  unavailable: (backtestId) => emit('unavailable', backtestId),
});
defineExpose({ refresh: inspection.refresh });
watch(
  [
    () => props.backtestId,
    inspection.terminalSnapshot,
    inspection.membersPending,
    inspection.membersError,
  ],
  ([id]) => {
    if (id)
      emit(
        'heatmap-state',
        id,
        inspection.terminalSnapshot.value,
        inspection.membersPending.value,
        inspection.membersError.value,
      );
  },
  { immediate: true },
);
watch(
  [
    () => props.backtestId,
    inspection.members,
    inspection.membersError,
    inspection.membersPending,
  ],
  ([id]) => {
    if (!id) return;
    const state =
      inspection.membersPending.value && !inspection.members.value?.length
        ? 'loading'
        : inspection.membersError.value
          ? 'error'
          : inspection.members.value
            ? 'ready'
            : 'loading';
    emit('runs-state', id, state);
  },
  { immediate: true },
);
const {
  selectedBacktest,
  detailError,
  controlPending,
  controlError,
  isTerminal,
  statusLabel,
  canControl,
  canPause,
  control,
} = inspection;
</script>
<style scoped>
.title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
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
h3 {
  margin: var(--design-space-sm) 0;
  font-size: var(--design-text-heading);
  line-height: 1.3;
  font-weight: 600;
}
p {
  margin: 0;
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
  color: var(--design-color-warning);
  border-color: var(--design-color-warning);
  background: color-mix(
    in srgb,
    var(--design-color-warning) 12%,
    var(--design-color-inset)
  );
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
