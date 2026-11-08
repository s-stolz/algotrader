<template>
  <ComparisonColumnSettings :comparison="comparison" />
  <BaseDataTable
    data-testid="workspace-current-backtest"
    :columns="comparisonColumns"
    :data="sortedCurrentRows"
    :row-key="(run: BacktestRun) => run.run_id"
    :row-props="currentRowProps"
    :pagination="analysisPagination"
    :paginate-single-page="true"
    :max-height="360"
    :scroll-x="comparisonScrollWidth"
    size="small"
    @update:sorter="updateComparisonSort"
  />
  <WorkspaceReplay :inspection="inspection" />
  <MonthlyResults :inspection="inspection" />
</template>
<script setup lang="ts">
import MonthlyResults from '../results/MonthlyResults.vue';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import ComparisonColumnSettings from './ComparisonColumnSettings.vue';
import WorkspaceReplay from './WorkspaceReplay.vue';
import type { BacktestRun } from '@/types/backtesterContracts';
import type { BacktestWorkspace } from '../useBacktestWorkspace';
import type { WorkspaceComparison } from './useWorkspaceComparison';
const props = defineProps<{
  inspection: BacktestWorkspace['inspection'];
  comparison: WorkspaceComparison;
}>();
const {
  comparisonColumns,
  updateComparisonSort,
  sortedCurrentRows,
  currentRowProps,
  analysisPagination,
  comparisonScrollWidth,
} = props.comparison;
</script>
