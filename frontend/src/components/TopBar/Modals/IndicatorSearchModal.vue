<template>
  <BaseModal :modalId="'indicatorSearch'" :title="'Indicator'">
    <div>
      <span id="search-bar-wrapper">
        <n-input
          v-model:value="indicatorInput"
          id="indicator-input"
          autocomplete="off"
          placeholder="Indicator"
          round
          clearable
        >
          <template #prefix>
            <n-icon>
              <SearchOutline />
            </n-icon>
          </template>
        </n-input>
        <hr class="separator" />
      </span>

      <BaseDataTable :max-height="300">
        <tbody>
          <tr v-for="indicator in filteredIndicators" :key="indicator.id" @click="onApplyIndicator(indicator)">
            <td>{{ indicator.name }}</td>
          </tr>
        </tbody>
      </BaseDataTable>
    </div>
  </BaseModal>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { NIcon, NInput } from 'naive-ui';

import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import { fetchAvailableIndicators } from '@/api/indicatorClient';
import BaseModal from '@/components/Common/BaseModal.vue';
import { SearchOutline } from '@/icons';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { AvailableIndicator } from '@/types/contracts';

defineOptions({
  name: 'IndicatorSearchModal',
});

const indicatorInput = ref('');
const indicators = ref<AvailableIndicator[]>([]);
const currentMarketStore = useCurrentMarketStore();
const currentTimeframeStore = useCurrentTimeframeStore();
const indicatorsStore = useIndicatorsStore();

const filteredIndicators = computed(() => indicators.value
  .filter((indicator) => indicator.name.toUpperCase().includes(indicatorInput.value.toUpperCase()))
  .sort((a, b) => a.name.localeCompare(b.name)));

const symbol = computed(() => currentMarketStore.symbol);
const exchange = computed(() => currentMarketStore.exchange);
const timeframe = computed(() => currentTimeframeStore.value);

async function getIndicators(): Promise<void> {
  try {
    indicators.value = await fetchAvailableIndicators();
  } catch (error) {
    console.error('Error fetching indicators:', error);
  }
}

function onApplyIndicator(indicator: AvailableIndicator): void {
  const queryParams: {
    exchange?: string;
    limit: number;
    symbol: string | null;
    timeframe: string;
  } = {
    symbol: symbol.value,
    timeframe: timeframe.value,
    limit: 500,
  };

  if (exchange.value) {
    queryParams.exchange = exchange.value;
  }

  void indicatorsStore.requestIndicator(null, indicator.id, queryParams, {});
}

onMounted(() => {
  void getIndicators();
});
</script>

<style scoped>
#search-bar-wrapper {
  position: sticky;
  top: -10px;
}

#indicator-input {
  width: calc(100% - 30px);
  margin: 8px 15px;
}

tr {
  cursor: pointer;
}
</style>
