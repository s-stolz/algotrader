<script setup lang="ts">
import BaseDatePicker from './BaseDatePicker.vue';
import { NButton } from 'naive-ui';
defineProps<{
  start: string;
  end: string;
  invalid?: boolean;
  errorId?: string;
}>();
const emit = defineEmits<{
  'update:start': [value: string | null];
  'update:end': [value: string | null];
}>();
const datePresets = [
  { label: 'Past month', months: 1 },
  { label: 'Past year', months: 12 },
  { label: 'Past 5 years', months: 60 },
  { label: 'Past 10 years', months: 120 },
  { label: 'Year to date', months: 0 },
];
function applyDatePreset(months: number) {
  const now = new Date();
  const end = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
  );
  const start =
    months === 0
      ? new Date(Date.UTC(end.getUTCFullYear(), 0, 1))
      : new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - months, 1));
  if (months > 0) {
    const lastDay = new Date(
      Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0),
    ).getUTCDate();
    start.setUTCDate(Math.min(end.getUTCDate(), lastDay));
  }
  emit('update:start', start.toISOString().slice(0, 10));
  emit('update:end', end.toISOString().slice(0, 10));
}
</script>
<template>
  <fieldset
    class="full date-range"
    :aria-invalid="!!invalid"
    :aria-describedby="invalid ? errorId : undefined"
  >
    <legend class="visually-hidden">Dates (UTC)</legend>
    <div class="date-inputs">
      <label
        ><span>Start date (UTC)</span
        ><BaseDatePicker
          :formatted-value="start || null"
          data-testid="creation-start"
          :status="invalid ? 'error' : undefined"
          @update:formatted-value="emit('update:start', $event)"
          type="date"
          value-format="yyyy-MM-dd"
          :clearable="false"
          :input-readonly="true"
      /></label>
      <label
        ><span>End date (UTC)</span
        ><BaseDatePicker
          :formatted-value="end || null"
          data-testid="creation-end"
          :status="invalid ? 'error' : undefined"
          @update:formatted-value="emit('update:end', $event)"
          type="date"
          value-format="yyyy-MM-dd"
          :clearable="false"
          :input-readonly="true"
      /></label>
    </div>
    <div class="preset-buttons"
      ><n-button
        v-for="preset in datePresets"
        :key="preset.months"
        size="tiny"
        secondary
        :theme-overrides="{ fontSizeTiny: '11px', heightTiny: '24px' }"
        @click="applyDatePreset(preset.months)"
        >{{ preset.label }}</n-button
      ></div
    >
  </fieldset>
</template>
<style scoped>
.date-range {
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}
.date-range legend {
  padding: 0;
  margin-bottom: var(--design-space-xs);
  font-size: var(--design-text-secondary);
}
.date-inputs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: center;
  gap: var(--design-space-sm);
}
.preset-buttons {
  display: flex;
  gap: var(--design-space-xs);
  margin-top: var(--design-space-sm);
  flex-wrap: wrap;
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
label {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--design-space-sm);
  font-size: var(--design-text-secondary);
}
@media (max-width: 520px) {
  .date-inputs {
    grid-template-columns: 1fr;
  }
}
</style>
