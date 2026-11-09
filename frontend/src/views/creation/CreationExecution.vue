<template>
  <p v-if="currencies.length"
    >Account currency: {{ currencies.join(', ') }} (from selected symbols)</p
  >
  <BacktestRiskFields
    v-model="draft.execution"
    :errors="setupErrors"
    @change="touchSetup"
  />
  <CreationParameters execution-settings />
  <BacktestExecutionFields
    v-model:execution="draft.execution"
    v-model:engine="draft.engine"
    :errors="setupErrors"
    @change="touchSetup"
  />
</template>
<script setup lang="ts">
import BacktestRiskFields from '../BacktestRiskFields.vue';
import CreationParameters from './CreationParameters.vue';
import BacktestExecutionFields from '../BacktestExecutionFields.vue';
import { useCreation } from './creationContext';
import { computed } from 'vue';
import { useMarketsStore } from '@/stores/marketsStore';
const { draft, setupErrors, touchSetup, selections } = useCreation();
const markets = useMarketsStore();
const currencies = computed(() => [
  ...new Set(
    markets.all
      .filter((market) => selections.value.marketIds.includes(market.symbol_id))
      .map((market) => market.settlement_currency)
      .filter(Boolean),
  ),
]);
</script>
