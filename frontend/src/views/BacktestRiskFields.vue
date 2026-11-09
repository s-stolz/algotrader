<script setup lang="ts">
import { computed } from 'vue';
import { NInputNumber } from 'naive-ui';
import BacktestFieldHelp from './BacktestFieldHelp.vue';
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
    <div class="risk-row">
      <div class="sizing-field">
        <div class="field-label">
          <span>Sizing mode</span>
          <BacktestFieldHelp label="sizing modes">
            <p
              ><strong>Strategy-defined:</strong> Use the quantity supplied by
              the strategy and its sizing settings.</p
            >
            <p
              ><strong>Fixed quantity:</strong> Request the same number of
              quantity units for each entry.</p
            >
            <p
              ><strong>Fixed exposure:</strong> Size each entry to a fixed
              monetary position value, using the entry price and contract
              multiplier.</p
            >
            <p
              ><strong>Exposure (% of equity):</strong> Use a percentage of
              current equity as the position value. Equity includes unrealized
              profit and loss.</p
            >
            <p
              ><strong>Risk per entry:</strong> Calculate quantity from a fixed
              monetary risk budget and the distance from entry to the initial
              stop loss.</p
            >
            <p
              ><strong>Risk per entry (% of equity):</strong> Use a percentage
              of current equity as the risk budget, then calculate quantity from
              the initial stop-loss distance.</p
            >
            <p
              >Risk modes require an initial stop. Planned risk excludes costs
              and can differ from the actual loss. Quantities round down to the
              symbol’s increment; orders below its minimum or without enough
              margin are skipped.</p
            >
          </BacktestFieldHelp>
        </div>
        <BaseSelect
          :value="sizing.mode"
          :options="modes"
          aria-label="Sizing mode"
          @update:value="changeSizing"
        />
        <slot
          v-if="sizing.mode === 'strategy'"
          name="sizing"
        />
        <label v-if="sizing.mode !== 'strategy'">
          Sizing amount<n-input-number
            :value="sizing.value"
            :min="0"
            aria-label="Sizing amount"
            @update:value="execution.sizing = { ...sizing, value: $event }"
          />
        </label>
      </div>
      <label>
        Leverage<n-input-number
          :value="sizing.leverage"
          :min="1"
          aria-label="Leverage"
          @update:value="
            execution.sizing = { ...sizing, leverage: $event ?? 1 }
          "
        />
      </label>
    </div>
    <p
      >Money amounts use each symbol’s settlement currency. Leverage determines
      required margin; it does not multiply the requested position size.</p
    >
    <div class="risk-row">
      <div
        v-for="key in exits"
        :key="key"
        class="protection-field"
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
        <slot
          v-if="(execution[key]?.mode ?? 'strategy') === 'strategy'"
          :name="key"
        />
        <n-input-number
          v-if="
            execution[key] &&
            !['none', 'strategy'].includes(execution[key]!.mode)
          "
          :value="execution[key]!.value"
          :min="0"
          :aria-label="
            key === 'stop_loss' ? 'Stop-loss distance' : 'Take-profit distance'
          "
          @update:value="execution[key] = { ...execution[key]!, value: $event }"
        />
      </div>
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
.risk-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: var(--design-space-md);
}
.field-label {
  display: flex;
  align-items: center;
  gap: var(--design-space-xs);
}
.sizing-field,
.protection-field,
label {
  display: grid;
  min-width: 0;
  gap: var(--design-space-xs);
}
p {
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
@media (max-width: 480px) {
  .risk-row {
    grid-template-columns: 1fr;
  }
}
</style>
