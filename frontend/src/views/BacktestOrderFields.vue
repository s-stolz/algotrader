<script setup lang="ts">
import { computed } from 'vue';
import BacktestFieldHelp from './BacktestFieldHelp.vue';
import { NInputNumber } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import type { BacktestExecutionPayload } from '@/types/backtest/requests';
const execution = defineModel<BacktestExecutionPayload>('execution', {
  required: true,
});
defineProps<{ errors: Record<string, string> }>();
const emit = defineEmits<{ change: [field: string] }>();
const policy = computed({
  get: () =>
    execution.value.intrabar_execution_policy ??
    (execution.value.intrabar_exit_policy === 'take_profit_first'
      ? 'optimistic'
      : execution.value.intrabar_exit_policy === 'error'
        ? 'error'
        : 'conservative'),
  set: (value: 'conservative' | 'optimistic' | 'error') => {
    execution.value.intrabar_execution_policy = value;
    emit('change', 'intrabar_execution_policy');
  },
});
</script>
<template>
  <template v-if="execution.execution_mode === 'orders'">
    <div
      class="field"
      data-setup-field="candle_quote"
      ><span class="field-label"
        >Candle quote
        <BacktestFieldHelp label="candle quote">
          <p
            >Choose whether the candle's open, high, low and close represent
            bid, ask or midpoint prices. This describes the data source.</p
          >
          <p
            >Buy limits match the ask; sell limits match the bid. With bid
            candles, the ask is the candle price plus spread. With ask candles,
            the bid is the candle price minus spread. Midpoint candles use half
            the spread on each side.</p
          >
          <p
            >For example, a bid price of 1.1000 with a spread of 0.0002 gives an
            ask of 1.1002. This can change whether a limit fills. With zero
            spread, all three choices behave identically.</p
          >
        </BacktestFieldHelp>
      </span>
      <BaseSelect
        v-model:value="execution.candle_quote"
        aria-label="Candle quote"
        placeholder="Select quote convention"
        :options="[
          { label: 'Bid', value: 'bid' },
          { label: 'Ask', value: 'ask' },
          { label: 'Mid', value: 'mid' },
        ]"
        :status="errors.candle_quote ? 'error' : undefined"
        @update:value="emit('change', 'candle_quote')"
      />
      <small
        v-if="errors.candle_quote"
        role="alert"
        >{{ errors.candle_quote }}</small
      >
    </div>
    <div
      class="field"
      data-setup-field="spread"
      >Spread (price units)
      <n-input-number
        v-model:value="execution.spread"
        :min="0"
        :input-props="{ 'aria-label': 'Spread (price units)' }"
        :status="errors.spread ? 'error' : undefined"
        @update:value="emit('change', 'spread')"
      />
      <small
        v-if="errors.spread"
        role="alert"
        >{{ errors.spread }}</small
      >
    </div>
    <div
      class="field"
      data-setup-field="max_position_quantity"
      ><span class="field-label"
        >Maximum position quantity
        <BacktestFieldHelp label="maximum position quantity">
          <p
            >Optional cap on the absolute net position, using the same quantity
            units as the strategy. Leave empty for unlimited exposure.</p
          >
          <p
            >This does not set each order's quantity. An order that would exceed
            the cap is cancelled rather than resized. Reducing exposure remains
            allowed.</p
          >
        </BacktestFieldHelp>
      </span>
      <n-input-number
        v-model:value="execution.max_position_quantity"
        placeholder="Unlimited"
        :input-props="{ 'aria-label': 'Maximum position quantity' }"
        :status="errors.max_position_quantity ? 'error' : undefined"
        @update:value="emit('change', 'max_position_quantity')"
      />
      <small
        v-if="errors.max_position_quantity"
        role="alert"
        >{{ errors.max_position_quantity }}</small
      >
    </div>
    <div
      class="field"
      data-setup-field="intrabar_execution_policy"
      ><span class="field-label"
        >Intrabar execution policy
        <BacktestFieldHelp label="intrabar execution policy">
          <p
            >A minute candle can touch an entry, stop loss and take profit
            without revealing which came first. The backtester compares
            open–high–low–close and open–low–high–close paths.</p
          >
          <p
            ><strong>Conservative:</strong> Choose the path with lower equity at
            the minute close.</p
          >
          <p
            ><strong>Optimistic:</strong> Choose the path with higher equity at
            the minute close.</p
          >
          <p
            ><strong>Error:</strong> Fail the run if the paths produce different
            execution outcomes.</p
          >
          <p
            >Exits can only execute after entry. Opening gaps are processed
            first; trading costs still apply. These are OHLC path assumptions,
            not the actual tick sequence.</p
          >
        </BacktestFieldHelp>
      </span>
      <BaseSelect
        v-model:value="policy"
        aria-label="Intrabar execution policy"
        :options="[
          { label: 'Conservative', value: 'conservative' },
          { label: 'Optimistic', value: 'optimistic' },
          { label: 'Error', value: 'error' },
        ]"
      />
    </div>
  </template>
</template>
<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.field {
  min-width: 0;
  font-size: var(--design-text-secondary);
}
.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
}
small {
  line-height: 1.5;
}
</style>
