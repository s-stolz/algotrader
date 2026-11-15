<template>
  <main class="chart-workspace">
    <BaseAsyncState
      v-if="!initialized"
      style="flex: 1"
      :kind="initializationFailed ? 'error' : 'loading'"
      :label="initializationFailed ? 'Chart unavailable' : 'Loading Chart'"
      :message="initializationFailed ? 'Couldn’t initialize Chart.' : ''"
      :retry="initializationFailed"
      @retry="initializeChartView"
    />
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
import { onActivated, onBeforeUnmount, onDeactivated, ref } from 'vue';
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';
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
const initializationFailed = ref(false);
let initializing = false;
let ready = false;
let active = true;
onActivated(() => {
  active = true;
  if (ready) initialized.value = true;
});
onDeactivated(() => {
  active = false;
});
onBeforeUnmount(() => {
  active = false;
});
const indicatorsStore = useIndicatorsStore();
const overlayStore = useBacktestOverlayStore();
const marketsStore = useMarketsStore();
const currentMarketStore = useCurrentMarketStore();
const chartInteractionMode = ref<ChartInteractionMode>(
  DEFAULT_CHART_INTERACTION_MODE,
);

async function fetchMarketsAndInitCurrent(): Promise<void> {
  await marketsStore.fetch();
  if (marketsStore.fetchError) throw new Error(marketsStore.fetchError);

  if (marketsStore.all.length === 0) {
    return;
  }

  if (currentMarketStore.isValid(marketsStore.all)) {
    return;
  }

  currentMarketStore.setMarket(marketsStore.all[0]);
}

async function initializeChartView(): Promise<void> {
  if (initializing || ready) return;
  initializing = true;
  initializationFailed.value = false;
  const results = await Promise.allSettled([
    fetchMarketsAndInitCurrent(),
    indicatorsStore.restorePersistedIndicators(),
  ]);
  initializing = false;
  initializationFailed.value = results.some(
    (result) => result.status === 'rejected',
  );
  ready = !initializationFailed.value;
  if (active && ready) initialized.value = true;
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
