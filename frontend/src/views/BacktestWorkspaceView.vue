<template>
  <main class="workspace">
    <header
      v-if="page === 'analysis'"
      class="workspace-header"
    >
      <nav
        class="analysis-breadcrumb"
        aria-label="Backtest location"
      >
        <n-button
          text
          class="history-return"
          data-testid="workspace-history-return"
          @click="backToHistory"
        >
          <template #icon><n-icon :component="ArrowBackOutline" /></template>All
          backtests
        </n-button>
      </nav>
      <n-button
        type="primary"
        class="workspace-create"
        data-testid="workspace-create"
        @click="creationOpen = true"
      >
        <template #icon><n-icon :component="AddOutline" /></template>Create
        Backtest
      </n-button>
    </header>

    <BacktestCreationDrawer
      v-model:show="creationOpen"
      @submitted="createdRun"
      @submitted-batch="createdBatch"
    />

    <BacktestQueueHealth ref="queueHealth" />
    <p
      v-if="readError"
      role="alert"
    >
      Run history unavailable; current lifecycle status is unknown.
      {{ readError }}
      <n-button
        data-testid="workspace-refresh"
        size="small"
        quaternary
        :loading="isRefreshing"
        @click="refreshWorkspace"
      >
        <template #icon><n-icon :component="RefreshOutline" /></template>Retry
        now
      </n-button>
    </p>
    <p
      v-if="deleteError"
      role="alert"
      >{{ deleteError }}</p
    >
    <p
      v-if="selectionNotice"
      role="status"
      >{{ selectionNotice }}</p
    >
    <p
      v-if="cancelError"
      role="alert"
      >{{ cancelError }}</p
    >

    <BacktestHistory
      v-show="page === 'history'"
      :history="workspace.history"
      :actions="workspace.historyActions"
      :can-create="page === 'history'"
    />

    <BacktestInspection
      :workspace="workspace"
      :comparison="comparison"
    />
    <ExecutionLogDrawer
      v-if="logRun"
      :run="logRun"
      :show="logRun !== null"
      @close="logRun = null"
    />
  </main>
</template>

<script setup lang="ts">
import { NButton, NIcon } from 'naive-ui';
import {
  ArrowBackOutline,
  AddOutline,
  RefreshOutline,
} from '@vicons/ionicons5';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';
import ExecutionLogDrawer from '@/components/Backtest/ExecutionLogDrawer.vue';
import BacktestCreationDrawer from './BacktestCreationDrawer.vue';
import BacktestHistory from './workspace/BacktestHistory.vue';
import BacktestInspection from './workspace/BacktestInspection.vue';
import { useBacktestWorkspace } from './workspace/useBacktestWorkspace';
import { useWorkspaceComparison } from './workspace/comparison/useWorkspaceComparison';
defineOptions({ name: 'BacktestWorkspaceView' });
const workspace = useBacktestWorkspace();
const comparison = useWorkspaceComparison(workspace);
const {
  creationOpen,
  page,
  queueHealth,
  logRun,
  backToHistory,
  refreshWorkspace,
  createdRun,
  createdBatch,
  selectionNotice,
} = workspace;
const { isRefreshing, readError } = workspace.history;
const { cancelError, deleteError } = workspace.commands;
</script>
<style scoped>
.workspace {
  font-family: var(--design-font-ui);
  font-size: var(--design-text-body);
  min-height: 100%;
  box-sizing: border-box;
  max-width: 1800px;
  margin: 0 auto;
  padding: var(--design-space-xl) var(--design-space-xxl)
    var(--design-space-xxl);
  color: var(--design-color-body);
}
.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--design-space-xl);
  min-height: 36px;
  margin-bottom: var(--design-space-xl);
}
.section-heading p {
  margin: var(--design-space-sm) 0 0;
  color: var(--design-color-muted);
  font-size: var(--design-text-body);
  overflow-wrap: anywhere;
}
.workspace-create {
  flex-shrink: 0;
  margin-left: auto;
}
.analysis-breadcrumb {
  display: flex;
  align-items: center;
  gap: var(--design-space-lg);
  min-width: 0;
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
.history-return {
  color: var(--design-color-muted);
}
:deep(.run-identity) {
  min-width: 0;
  font-weight: 500;
}
:deep(.run-status-icon) {
  display: inline-flex;
  vertical-align: middle;
}
:deep(.run-identity small) {
  display: block;
  color: var(--design-color-muted);
  font-size: var(--design-text-id);
  font-family: var(--design-font-mono);
  margin-top: var(--design-space-xs);
}
:deep(.row-actions) {
  display: flex;
  align-items: center;
  gap: var(--design-space-xs);
}
:deep(.run-chart-action) {
  display: inline-flex;
  align-items: center;
}
:deep(.run-log-action) {
  display: inline-flex;
  align-items: center;
}
:deep(.unavailable-log-icon) {
  position: relative;
}
:deep(.unavailable-log-icon::after) {
  content: '';
  position: absolute;
  top: 50%;
  left: -2px;
  width: 20px;
  height: 1.5px;
  background: currentColor;
  transform: rotate(-45deg);
  pointer-events: none;
}
:deep(.negative-metric) {
  color: var(--design-color-negative);
}
:deep(.positive-metric) {
  color: var(--design-color-positive);
}
@media (max-width: 700px) {
  .workspace-header {
    flex-wrap: wrap;
  }
  .workspace {
    padding: var(--design-space-lg) var(--design-space-sm)
      var(--design-space-xxl);
  }
}
</style>
