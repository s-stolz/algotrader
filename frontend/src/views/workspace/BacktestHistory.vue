<template>
  <section
    class="history-page"
    aria-label="Saved Backtest Runs"
  >
    <div class="workspace-summary">
      <div
        ><span>Saved experiments</span
        ><strong>{{ historyRows.length }}</strong></div
      >
      <div
        ><span>In progress</span><strong>{{ activeHistoryCount }}</strong></div
      >
      <div
        ><span>Completed</span><strong>{{ completedHistoryCount }}</strong></div
      >
      <div
        ><span>With failed runs</span
        ><strong class="failure-count">{{ failedHistoryCount }}</strong></div
      >
    </div>
    <div class="table-panel">
      <div class="section-heading history-heading">
        <div>
          <div class="history-title">
            <h2>Experiment history</h2>
            <n-tag
              :bordered="false"
              size="small"
              >{{ filteredHistory.length }} experiments</n-tag
            >
          </div>
          <p>Open a backtest to explore its configuration and performance.</p>
        </div>
        <n-button
          v-if="canCreate"
          type="primary"
          data-testid="workspace-create"
          @click="actions.create"
        >
          <template #icon><n-icon :component="AddOutline" /></template>Create
          Backtest
        </n-button>
      </div>
      <BacktestHistoryFilters :history="history" />

      <p
        v-if="isLoading"
        role="status"
        >Loading saved runs…</p
      >

      <p
        v-if="
          runs !== null &&
          batches !== null &&
          historyRows.length === 0 &&
          !readError
        "
        role="status"
      >
        No saved Backtest Runs or Batches.
      </p>
      <p
        v-else-if="
          runs !== null &&
          batches !== null &&
          filteredHistory.length === 0 &&
          !readError
        "
        role="status"
      >
        No Backtest Runs or Batches match these filters.
      </p>

      <BaseDataTable
        v-if="runs !== null && batches !== null"
        data-testid="workspace-history"
        :columns="historyColumns"
        :data="filteredHistory"
        :row-key="rowKey"
        :row-props="historyRowProps"
        :pagination="historyPagination"
        :scroll-x="1470"
        :max-height="540"
        size="medium"
        striped
      />
    </div>
  </section>
</template>
<script setup lang="ts">
import { NButton, NIcon, NTag } from 'naive-ui';
import { AddOutline } from '@vicons/ionicons5';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import BacktestHistoryFilters from './BacktestHistoryFilters.vue';
import { createHistoryColumns } from './backtestHistoryColumns';
import { rowKey } from './backtestHistoryRows';
import type { BacktestWorkspace } from './useBacktestWorkspace';
const props = defineProps<{
  history: BacktestWorkspace['history'];
  actions: BacktestWorkspace['historyActions'];
  canCreate: boolean;
}>();
const {
  runs,
  batches,
  isLoading,
  readError,
  historyRows,
  activeHistoryCount,
  completedHistoryCount,
  failedHistoryCount,
  filteredHistory,
  historyPagination,
} = props.history;
const historyColumns = createHistoryColumns(props.actions);
const historyRowProps = props.actions.rowProps;
</script>
<style scoped>
.workspace-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin: 24px 0;
}
.workspace-summary > div {
  padding: 18px 22px;
  border: 1px solid var(--surface-border);
  border-radius: 10px;
  background: var(--surface-panel);
}
.workspace-summary span {
  display: block;
  color: #96a5b4;
  font-size: 12px;
}
.workspace-summary strong {
  display: block;
  margin-top: 8px;
  font-size: 27px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.failure-count {
  color: #e7ae7b;
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
.history-heading {
  margin-bottom: 22px;
  flex-wrap: wrap;
}
.history-heading > .n-button {
  flex-shrink: 0;
}
.history-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
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
@media (max-width: 700px) {
  .workspace-summary {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  .table-panel {
    padding: 14px;
  }
  .section-heading {
    align-items: flex-start;
  }
}
</style>
