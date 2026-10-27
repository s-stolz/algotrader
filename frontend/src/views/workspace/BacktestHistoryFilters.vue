<template>
  <div class="filters">
    <n-input
      v-model:value="search"
      data-testid="workspace-search"
      clearable
      placeholder="Search saved runs and batches"
      aria-label="Search saved runs and batches"
    />
    <BaseSelect
      v-model:value="statusFilter"
      data-testid="workspace-status-filter"
      aria-label="Filter by status"
      :options="statusOptions"
    />
    <BaseSelect
      v-model:value="typeFilter"
      data-testid="workspace-type-filter"
      aria-label="Filter by type"
      :options="typeOptions"
    />
    <BaseSelect
      v-model:value="marketFilter"
      data-testid="workspace-market-filter"
      aria-label="Filter by Market"
      :options="marketOptions"
    />
    <BaseSelect
      v-model:value="strategyFilter"
      data-testid="workspace-strategy-filter"
      aria-label="Filter by Strategy"
      :options="strategyOptions"
    />
    <BaseSelect
      v-model:value="timeframeFilter"
      data-testid="workspace-timeframe-filter"
      aria-label="Filter by Timeframe"
      :options="timeframeOptions"
    />
    <BaseSelect
      v-model:value="failedFilter"
      data-testid="workspace-failed-filter"
      aria-label="Filter by failed runs"
      :options="failedOptions"
    />
  </div>
</template>
<script setup lang="ts">
import { NInput } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import type { BacktestWorkspace } from './useBacktestWorkspace';
const props = defineProps<{ history: BacktestWorkspace['history'] }>();
const {
  search,
  statusFilter,
  typeFilter,
  marketFilter,
  strategyFilter,
  timeframeFilter,
  failedFilter,
  statusOptions,
  typeOptions,
  marketOptions,
  strategyOptions,
  timeframeOptions,
  failedOptions,
} = props.history;
</script>
<style scoped>
.filters {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) repeat(6, minmax(110px, 1fr));
  gap: var(--design-space-sm);
  margin-bottom: var(--design-space-xl);
}
@media (max-width: 1200px) {
  .filters {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
@media (max-width: 700px) {
  .filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
