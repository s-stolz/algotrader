<script setup lang="ts">
import { computed } from 'vue';
import { NInputNumber } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import type { BacktestExecutionPayload } from '@/types/backtest/requests';
withDefaults(defineProps<{ errors?: Record<string, string> }>(), {
  errors: () => ({}),
});
const emit = defineEmits<{ change: [field: string] }>();
const execution = defineModel<BacktestExecutionPayload>({ required: true });
const sizing = computed(
  () =>
    execution.value.sizing ?? {
      mode: 'strategy' as const,
      value: null,
      leverage: 1,
    },
);
const modes = [
  { label: 'Strategy-defined', value: 'strategy' },
  { label: 'Fixed quantity', value: 'units' },
  { label: 'Fixed exposure', value: 'exposure' },
  { label: 'Exposure (% of equity)', value: 'equity_exposure' },
  { label: 'Risk per entry', value: 'risk' },
  { label: 'Risk per entry (% of equity)', value: 'equity_risk' },
];
const protectionModes = [
  { label: 'Strategy-provided', value: 'strategy' },
  { label: 'None', value: 'none' },
  { label: 'Percent of entry', value: 'percent' },
  { label: 'Price distance', value: 'distance' },
  { label: 'Tick distance', value: 'ticks' },
];
const exits = ['stop_loss', 'take_profit'] as const;
function changeSizing(mode: typeof sizing.value.mode) {
  emit('change', 'sizing');
  execution.value.sizing = {
    ...sizing.value,
    mode,
    value: mode === 'strategy' ? null : 1,
  };
}
function changeExit(
  key: (typeof exits)[number],
  mode: 'none' | 'strategy' | 'percent' | 'distance' | 'ticks',
) {
  emit('change', key);
  execution.value[key] = {
    mode,
    value: mode === 'none' || mode === 'strategy' ? null : 1,
  };
}
</script>
<template>
  <div
    class="risk-fields"
    data-setup-field="sizing"
  >
    <p
      v-if="errors.sizing"
      role="alert"
      >{{ errors.sizing }}</p
    >
    <label
      >Sizing mode<BaseSelect
        :value="sizing.mode"
        :options="modes"
        aria-label="Sizing mode"
        @update:value="changeSizing"
    /></label>
    <label v-if="sizing.mode !== 'strategy'"
      >Sizing amount<n-input-number
        :value="sizing.value"
        :min="0"
        aria-label="Sizing amount"
        @update:value="execution.sizing = { ...sizing, value: $event }"
    /></label>
    <label
      >Leverage<n-input-number
        :value="sizing.leverage"
        :min="1"
        aria-label="Leverage"
        @update:value="execution.sizing = { ...sizing, leverage: $event ?? 1 }"
    /></label>
    <p
      >Money amounts use each symbol’s settlement currency. Leverage determines
      required margin; it does not multiply the requested position size.</p
    >
    <div
      v-for="key in exits"
      :key="key"
      :data-setup-field="key"
    >
      <p
        v-if="errors[key]"
        role="alert"
        >{{ errors[key] }}</p
      >
      <label
        >{{ key === 'stop_loss' ? 'Stop-loss' : 'Take-profit'
        }}<BaseSelect
          :value="execution[key]?.mode ?? 'strategy'"
          :options="protectionModes"
          :aria-label="
            key === 'stop_loss' ? 'Stop-loss source' : 'Take-profit source'
          "
          @update:value="changeExit(key, $event)"
      /></label>
      <n-input-number
        v-if="
          execution[key] && !['none', 'strategy'].includes(execution[key]!.mode)
        "
        :value="execution[key]!.value"
        :min="0"
        :aria-label="
          key === 'stop_loss' ? 'Stop-loss distance' : 'Take-profit distance'
        "
        @update:value="execution[key] = { ...execution[key]!, value: $event }"
      />
    </div>
    <p v-if="sizing.mode === 'risk' || sizing.mode === 'equity_risk'"
      >Planned risk uses entry-to-stop distance, excluding costs. Each entry has
      its own budget; combined position risk can be higher.</p
    >
  </div>
</template>
<style scoped>
.risk-fields {
  display: grid;
  gap: var(--design-space-md);
}
label {
  display: grid;
  gap: var(--design-space-xs);
}
p {
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
</style>
