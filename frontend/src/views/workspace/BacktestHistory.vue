<template>
  <section
    class="history-page"
    aria-label="Saved Backtest Runs"
  >
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
        </div>
        <n-button
          v-if="canCreate"
          class="history-create"
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
        v-if="backtests !== null && historyRows.length === 0 && !readError"
        role="status"
      >
        No saved Backtests.
      </p>
      <p
        v-else-if="
          backtests !== null && filteredHistory.length === 0 && !readError
        "
        role="status"
      >
        No Backtests match these filters.
      </p>

      <BaseDataTable
        v-if="backtests !== null"
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
  backtests,
  isLoading,
  readError,
  historyRows,
  filteredHistory,
  historyPagination,
} = props.history;
const historyColumns = createHistoryColumns(props.actions);
const historyRowProps = props.actions.rowProps;
</script>
<style scoped>
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
.history-heading {
  margin-bottom: var(--design-space-xl);
  flex-wrap: wrap;
}
.history-create {
  flex-shrink: 0;
}
.history-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--design-space-md);
}
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--design-space-xl);
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
