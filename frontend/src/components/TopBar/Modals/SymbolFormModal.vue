<template>
  <BaseModal
    ref="symbolForm"
    :modalId="'symbolForm'"
    :title="market ? 'Edit symbol' : 'New symbol'"
  >
    <div id="new-symbol-input-wrapper">
      <div class="symbol-field symbol-field-wide">
        <span>Data source</span>
        <BaseSelect
          v-if="!market"
          v-model:value="sourceType"
          aria-label="Data source"
          :options="sourceOptions"
          @update:value="resetBrokerSelection"
        />
        <span v-else>{{
          isBroker ? 'Connected broker' : 'Custom · CSV uploads'
        }}</span>
        <BrokerInstrumentPicker
          v-if="isBroker && !market"
          @verified="applyBrokerInstrument"
        />
      </div>
      <div class="symbol-field">
        <SymbolFieldLabel label="Symbol"
          >Broker instrument code, such as EURUSD or BTCUSD.</SymbolFieldLabel
        >
        <n-input
          class="new-symbol-input"
          :input-props="{
            style: 'text-transform: uppercase;',
          }"
          v-model:value="symbol"
          :disabled="isBroker"
          :status="validSymbol || symbol === undefined ? 'success' : 'error'"
          placeholder="Symbol"
          aria-label="Symbol"
        />
      </div>
      <div class="symbol-field">
        <SymbolFieldLabel label="Exchange"
          >Broker or trading venue used to identify this
          market.</SymbolFieldLabel
        >
        <n-input
          class="new-symbol-input"
          :input-props="{
            style: 'text-transform: uppercase;',
          }"
          v-model:value="exchange"
          :disabled="isBroker"
          :status="
            validExchange || exchange === undefined ? 'success' : 'error'
          "
          placeholder="Exchange"
          aria-label="Exchange"
        />
      </div>
      <div class="symbol-field">
        <SymbolFieldLabel label="Minimum price move"
          >Smallest price increment (tick size), such as 0.00001 for
          EURUSD.</SymbolFieldLabel
        >
        <n-input-number
          class="new-symbol-input"
          v-model:value="minMove"
          aria-label="Minimum price move"
          :min="0"
          :step="0.0001"
        />
        <span
          v-if="brokerInstrument?.suggested_min_move"
          class="specification-hint"
        >
          Display precision suggests {{ brokerInstrument.suggested_min_move }}.
          Enter the verified tick size.
        </span>
      </div>
      <div class="symbol-field">
        <SymbolFieldLabel label="Market type"
          >Asset category: Forex, Crypto, or Stock.</SymbolFieldLabel
        >
        <BaseSelect
          class="new-symbol-input"
          v-model:value="marketType"
          placeholder="Market Type"
          aria-label="Market Type"
          :status="
            validMarketType || marketType === undefined ? 'success' : 'error'
          "
          :options="options"
        />
      </div>
      <div class="symbol-field">
        <SymbolFieldLabel label="Timezone"
          >Market timezone, such as UTC or Europe/Berlin.</SymbolFieldLabel
        >
        <n-input
          v-model:value="timezone"
          placeholder="Timezone"
          aria-label="Timezone"
        />
      </div>
      <div class="symbol-field">
        <SymbolFieldLabel label="Settlement currency"
          >Currency used for backtest equity, profit, and risk amounts. No
          currency conversion is applied.</SymbolFieldLabel
        >
        <n-input
          v-model:value="currency"
          placeholder="Settlement currency"
          aria-label="Settlement currency"
        />
      </div>
      <div class="symbol-field symbol-field-wide">
        <SymbolFieldLabel label="Contract multiplier"
          >Value of a 1.0 price move per quantity unit, in settlement currency.
          Use 1 for base-asset units.</SymbolFieldLabel
        >
        <n-input-number
          v-model:value="multiplier"
          placeholder="Contract multiplier"
          aria-label="Contract multiplier"
        />
      </div>
      <div class="symbol-field">
        <SymbolFieldLabel label="Minimum quantity"
          >Smallest permitted order, in quantity units—not lots. For EURUSD,
          1,000 units equals 0.01 lot.</SymbolFieldLabel
        >
        <n-input-number
          v-model:value="minimum"
          placeholder="Minimum quantity"
          aria-label="Minimum quantity"
        />
      </div>
      <div class="symbol-field">
        <SymbolFieldLabel label="Quantity increment"
          >Step between valid order sizes. An increment of 1,000 allows 1,000,
          2,000, 3,000 units, and so on.</SymbolFieldLabel
        >
        <n-input-number
          v-model:value="step"
          placeholder="Quantity increment"
          aria-label="Quantity increment"
        />
      </div>
      <p
        v-if="error"
        role="alert"
        >{{ error }}</p
      >
    </div>

    <template #footer>
      <n-button
        round
        class="new-symbol-button"
        :loading="saving"
        @click="addSymbol"
      >
        {{ market ? 'Save symbol' : 'Add symbol' }}
      </n-button>
    </template>
  </BaseModal>
</template>

<script setup lang="ts">
import BrokerInstrumentPicker from './markets/BrokerInstrumentPicker.vue';
import type { BrokerInstrument } from '@/types/brokerContracts';
import SymbolFieldLabel from './SymbolFieldLabel.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import { computed, ref } from 'vue';
import type { SelectOption } from 'naive-ui';
import { NButton, NInput, NInputNumber } from 'naive-ui';

import { createMarket, updateMarket } from '@/api/marketClient';
import BaseModal from '@/components/Common/BaseModal.vue';
import { useMarketsStore } from '@/stores/marketsStore';
import type { Market, MarketCreatePayload } from '@/types/contracts';

defineOptions({
  name: 'SymbolFormModal',
});

interface BaseModalExpose {
  close: () => void;
}

const props = defineProps<{ market?: Market | null }>();
const emit = defineEmits<{ created: [market: Market] }>();
const sourceType = ref<'custom' | 'broker'>(
  props.market?.source_type ?? 'custom',
);
const sourceOptions = [
  { label: 'Connected broker', value: 'broker' },
  { label: 'Custom · CSV uploads', value: 'custom' },
];
const isBroker = computed(() => sourceType.value === 'broker');
const brokerInstrument = ref<BrokerInstrument | null>(null);
const saving = ref(false);
const marketsStore = useMarketsStore();
const symbolForm = ref<BaseModalExpose | null>(null);
const symbol = ref<string | null | undefined>(props.market?.symbol);
const exchange = ref<string | null | undefined>(props.market?.exchange);
const minMove = ref<number | null>(props.market?.min_move ?? 0.00001);
const marketType = ref<string | null | undefined>(props.market?.market_type);
const timezone = ref(props.market?.timezone ?? 'UTC');
const currency = ref(props.market?.settlement_currency ?? '');
const multiplier = ref<number | null>(
  props.market?.contract_multiplier ?? null,
);
const minimum = ref<number | null>(props.market?.minimum_quantity ?? null);
const step = ref<number | null>(props.market?.quantity_step ?? null);
const error = ref('');
const options: SelectOption[] = [
  { label: 'Forex', value: 'Forex' },
  { label: 'Crypto', value: 'Crypto' },
  { label: 'Stock', value: 'Stock' },
];

const validSymbol = computed(
  () => typeof symbol.value === 'string' && symbol.value.trim() !== '',
);
const validExchange = computed(
  () => typeof exchange.value === 'string' && exchange.value.trim() !== '',
);
const validMinMove = computed(
  () => typeof minMove.value === 'number' && minMove.value > 0,
);
const validMarketType = computed(
  () => typeof marketType.value === 'string' && marketType.value.trim() !== '',
);

function setInvalidInputs(): void {
  if (!validSymbol.value) symbol.value = null;
  if (!validExchange.value) exchange.value = null;
  if (!validMinMove.value) minMove.value = null;
  if (!validMarketType.value) marketType.value = null;
}

async function addSymbol(): Promise<void> {
  if (saving.value) return;
  error.value = '';
  if (isBroker.value && !props.market && !brokerInstrument.value) {
    error.value = 'Select and verify a broker instrument.';
    return;
  }
  setInvalidInputs();
  if (
    !currency.value.trim() ||
    !timezone.value.trim() ||
    ![multiplier.value, minimum.value, step.value].every(
      (value) =>
        typeof value === 'number' && Number.isFinite(value) && value > 0,
    )
  ) {
    error.value =
      'Complete the currency, timezone, and positive instrument specifications.';
    return;
  }
  if (
    !validSymbol.value ||
    !validExchange.value ||
    !validMinMove.value ||
    !validMarketType.value
  ) {
    setInvalidInputs();
    console.error('Invalid Inputs!');
    return;
  }

  const binding = props.market ?? brokerInstrument.value;
  const newMarket: MarketCreatePayload = {
    source_type: sourceType.value,
    ...(isBroker.value && binding
      ? {
          broker_provider: binding.broker_provider,
          broker_account_id: binding.broker_account_id,
          broker_environment: binding.broker_environment,
          broker_symbol_id: binding.broker_symbol_id,
        }
      : {}),
    symbol: symbol.value!.toUpperCase().trim(),
    exchange: exchange.value!.toUpperCase().trim(),
    min_move: minMove.value!,
    market_type: marketType.value!.trim(),
    timezone: timezone.value.trim(),
    settlement_currency: currency.value.trim().toUpperCase(),
    contract_multiplier: multiplier.value!,
    minimum_quantity: minimum.value!,
    quantity_step: step.value!,
  };

  saving.value = true;
  try {
    const result = props.market
      ? await updateMarket(props.market.symbol_id, newMarket)
      : await createMarket(newMarket);
    await marketsStore.fetch();
    symbolForm.value?.close();
    if (!props.market)
      emit('created', { ...newMarket, symbol_id: result.symbol_id });
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : 'Unable to save symbol';
  } finally {
    saving.value = false;
  }
}

function resetBrokerSelection() {
  brokerInstrument.value = null;
  symbol.value = undefined;
  exchange.value = undefined;
  minMove.value = isBroker.value ? null : 0.00001;
  marketType.value = undefined;
  timezone.value = isBroker.value ? '' : 'UTC';
  currency.value = '';
  multiplier.value = minimum.value = step.value = null;
}

function applyBrokerInstrument(instrument: BrokerInstrument | null) {
  brokerInstrument.value = instrument;
  symbol.value = instrument?.symbol;
  exchange.value = instrument?.exchange;
  minMove.value = null;
  marketType.value = instrument?.market_type;
  timezone.value = instrument?.timezone ?? '';
  currency.value = instrument?.settlement_currency ?? '';
  multiplier.value = null;
  minimum.value = instrument?.minimum_quantity ?? null;
  step.value = instrument?.quantity_step ?? null;
}
</script>

<style scoped>
#new-symbol-input-wrapper {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--design-space-lg);
  padding: var(--design-space-lg);
}

.symbol-field {
  display: flex;
  flex-direction: column;
  gap: var(--design-space-xs);
  min-width: 0;
}
.symbol-field-wide {
  grid-column: 1 / -1;
}
.symbol-field > :last-child {
  margin-top: auto;
}
[role='alert'] {
  grid-column: 1 / -1;
  color: var(--design-color-error);
}
@media (max-width: 480px) {
  #new-symbol-input-wrapper {
    grid-template-columns: 1fr;
  }
}
.new-symbol-input,
.new-symbol-button {
  width: 100%;
}
</style>
