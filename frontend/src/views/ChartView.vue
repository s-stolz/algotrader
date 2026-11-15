<template>
  <main class="chart-workspace">
    <TheTopBar
      v-if="initialized"
      v-model:chart-interaction-mode="chartInteractionMode"
    />
    <ChartArea
      v-if="initialized"
      id="chart-area"
      ref="chartArea"
      :interaction-mode="chartInteractionMode"
      @candles-loaded="restoreChartOverlay"
    />
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import ChartArea from '@/components/Chart/ChartArea.vue';
import {
  DEFAULT_CHART_INTERACTION_MODE,
  type ChartInteractionMode,
} from '@/components/Chart/chartInteractionMode';
import TheTopBar from '@/components/TopBar/TheTopBar.vue';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import { useMarketsStore } from '@/stores/marketsStore';

defineOptions({
  name: 'ChartView',
});

const initialized = ref(false);
const indicatorsStore = useIndicatorsStore();
const overlayStore = useBacktestOverlayStore();
const marketsStore = useMarketsStore();
const currentMarketStore = useCurrentMarketStore();
const chartInteractionMode = ref<ChartInteractionMode>(
  DEFAULT_CHART_INTERACTION_MODE,
);

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
  await Promise.all([
    fetchMarketsAndInitCurrent(),
    indicatorsStore.restorePersistedIndicators(),
  ]);
  initialized.value = true;
}

let hasRestoredOverlay = false;
function restoreChartOverlay(): void {
  if (hasRestoredOverlay) return;
  hasRestoredOverlay = true;
  if (!overlayStore.selectedRun) void overlayStore.restorePersistedSelection();
}

void initializeChartView();
</script>

<style scoped>
.chart-workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

#chart-area {
  flex: 1;
  min-height: 0;
}
</style>
