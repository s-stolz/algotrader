<template>
  <BaseModal ref="symbolForm" :modalId="'symbolForm'" :title="'New Symbol'">
    <div id="new-symbol-input-wrapper">
      <n-input
        class="new-symbol-input text-uppercase"
        v-model:value="symbol"
        :status="validSymbol || symbol === undefined ? 'success' : 'error'"
        placeholder="Symbol"
      />

      <n-input
        class="new-symbol-input text-uppercase"
        v-model:value="exchange"
        :status="validExchange || exchange === undefined ? 'success' : 'error'"
        placeholder="Exchange"
      />

      <n-input-number
        class="new-symbol-input"
        v-model:value="minMove"
        min="0"
        step="0.0001"
      />

      <n-select
        class="new-symbol-input"
        v-model:value="marketType"
        placeholder="Market Type"
        :status="validMarketType || marketType === undefined ? 'success' : 'error'"
        :options="options"
      />
    </div>

    <template #footer>
      <n-button round class="new-symbol-button" @click="addSymbol"> Add Symbol </n-button>
    </template>
  </BaseModal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { SelectOption } from 'naive-ui';
import { NButton, NInput, NInputNumber, NSelect } from 'naive-ui';

import { createMarket } from '@/api/marketClient';
import BaseModal from '@/components/Common/BaseModal.vue';
import { useMarketsStore } from '@/stores/marketsStore';
import type { MarketCreatePayload } from '@/types/contracts';

defineOptions({
  name: 'SymbolFormModal',
});

interface BaseModalExpose {
  close: () => void;
}

const marketsStore = useMarketsStore();
const symbolForm = ref<BaseModalExpose | null>(null);
const symbol = ref<string | null | undefined>(undefined);
const exchange = ref<string | null | undefined>(undefined);
const minMove = ref<number | null>(0.00001);
const marketType = ref<string | null | undefined>(undefined);
const options: SelectOption[] = [
  { label: 'Forex', value: 'Forex' },
  { label: 'Crypto', value: 'Crypto' },
  { label: 'Stock', value: 'Stock' },
];

const validSymbol = computed(() => typeof symbol.value === 'string' && symbol.value.trim() !== '');
const validExchange = computed(() => typeof exchange.value === 'string' && exchange.value.trim() !== '');
const validMinMove = computed(() => typeof minMove.value === 'number' && minMove.value > 0);
const validMarketType = computed(() => (
  typeof marketType.value === 'string' && marketType.value.trim() !== ''
));

function setInvalidInputs(): void {
  if (!validSymbol.value) symbol.value = null;
  if (!validExchange.value) exchange.value = null;
  if (!validMinMove.value) minMove.value = 0.00001;
  if (!validMarketType.value) marketType.value = null;
}

async function addSymbol(): Promise<void> {
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
    timezone: 'UTC',
  };

  await createMarket(newMarket);
  symbolForm.value?.close();
  await marketsStore.fetch();
}
</script>

<style scoped>
.new-symbol-input {
  width: calc(100% - 30px);
  margin: 10px 15px 0 15px;
}

.new-symbol-input:last-child {
  margin-bottom: 10px;
}

.new-symbol-button {
  width: 100%;
}

.text-uppercase ::v-deep input {
  text-transform: uppercase;
}
</style>
