<template>
  <div id="wrapper-select">
    <n-button primary round @click="modalStore.openModal('symbolSearch')">
      {{ currentSymbol }}
    </n-button>

    <TimeframeDropdown />

    <div class="chart-interaction-controls" role="group" aria-label="Chart interaction mode">
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-button
            circle
            class="chart-interaction-mode-button"
            :class="{
              'chart-interaction-mode-button--active': isChartInteractionModeSelected('pan'),
            }"
            data-testid="chart-interaction-mode-pan"
            aria-label="Pan mode"
            :aria-pressed="isChartInteractionModeSelected('pan')"
            @click="selectChartInteractionMode('pan')"
          >
            <n-icon size="20">
              <HandRightOutline />
            </n-icon>
          </n-button>
        </template>
        <span data-testid="chart-interaction-mode-pan-tooltip">Pan</span>
      </n-tooltip>

      <n-tooltip trigger="hover">
        <template #trigger>
          <n-button
            circle
            class="chart-interaction-mode-button"
            :class="{
              'chart-interaction-mode-button--active': isChartInteractionModeSelected('measure'),
            }"
            data-testid="chart-interaction-mode-measure"
            aria-label="Measure mode"
            :aria-pressed="isChartInteractionModeSelected('measure')"
            @click="selectChartInteractionMode('measure')"
          >
            <n-icon size="20">
              <ExpandOutline />
            </n-icon>
          </n-button>
        </template>
        <span data-testid="chart-interaction-mode-measure-tooltip">Measure</span>
      </n-tooltip>
    </div>

    <n-button round @click="modalStore.openModal('indicatorSearch')">Indicator</n-button>
    <n-button round data-testid="open-backtest-runs" @click="modalStore.openModal('backtestRuns')">
      <template #icon>
        <n-icon>
          <ListOutline />
        </n-icon>
      </template>
      Backtest Runs
    </n-button>

    <TopBarModals />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NButton, NIcon, NTooltip } from 'naive-ui';

import {
  DEFAULT_CHART_INTERACTION_MODE,
  type ChartInteractionMode,
} from '@/components/Chart/chartInteractionMode';
import TimeframeDropdown from '@/components/TopBar/TimeframeDropdown.vue';
import TopBarModals from '@/components/TopBar/Modals/TopBarModals.vue';
import { ExpandOutline, HandRightOutline, ListOutline } from '@/icons';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useModalStore } from '@/stores/modalStore';

defineOptions({
  name: 'TheTopBar',
});

const props = withDefaults(defineProps<{
  chartInteractionMode?: ChartInteractionMode;
}>(), {
  chartInteractionMode: DEFAULT_CHART_INTERACTION_MODE,
});

const emit = defineEmits<{
  'update:chartInteractionMode': [mode: ChartInteractionMode];
}>();

const currentMarketStore = useCurrentMarketStore();
const modalStore = useModalStore();
const currentSymbol = computed(() => currentMarketStore.symbol);

function isChartInteractionModeSelected(mode: ChartInteractionMode): boolean {
  return props.chartInteractionMode === mode;
}

function selectChartInteractionMode(mode: ChartInteractionMode): void {
  emit('update:chartInteractionMode', mode);
}
</script>

<style scoped>
#wrapper-select {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.chart-interaction-controls {
  display: flex;
  align-items: center;
  gap: 6px;
}

.chart-interaction-mode-button {
  width: 34px;
  height: 34px;
  color: #cbd5e1;
  background: rgba(19, 23, 34, 0.35);
  border: 1px solid rgba(148, 163, 184, 0.35);
}

.chart-interaction-mode-button:hover,
.chart-interaction-mode-button:focus-visible {
  color: #f8fafc;
  border-color: rgba(148, 163, 184, 0.75);
}

.chart-interaction-mode-button--active {
  color: #ffffff;
  background: rgba(37, 99, 235, 0.32);
  border-color: #60a5fa;
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.4);
}
</style>
