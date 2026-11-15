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
  { label: 'Strategy-provided', value: 'strategy' },
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
    <div class="risk-row">
      <div class="sizing-field">
        <div class="field-label">
          <span>Sizing mode</span>
          <BacktestFieldHelp label="sizing modes">
            <p
              ><strong>Strategy-provided:</strong> Use the quantity supplied by
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
            <p>Money amounts use each symbol’s settlement currency.</p>
            <p
              >Each entry has its own risk budget; combined position risk can be
              higher.</p
            >
          </BacktestFieldHelp>
          <BacktestFieldHelp
            v-if="errors.sizing"
            label="sizing"
            error
          >
            <p>{{ errors.sizing }}</p>
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
            :status="
              errors.sizing &&
              (!sizing.value ||
                sizing.value <= 0 ||
                !Number.isFinite(sizing.value))
                ? 'error'
                : undefined
            "
            :input-props="{
              'aria-invalid':
                !!errors.sizing &&
                (!sizing.value ||
                  sizing.value <= 0 ||
                  !Number.isFinite(sizing.value)),
            }"
            aria-label="Sizing amount"
            @blur="emit('change', 'sizing')"
            @update:value="execution.sizing = { ...sizing, value: $event }"
          />
        </label>
      </div>
      <label>
        <span class="field-label">
          Leverage
          <BacktestFieldHelp label="leverage">
            <p
              >Leverage determines required margin; it does not multiply the
              requested position size.</p
            >
          </BacktestFieldHelp>
        </span>
        <n-input-number
          :value="sizing.leverage"
          :min="1"
          :status="
            errors.sizing &&
            (!Number.isFinite(sizing.leverage) || sizing.leverage < 1)
              ? 'error'
              : undefined
          "
          :input-props="{
            'aria-invalid':
              !!errors.sizing &&
              (!Number.isFinite(sizing.leverage) || sizing.leverage < 1),
          }"
          aria-label="Leverage"
          @blur="emit('change', 'sizing')"
          @update:value="
            execution.sizing = { ...sizing, leverage: $event ?? 1 }
          "
        />
      </label>
    </div>
    <div class="risk-row">
      <div
        v-for="key in exits"
        :key="key"
        class="protection-field"
        :data-setup-field="key"
      >
        <div class="field-label">
          <span>{{ key === 'stop_loss' ? 'Stop-loss' : 'Take-profit' }}</span>
          <BacktestFieldHelp
            v-if="errors[key]"
            :label="key === 'stop_loss' ? 'stop-loss' : 'take-profit'"
            error
          >
            <p>{{ errors[key] }}</p>
          </BacktestFieldHelp>
        </div>
        <span
          v-if="errors[key]"
          :id="`setup-${key}-error`"
          hidden
          >{{ errors[key] }}</span
        >
        <BaseSelect
          :value="execution[key]?.mode ?? 'strategy'"
          :options="protectionModes"
          :status="errors[key] ? 'error' : undefined"
          :input-props="{
            'aria-invalid': !!errors[key],
            'aria-describedby': errors[key] ? `setup-${key}-error` : undefined,
          }"
          :aria-label="
            key === 'stop_loss' ? 'Stop-loss source' : 'Take-profit source'
          "
          @update:value="changeExit(key, $event)"
        />
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
          :status="errors[key] ? 'error' : undefined"
          :input-props="{
            'aria-invalid': !!errors[key],
            'aria-describedby': errors[key] ? `setup-${key}-error` : undefined,
          }"
          :min="0"
          @blur="emit('change', key)"
          :aria-label="
            key === 'stop_loss' ? 'Stop-loss distance' : 'Take-profit distance'
          "
          @update:value="execution[key] = { ...execution[key]!, value: $event }"
        />
      </div>
    </div>
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
