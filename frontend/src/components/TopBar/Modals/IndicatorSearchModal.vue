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

      <n-scrollbar style="height: 300px">
        <table>
          <tbody>
            <template v-for="(indicator) in filteredIndicators" :key="indicator.id">
              <tr @click="onApplyIndicator(indicator)">
                <td>
                  {{ indicator.name }}
                </td>
              </tr>

              <hr class="row-separator" />
            </template>
          </tbody>
        </table>
      </n-scrollbar>
    </div>
  </BaseModal>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { NIcon, NInput, NScrollbar } from 'naive-ui';

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

table {
  width: 100%;
}

tr {
  padding: 5px 15px;
  width: calc(100% - 30px);
  display: flex;
  cursor: pointer;
}

td {
  line-height: 20px;
  padding: 10px 0;
}

.row-separator {
  border: none;
  height: 1px;
  background-color: #a0a0a029;
  margin: 0;
}

tr:hover {
  background-color: #36363661;
}
</style>
