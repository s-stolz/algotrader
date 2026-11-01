<script setup lang="ts">
import { computed } from 'vue';
import { NInputNumber } from 'naive-ui';
import type { BacktestExecutionPayload } from '@/types/backtesterContracts';
import { dailyEntryLimitIssue } from '@/types/backtest/entryLimit';

const execution = defineModel<BacktestExecutionPayload>('execution', {
  required: true,
});
const issue = computed(() =>
  dailyEntryLimitIssue(execution.value.max_entries_per_day),
);
function update(value: number | null) {
  if (value === null) delete execution.value.max_entries_per_day;
  else execution.value.max_entries_per_day = value;
}
</script>
<template>
  <div>
    <label
      >Max entries per day (UTC)
      <n-input-number
        :value="execution.max_entries_per_day ?? null"
        :min="1"
        :precision="0"
        clearable
        placeholder="Unlimited"
        :status="issue ? 'error' : undefined"
        @update:value="update"
      />
    </label>
    <p
      v-if="issue"
      role="alert"
      >{{ issue }}</p
    >
  </div>
</template>
<style scoped>
label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: var(--design-text-secondary);
}
p {
  margin-bottom: 0;
}
</style>
