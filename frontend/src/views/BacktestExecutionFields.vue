<script setup lang="ts">
import { ref } from 'vue';
import { NButton, NIcon, NInputNumber } from 'naive-ui';
import type { SelectOption } from 'naive-ui';
import InformationCircleOutline from '@vicons/ionicons5/InformationCircleOutline';
import BasePopover from '@/components/Common/BasePopover.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import type { BacktestRequestPayload } from '@/types/backtesterContracts';
const execution = defineModel<BacktestRequestPayload['execution']>('execution', { required: true });
const engine = defineModel<BacktestRequestPayload['engine']>('engine', { required: true });
const gapHelp = ref(false);
const exitHelp = ref(false);
const directionOptions: SelectOption[] = [
  { label: 'Long and short', value: 'long_and_short' },
  { label: 'Long only', value: 'long_only' },
  { label: 'Short only', value: 'short_only' },
];
const engineOptions: SelectOption[] = [
  { label: 'Vectorized', value: 'vectorized' }, { label: 'Event driven', value: 'event_driven' },
];
const gapOptions: SelectOption[] = [
  { label: 'Skip', value: 'skip' }, { label: 'Expire', value: 'expire' },
  { label: 'Error', value: 'error' },
];
const exitOptions: SelectOption[] = [
  { label: 'Conservative', value: 'conservative' },
  { label: 'Stop first', value: 'stop_first' },
  { label: 'Take profit first', value: 'take_profit_first' },
  { label: 'Error', value: 'error' },
];

</script>
<template><div class="fields">
  <label class="full">Allowed directions<BaseSelect v-model:value="execution.allowed_directions" :options="directionOptions" /></label>
  <label class="full">Engine<BaseSelect v-model:value="engine" :options="engineOptions" /></label>
  <section class="full"><h4>Trading costs</h4><div class="fields costs">
    <label>Slippage (bps)<n-input-number v-model:value="execution.slippage_bps" :min="0" /></label>
    <label>Commission (bps)<n-input-number v-model:value="execution.commission_bps" :min="0" /></label>
  </div></section>
  <section class="full"><h4>Data &amp; fills</h4><div class="fields costs">
    <div class="policy-field"><span class="policy-label">Gap policy
      <BasePopover v-model:show="gapHelp" trigger="hover" :width="320">
        <template #trigger><n-button text aria-label="About gap policy" @focus="gapHelp = true" @blur="gapHelp = false" @click="gapHelp = true"><n-icon :component="InformationCircleOutline" :size="17" /></n-button></template>
        <div class="policy-help">
          <p>What happens when a pending trade cannot use the next candle's opening price because it is missing or invalid?</p>
          <p><strong>Skip:</strong> Wait for a valid opening price. Pending trade changes are combined before execution.</p>
          <p><strong>Expire:</strong> Discard those pending trade changes.</p>
          <p><strong>Error:</strong> Fail the backtest and report the invalid opening price.</p>
        </div>
      </BasePopover>
    </span><BaseSelect v-model:value="execution.gap_policy" aria-label="Gap policy" :options="gapOptions" /></div>
    <div class="policy-field"><span class="policy-label">Intrabar exit policy
      <BasePopover v-model:show="exitHelp" trigger="hover" :width="320">
        <template #trigger><n-button text aria-label="About intrabar exit policy" @focus="exitHelp = true" @blur="exitHelp = false" @click="exitHelp = true"><n-icon :component="InformationCircleOutline" :size="17" /></n-button></template>
        <div class="policy-help">
          <p>A candle can touch both the stop loss and take profit without revealing which came first.</p>
          <p><strong>Conservative / Stop first:</strong> Use the stop-loss price. These options currently behave identically.</p>
          <p><strong>Take profit first:</strong> Use the take-profit price.</p>
          <p><strong>Error:</strong> Fail the backtest when the order cannot be determined.</p>
          <p>If the candle opens beyond an exit level, that exit is filled at the opening price before this rule is considered. Trading costs still apply.</p>
        </div>
      </BasePopover>
    </span><BaseSelect v-model:value="execution.intrabar_exit_policy" aria-label="Intrabar exit policy" :options="exitOptions" /></div>
  </div></section>
</div></template>
<style scoped>
.policy-field { display: flex; flex-direction: column; gap: 8px; font-size: 12px; min-width: 0; }
.policy-label { display: flex; align-items: center; gap: 6px; }
.policy-help p { margin: 0 0 10px; line-height: 1.5; }
.policy-help p:last-child { margin-bottom: 0; }
.fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
label { min-width: 0; display: flex; flex-direction: column; gap: 7px; font-size: 12px; }
h4 { margin: 6px 0 0; font-size: 13px; }
.full { grid-column: 1 / -1; }
.costs { padding-top: 14px; }
@media (max-width: 520px) { .fields { grid-template-columns: 1fr; } }
</style>
