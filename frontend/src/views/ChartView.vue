<template>
  <div>
    <TheTopBar />
    <ChartArea
      id="chart-area"
      ref="chartArea"
    />
  </div>
</template>

<script setup lang="ts">
import ChartArea from '@/components/Chart/ChartArea.vue';
import TheTopBar from '@/components/TopBar/TheTopBar.vue';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useMarketsStore } from '@/stores/marketsStore';

defineOptions({
  name: 'ChartView',
});

const marketsStore = useMarketsStore();
const currentMarketStore = useCurrentMarketStore();

async function fetchMarketsAndInitCurrent(): Promise<void> {
  await marketsStore.fetch();

  if (marketsStore.all.length === 0) {
    return;
  }

  if (currentMarketStore.isValid(marketsStore.all)) {
    return;
  }

  currentMarketStore.setMarket(marketsStore.all[0]);
}

async function initializeChartView(): Promise<void> {
  await fetchMarketsAndInitCurrent();
}

void initializeChartView();
</script>

<style scoped>
#chart-area {
  height: calc(100vh - 80px);
}
</style>
