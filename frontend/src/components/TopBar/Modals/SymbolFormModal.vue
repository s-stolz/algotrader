<template>
  <BaseModal
    ref="symbolForm"
    :modalId="'symbolForm'"
    :title="market ? 'Edit symbol' : 'New symbol'"
  >
    <div id="new-symbol-input-wrapper">
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
          min="0"
          step="0.0001"
        />
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
        @click="addSymbol"
      >
        {{ market ? 'Save symbol' : 'Add symbol' }}
      </n-button>
    </template>
  </BaseModal>
</template>

<script setup lang="ts">
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
  if (!validMinMove.value) minMove.value = 0.00001;
  if (!validMarketType.value) marketType.value = null;
}

async function addSymbol(): Promise<void> {
  error.value = '';
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

  const newMarket: MarketCreatePayload = {
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

  try {
    if (props.market) await updateMarket(props.market.symbol_id, newMarket);
    else await createMarket(newMarket);
    await marketsStore.fetch();
    symbolForm.value?.close();
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : 'Unable to save symbol';
  }
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
