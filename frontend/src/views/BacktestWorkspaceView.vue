<template>
  <n-config-provider :theme-overrides="workspaceTheme">
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
            data-testid="workspace-history-return"
            @click="backToHistory"
          >
            <template #icon><n-icon :component="ArrowBackOutline" /></template
            >All backtests
          </n-button>
        </nav>
        <n-button
          type="primary"
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
  </n-config-provider>
</template>

<script setup lang="ts">
import {
  NButton,
  NConfigProvider,
  NIcon,
  type GlobalThemeOverrides,
} from 'naive-ui';
import {
  ArrowBackOutline,
  AddOutline,
  RefreshOutline,
} from '@vicons/ionicons5';
import { baseSelectTheme } from '@/components/Common/baseSelectTheme';
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
const workspaceTheme: GlobalThemeOverrides = {
  common: {
    fontFamily:
      'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
  },
  Select: baseSelectTheme,
};
</script>
<style scoped>
.workspace {
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
  min-height: 100%;
  box-sizing: border-box;
  max-width: 1800px;
  margin: 0 auto;
  padding: 24px 30px 48px;
  color: #dce4ed;
}
.workspace :deep(*) {
  font-family: inherit;
}
.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 36px;
  margin-bottom: 20px;
}
.section-heading p {
  margin: 6px 0 0;
  color: #8f9dab;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.workspace-header > .n-button {
  flex-shrink: 0;
  margin-left: auto;
}
.analysis-breadcrumb {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  color: #8291a2;
  font-size: 12px;
}
.analysis-breadcrumb .n-button {
  color: #9aafbf;
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
  color: #8190a0;
  font-size: 10px;
  font-family: monospace;
  margin-top: 3px;
}
:deep(.row-actions) {
  display: flex;
  align-items: center;
  gap: 4px;
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
  color: #f0aaa2;
}
:deep(.positive-metric) {
  color: #7dd5b4;
}
:deep(.n-data-table-tr) {
  cursor: pointer;
}
@media (max-width: 700px) {
  .workspace-header {
    flex-wrap: wrap;
  }
  .workspace {
    padding: 16px 6px 32px;
  }
}
</style>
