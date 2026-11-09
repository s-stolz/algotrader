<script setup lang="ts">
import { ref } from 'vue';
import BacktestOrderFields from './BacktestOrderFields.vue';
import { NButton, NIcon, NInputNumber } from 'naive-ui';
import type { SelectOption } from 'naive-ui';
import InformationCircleOutline from '@vicons/ionicons5/es/InformationCircleOutline';
import BasePopover from '@/components/Common/BasePopover.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import type { BacktestRequestPayload } from '@/types/backtesterContracts';
const execution = defineModel<BacktestRequestPayload['execution']>(
  'execution',
  { required: true },
);
const engine = defineModel<BacktestRequestPayload['engine']>('engine', {
  required: true,
});
defineProps<{ errors: Record<string, string> }>();
const emit = defineEmits<{ change: [field: string] }>();
const gapHelp = ref(false);
const exitHelp = ref(false);
const engineOptions: SelectOption[] = [
  { label: 'Vectorized', value: 'vectorized' },
  { label: 'Event driven', value: 'event_driven' },
];
const gapOptions: SelectOption[] = [
  { label: 'Skip', value: 'skip' },
  { label: 'Expire', value: 'expire' },
  { label: 'Error', value: 'error' },
];
const exitOptions: SelectOption[] = [
  { label: 'Conservative', value: 'conservative' },
  { label: 'Stop first', value: 'stop_first' },
  { label: 'Take profit first', value: 'take_profit_first' },
  { label: 'Error', value: 'error' },
];
</script>
<template>
  <div class="fields">
    <label
      class="full"
      data-setup-field="engine"
      >Engine<BaseSelect
        v-model:value="engine"
        :options="engineOptions"
        :status="errors.engine ? 'error' : undefined"
        @update:value="emit('change', 'engine')"
      /><small
        v-if="errors.engine"
        role="alert"
        >{{ errors.engine }}</small
      ></label
    >
    <BacktestOrderFields
      v-model:execution="execution"
      :errors="errors"
      @change="emit('change', $event)"
    />
    <section class="full"
      ><div class="fields">
        <div
          class="policy-field"
          data-setup-field="gap_policy"
          ><span class="policy-label"
            >Gap policy
            <BasePopover
              v-model:show="gapHelp"
              trigger="hover"
              :width="320"
            >
              <template #trigger
                ><n-button
                  text
                  aria-label="About gap policy"
                  @focus="gapHelp = true"
                  @blur="gapHelp = false"
                  @click="gapHelp = true"
                  ><n-icon
                    :component="InformationCircleOutline"
                    :size="17" /></n-button
              ></template>
              <div
                v-if="execution.execution_mode === 'orders'"
                class="policy-help"
              >
                <p
                  >Missing M1 candles create execution gaps, including
                  closed-market intervals.</p
                >
                <p><strong>Skip:</strong> Keep pending orders.</p>
                <p
                  ><strong>Expire:</strong> Cancel orders exposed to the gap.</p
                >
                <p
                  ><strong>Error:</strong> Fail the backtest and report the
                  gap.</p
                >
              </div>
              <div
                v-else
                class="policy-help"
              >
                <p
                  >What happens when a pending trade cannot use the next
                  candle's opening price because it is missing or invalid?</p
                >
                <p
                  ><strong>Skip:</strong> Wait for a valid opening price.
                  Pending trade changes are combined before execution.</p
                >
                <p
                  ><strong>Expire:</strong> Discard those pending trade
                  changes.</p
                >
                <p
                  ><strong>Error:</strong> Fail the backtest and report the
                  invalid opening price.</p
                >
              </div>
            </BasePopover> </span
          ><BaseSelect
            v-model:value="execution.gap_policy"
            aria-label="Gap policy"
            :options="gapOptions"
            :status="errors.gap_policy ? 'error' : undefined"
            @update:value="emit('change', 'gap_policy')"
          /><small
            v-if="errors.gap_policy"
            role="alert"
            >{{ errors.gap_policy }}</small
          ></div
        >
        <div
          class="policy-field"
          v-if="execution.execution_mode !== 'orders'"
          data-setup-field="intrabar_exit_policy"
          ><span class="policy-label"
            >Intrabar exit policy
            <BasePopover
              v-model:show="exitHelp"
              trigger="hover"
              :width="320"
            >
              <template #trigger
                ><n-button
                  text
                  aria-label="About intrabar exit policy"
                  @focus="exitHelp = true"
                  @blur="exitHelp = false"
                  @click="exitHelp = true"
                  ><n-icon
                    :component="InformationCircleOutline"
                    :size="17" /></n-button
              ></template>
              <div class="policy-help">
                <p
                  >A candle can touch both the stop loss and take profit without
                  revealing which came first.</p
                >
                <p
                  ><strong>Conservative / Stop first:</strong> Use the stop-loss
                  price. These options currently behave identically.</p
                >
                <p
                  ><strong>Take profit first:</strong> Use the take-profit
                  price.</p
                >
                <p
                  ><strong>Error:</strong> Fail the backtest when the order
                  cannot be determined.</p
                >
                <p
                  >If the candle opens beyond an exit level, that exit is filled
                  at the opening price before this rule is considered. Trading
                  costs still apply.</p
                >
              </div>
            </BasePopover> </span
          ><BaseSelect
            v-model:value="execution.intrabar_exit_policy"
            aria-label="Intrabar exit policy"
            :options="exitOptions"
            :status="errors.intrabar_exit_policy ? 'error' : undefined"
            @update:value="emit('change', 'intrabar_exit_policy')"
          /><small
            v-if="errors.intrabar_exit_policy"
            role="alert"
            >{{ errors.intrabar_exit_policy }}</small
          ></div
        >
      </div></section
    >
    <label
      v-for="cost in ['slippage_bps', 'commission_bps'] as const"
      :key="cost"
      :data-setup-field="cost"
    >
      {{ cost === 'slippage_bps' ? 'Slippage (bps)' : 'Commission (bps)' }}
      <n-input-number
        v-model:value="execution[cost]"
        :min="0"
        :status="errors[cost] ? 'error' : undefined"
        :input-props="{
          'aria-label':
            cost === 'slippage_bps' ? 'Slippage (bps)' : 'Commission (bps)',
          'aria-invalid': !!errors[cost],
          'aria-describedby': errors[cost] ? `${cost}-error` : undefined,
        }"
        @update:value="emit('change', cost)"
      />
      <small
        v-if="errors[cost]"
        :id="`${cost}-error`"
        role="alert"
        >{{ errors[cost] }}</small
      >
    </label>
  </div>
</template>
<style scoped>
.policy-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: var(--design-text-secondary);
  min-width: 0;
}
.policy-label {
  display: flex;
  align-items: center;
  gap: 6px;
}
.policy-help p {
  margin: 0 0 10px;
  line-height: 1.5;
}
.policy-help p:last-child {
  margin-bottom: 0;
}
.fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
label {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: var(--design-text-secondary);
}
.full {
  grid-column: 1 / -1;
}
@media (max-width: 520px) {
  .fields {
    grid-template-columns: 1fr;
  }
}
</style>
