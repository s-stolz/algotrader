<script setup lang="ts">
import { computed } from 'vue';
import BaseTimePicker from '@/components/Common/BaseTimePicker.vue';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import type { BacktestExecutionPayload } from '@/types/backtesterContracts';
import {
  dailyScheduleIssue,
  formatScheduleMinute,
  type DailyTradingSchedule,
} from '@/types/backtest/schedule';

const execution = defineModel<BacktestExecutionPayload>('execution', {
  required: true,
});
const fields = [
  { key: 'entry_start_minute_utc', label: 'Entry start' },
  { key: 'last_entry_minute_utc', label: 'Last entry' },
  { key: 'exit_minute_utc', label: 'Exit time' },
] as const;
const issue = computed(() =>
  dailyScheduleIssue(execution.value.daily_schedule),
);
function toggle(enabled: boolean) {
  if (enabled) {
    execution.value.daily_schedule = {
      entry_start_minute_utc: 0,
      last_entry_minute_utc: 720,
      exit_minute_utc: 1020,
    };
  } else {
    delete execution.value.daily_schedule;
  }
}
function updateTime(key: keyof DailyTradingSchedule, value: string | null) {
  if (!value || !execution.value.daily_schedule) return;
  const [hours, minutes] = value.split(':').map(Number);
  execution.value.daily_schedule[key] = hours * 60 + minutes;
}
</script>
<template>
  <section aria-label="Daily schedule">
    <BaseCheckbox
      :checked="!!execution.daily_schedule"
      @update:checked="toggle"
      >Daily schedule (UTC)</BaseCheckbox
    >
    <div
      v-if="execution.daily_schedule"
      class="schedule-fields"
    >
      <label
        v-for="field in fields"
        :key="field.key"
      >
        {{ field.label }}
        <BaseTimePicker
          :formatted-value="
            formatScheduleMinute(execution.daily_schedule[field.key])
          "
          format="HH:mm"
          value-format="HH:mm"
          :clearable="false"
          :aria-label="`${field.label} (UTC)`"
          @update:formatted-value="updateTime(field.key, $event)"
        />
      </label>
    </div>
    <p
      v-if="issue"
      role="alert"
      >{{ issue }}</p
    >
  </section>
</template>
<style scoped>
.schedule-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
  font-size: var(--design-text-secondary);
}
p {
  margin-bottom: 0;
}
@media (max-width: 520px) {
  .schedule-fields {
    grid-template-columns: 1fr;
  }
}
</style>
