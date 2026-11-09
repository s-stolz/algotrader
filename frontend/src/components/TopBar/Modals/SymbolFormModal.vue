<template>
  <BaseModal
    ref="symbolForm"
    :modalId="'symbolForm'"
    :title="market ? 'Edit symbol' : 'New symbol'"
  >
    <div id="new-symbol-input-wrapper">
      <n-input
        class="new-symbol-input"
        :input-props="{ style: 'text-transform: uppercase;' }"
        v-model:value="symbol"
        :status="validSymbol || symbol === undefined ? 'success' : 'error'"
        placeholder="Symbol"
        aria-label="Symbol"
      />

      <n-input
        class="new-symbol-input"
        :input-props="{ style: 'text-transform: uppercase;' }"
        v-model:value="exchange"
        :status="validExchange || exchange === undefined ? 'success' : 'error'"
        placeholder="Exchange"
        aria-label="Exchange"
      />

      <n-input-number
        class="new-symbol-input"
        v-model:value="minMove"
        aria-label="Minimum price move"
        min="0"
        step="0.0001"
      />

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
      <n-input
        v-model:value="timezone"
        placeholder="Timezone"
        aria-label="Timezone"
      />
      <n-input
        v-model:value="currency"
        placeholder="Settlement currency"
        aria-label="Settlement currency"
      />
      <n-input-number
        v-model:value="multiplier"
        placeholder="Contract multiplier"
        aria-label="Contract multiplier"
      />
      <n-input-number
        v-model:value="minimum"
        placeholder="Minimum quantity"
        aria-label="Minimum quantity"
      />
      <n-input-number
        v-model:value="step"
        placeholder="Quantity increment"
        aria-label="Quantity increment"
      />
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
  display: flex;
  flex-direction: column;
  gap: var(--design-space-md);
  padding: var(--design-space-lg);
}

.new-symbol-input,
.new-symbol-button {
  width: 100%;
}
</style>
