<template>
  <DesignScope>
    <div id="wrapper-select">
      <n-button
        primary
        round
        @click="modalStore.openModal('symbolSearch')"
      >
        {{ currentSymbol }}
      </n-button>

      <TimeframeDropdown />

      <n-button
        round
        @click="modalStore.openModal('indicatorSearch')"
        >Indicator</n-button
      >

      <div
        class="chart-interaction-controls"
        role="group"
        aria-label="Chart interaction mode"
      >
        <n-button
          circle
          :type="isChartInteractionModeSelected('pan') ? 'primary' : 'default'"
          :secondary="isChartInteractionModeSelected('pan')"
          class="chart-interaction-mode-button"
          :class="{
            'chart-interaction-mode-button--active':
              isChartInteractionModeSelected('pan'),
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
          :type="
            isChartInteractionModeSelected('measure') ? 'primary' : 'default'
          "
          :secondary="isChartInteractionModeSelected('measure')"
          class="chart-interaction-mode-button"
          :class="{
            'chart-interaction-mode-button--active':
              isChartInteractionModeSelected('measure'),
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
  </DesignScope>
</template>

<script setup lang="ts">
import DesignScope from '@/components/Common/DesignScope.vue';
import { designTokens } from '@/design/tokens';
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

const props = withDefaults(
  defineProps<{
    chartInteractionMode?: ChartInteractionMode;
  }>(),
  {
    chartInteractionMode: DEFAULT_CHART_INTERACTION_MODE,
  },
);

const emit = defineEmits<{
  'update:chartInteractionMode': [mode: ChartInteractionMode];
}>();

const currentMarketStore = useCurrentMarketStore();
const modalStore = useModalStore();
const currentSymbol = computed(() => currentMarketStore.symbol);
const selectedChartInteractionModeColor = designTokens.color.interactiveHover;

function isChartInteractionModeSelected(mode: ChartInteractionMode): boolean {
  return props.chartInteractionMode === mode;
}

function chartInteractionModeIconColor(
  mode: ChartInteractionMode,
): string | undefined {
  return isChartInteractionModeSelected(mode)
    ? selectedChartInteractionModeColor
    : undefined;
}

function selectChartInteractionMode(mode: ChartInteractionMode): void {
  emit('update:chartInteractionMode', mode);
}
</script>

<style scoped>
#wrapper-select {
  flex-shrink: 0;
  margin-bottom: var(--design-space-xl);
  display: flex;
  gap: var(--design-space-md);
  flex-wrap: wrap;
}

.chart-interaction-controls {
  display: flex;
  align-items: center;
  gap: var(--design-space-sm);
  margin-left: auto;
}
</style>
