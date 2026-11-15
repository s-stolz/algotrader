<script setup lang="ts">
import { NButton, NSwitch } from 'naive-ui';
import BaseTimePicker from '@/components/Common/BaseTimePicker.vue';
import {
  formatScheduleMinute,
  type DailyScheduleDraft,
  type DailyScheduleInput,
} from '@/types/backtest/schedule';

const schedule = defineModel<DailyScheduleDraft>('schedule', {
  required: true,
});
defineProps<{ errors: Record<string, string> }>();
const emit = defineEmits<{ change: [field: string] }>();
const fields = [
  { key: 'entry_start_minute_utc', label: 'Entry start' },
  { key: 'last_entry_minute_utc', label: 'Last entry' },
  { key: 'exit_minute_utc', label: 'Exit time' },
] as const;
const rowIds = new WeakMap<DailyScheduleInput, number>();
let nextId = 0;
function rowId(row: DailyScheduleInput): number {
  if (!rowIds.has(row)) rowIds.set(row, nextId++);
  return rowIds.get(row)!;
}
function addSchedule() {
  schedule.value.candidates.push({
    entry_start_minute_utc: null,
    last_entry_minute_utc: null,
    exit_minute_utc: null,
  });
}
function updateTime(
  row: DailyScheduleInput,
  key: keyof DailyScheduleInput,
  value: string | null,
  index: number,
) {
  const [hours, minutes] = value?.split(':').map(Number) ?? [];
  row[key] = value ? hours * 60 + minutes : null;
  emit('change', `schedule-${index}`);
}
</script>
<template>
  <div data-setup-field="schedule">
    <div class="schedule-toggle">
      <span id="daily-schedule-label"
        >Use daily schedules <small>UTC</small></span
      >
      <n-switch
        v-model:value="schedule.enabled"
        aria-labelledby="daily-schedule-label"
        @update:value="emit('change', 'schedule')"
      />
    </div>
    <template v-if="schedule.enabled">
      <div
        v-for="(row, index) in schedule.candidates"
        :key="rowId(row)"
        class="schedule-row"
        :class="{ invalid: errors[`schedule-${index}`] }"
        :data-setup-field="`schedule-${index}`"
      >
        <header>
          <strong>Schedule {{ index + 1 }}</strong>
          <n-button
            size="tiny"
            quaternary
            :disabled="schedule.candidates.length === 1"
            :aria-label="`Remove schedule ${index + 1}`"
            @click="schedule.candidates.splice(index, 1)"
            >Remove</n-button
          >
        </header>
        <div class="schedule-fields">
          <label
            v-for="field in fields"
            :key="field.key"
          >
            {{ field.label }}
            <BaseTimePicker
              :formatted-value="
                row[field.key] === null
                  ? null
                  : formatScheduleMinute(row[field.key]!)
              "
              format="HH:mm"
              value-format="HH:mm"
              :status="errors[`schedule-${index}`] ? 'error' : undefined"
              role="group"
              :aria-label="`Schedule ${index + 1} ${field.label} (UTC)`"
              :aria-invalid="!!errors[`schedule-${index}`]"
              :aria-describedby="
                errors[`schedule-${index}`]
                  ? `schedule-${index}-error`
                  : undefined
              "
              @update:formatted-value="
                updateTime(row, field.key, $event, index)
              "
            />
          </label>
        </div>
        <small
          v-if="errors[`schedule-${index}`]"
          :id="`schedule-${index}-error`"
          role="alert"
        >
          {{ errors[`schedule-${index}`] }}
        </small>
      </div>
      <n-button
        dashed
        block
        @click="addSchedule"
        >＋ Add schedule alternative</n-button
      >
      <small
        v-if="errors.schedule"
        role="alert"
        >{{ errors.schedule }}</small
      >
    </template>
  </div>
</template>
<style scoped>
.schedule-toggle,
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.schedule-toggle {
  margin-bottom: 18px;
}
.schedule-toggle small {
  margin-left: 8px;
  color: var(--design-color-muted);
}
.schedule-row {
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  background: var(--design-color-inset);
}
.schedule-row.invalid {
  border-color: var(--design-color-error);
}
header {
  margin-bottom: 10px;
  font-size: var(--design-text-secondary);
}
.schedule-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
  font-size: var(--design-text-secondary);
}
[role='alert'] {
  display: block;
  margin-top: 8px;
  color: var(--design-color-error);
}
@media (max-width: 520px) {
  .schedule-fields {
    grid-template-columns: 1fr;
  }
}
</style>
