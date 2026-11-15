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
      ><span>Daily entry limit <small>(Optional)</small></span>
      <n-input-number
        :value="execution.max_entries_per_day ?? null"
        :min="1"
        :precision="0"
        clearable
        placeholder="Unlimited"
        :status="issue ? 'error' : undefined"
        :input-props="{
          'aria-label': 'Daily entry limit',
          'aria-invalid': !!issue,
          'aria-describedby': issue ? 'entry-limit-error' : undefined,
        }"
        @update:value="update"
      />
    </label>
    <p
      v-if="issue"
      id="entry-limit-error"
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
small {
  color: var(--design-color-muted);
  font-size: 10px;
}
</style>
