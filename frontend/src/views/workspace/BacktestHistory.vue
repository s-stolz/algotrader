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
              v-if="!isLoading && !readError"
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

      <BaseAsyncState
        v-if="readError && filteredHistory.length"
        kind="error"
        compact
        label="Backtests unavailable"
        message="Couldn’t load backtests."
        retry
        :retrying="isRefreshing"
        @retry="actions.refresh"
      />
      <BaseDataTable
        data-testid="workspace-history"
        :columns="historyColumns"
        :data="filteredHistory"
        :row-key="rowKey"
        :row-props="historyRowProps"
        :pagination="
          !isLoading && !readError && filteredHistory.length
            ? historyPagination
            : false
        "
        :scroll-x="1470"
        :max-height="540"
        size="medium"
        striped
      >
        <template #empty>
          <BaseAsyncState
            :kind="isLoading ? 'loading' : readError ? 'error' : 'empty'"
            :label="
              isLoading
                ? 'Loading backtests'
                : readError
                  ? 'Backtests unavailable'
                  : 'No backtests'
            "
            :message="
              readError
                ? 'Couldn’t load backtests.'
                : historyRows.length
                  ? 'No matching backtests'
                  : 'No backtests yet'
            "
            :retry="!!readError"
            :retrying="isRefreshing"
            @retry="actions.refresh"
          />
        </template>
      </BaseDataTable>
    </div>
  </section>
</template>
<script setup lang="ts">
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';

import { NButton, NIcon, NTag } from 'naive-ui';
import { AddOutline } from '@vicons/ionicons5';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import BacktestHistoryFilters from '@/views/workspace/BacktestHistoryFilters.vue';
import { createHistoryColumns } from '@/views/workspace/backtestHistoryColumns';
import { rowKey } from '@/views/workspace/backtestHistoryRows';
import type { BacktestWorkspace } from '@/views/workspace/useBacktestWorkspace';
const props = defineProps<{
  history: BacktestWorkspace['history'];
  actions: BacktestWorkspace['historyActions'];
  canCreate: boolean;
}>();
const {
  isLoading,
  isRefreshing,
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
