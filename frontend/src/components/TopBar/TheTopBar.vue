<template>
  <div id="wrapper-select">
    <n-button primary round @click="modalStore.openModal('symbolSearch')">
      {{ currentSymbol }}
    </n-button>

    <TimeframeDropdown />

    <n-button round @click="modalStore.openModal('indicatorSearch')">Indicator</n-button>
    <n-button round data-testid="open-backtest-runs" @click="modalStore.openModal('backtestRuns')">
      Backtests
    </n-button>

    <div class="chart-interaction-controls" role="group" aria-label="Chart interaction mode">
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
        <template #icon>
          <n-icon
            size="20"
            :color="chartInteractionModeIconColor('pan')"
          >
            <HandRightOutline />
          </n-icon>
        </template>
      </n-button>

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
        <template #icon>
          <n-icon
            size="20"
            :color="chartInteractionModeIconColor('measure')"
          >
            <ResizeOutline />
          </n-icon>
        </template>
      </n-button>
    </div>

    <TopBarModals />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NButton, NIcon } from 'naive-ui';

import {
  DEFAULT_CHART_INTERACTION_MODE,
  type ChartInteractionMode,
} from '@/components/Chart/chartInteractionMode';
import TimeframeDropdown from '@/components/TopBar/TimeframeDropdown.vue';
import TopBarModals from '@/components/TopBar/Modals/TopBarModals.vue';
import { HandRightOutline, ResizeOutline } from '@/icons';
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
const selectedChartInteractionModeColor = '#7fe7c4';

function isChartInteractionModeSelected(mode: ChartInteractionMode): boolean {
  return props.chartInteractionMode === mode;
}

function chartInteractionModeIconColor(mode: ChartInteractionMode): string | undefined {
  return isChartInteractionModeSelected(mode) ? selectedChartInteractionModeColor : undefined;
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
  margin-left: auto;
}

.chart-interaction-mode-button--active :deep(.n-button__state-border) {
  border: var(--n-border-hover);
}

.chart-interaction-mode-button--active :deep(.n-button__content) {
  color: #7fe7c4;
}
</style>
