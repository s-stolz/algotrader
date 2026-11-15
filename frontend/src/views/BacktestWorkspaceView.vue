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
      :key="creationSession"
      v-model:show="creationOpen"
      @submitted="createdBacktest"
    />

    <BaseAsyncState
      v-if="deleteError || cancelError"
      kind="error"
      compact
      label="Action failed"
      message="Couldn’t complete this action."
      retry
      @retry="workspace.commands.retryFailedAction()"
    />
    <BaseAsyncState
      v-if="selectionNotice"
      kind="info"
      compact
      label="Selection changed"
      :message="selectionNotice"
    />

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
  </main>
</template>

<script setup lang="ts">
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';

import { NButton, NIcon } from 'naive-ui';
import ArrowBackOutline from '@vicons/ionicons5/es/ArrowBackOutline';
import AddOutline from '@vicons/ionicons5/es/AddOutline';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import BacktestHistory from '@/views/workspace/BacktestHistory.vue';
import BacktestInspection from '@/views/workspace/BacktestInspection.vue';
import { useBacktestWorkspace } from '@/views/workspace/useBacktestWorkspace';
import { useWorkspaceComparison } from '@/views/workspace/comparison/useWorkspaceComparison';
defineOptions({ name: 'BacktestWorkspaceView' });
const workspace = useBacktestWorkspace();
const comparison = useWorkspaceComparison(workspace);
const {
  creationOpen,
  creationSession,
  page,
  backToHistory,
  createdBacktest,
  selectionNotice,
} = workspace;
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
