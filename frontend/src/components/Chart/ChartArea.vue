<template>
  <DesignScope>
    <div id="chart-wrapper">
      <div
        ref="chartContainer"
        id="lightweight-chart"
        class="chart-container"
        :class="{
          'chart-container--measure-mode': interactionMode === 'measure',
        }"
      />

      <Teleport
        v-if="backtestOverlayStore.selectedRun && backtestOverlayTarget"
        :to="backtestOverlayTarget"
      >
        <div class="backtest-overlay-container">
          <div class="backtest-overlay-panel">
            <div class="backtest-overlay-details">
              <span class="backtest-overlay-title">{{
                activeBacktestRunTitle
              }}</span>
              <span class="backtest-overlay-context">{{
                activeBacktestRunContext
              }}</span>
            </div>
            <n-button
              text
              circle
              class="backtest-overlay-remove"
              data-testid="remove-backtest-overlay"
              aria-label="Remove Backtest Run overlay"
              @click="removeBacktestOverlay"
            >
              <n-icon size="20">
                <CloseCircleOutline />
              </n-icon>
            </n-button>
          </div>
          <div class="backtest-marker-legend"
            >↑ ↓ Entry · ● Exit · Green Buy · Red Sell</div
          >
          <div
            v-if="hoveredBacktestMarker"
            class="backtest-marker-details"
            role="tooltip"
          >
            {{ hoveredBacktestMarker }}
          </div>
        </div>
      </Teleport>

      <span class="legend">
        <span class="legend-value">O: <span ref="legendOpen">-</span></span>
        <span class="legend-value">H: <span ref="legendHigh">-</span></span>
        <span class="legend-value">L: <span ref="legendLow">-</span></span>
        <span class="legend-value">C: <span ref="legendClose">-</span></span>
      </span>

      <div v-if="chartReady">
        <indicator
          v-for="indicator in getAllIndicators()"
          :key="indicator._id"
          :indicator="indicator"
          :indicator-manager="indicatorManager"
        />
      </div>
    </div>
  </DesignScope>
</template>

<script lang="ts">
import DesignScope from '@/components/Common/DesignScope.vue';
import {
  computed,
  defineComponent,
  getCurrentInstance,
  markRaw,
  onBeforeUnmount,
  onMounted,
  ref,
  toRefs,
  watch,
  type PropType,
} from 'vue';
import { NButton, NIcon } from 'naive-ui';
import { useCandlesticksStore } from '@/stores/candlesticksStore';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import { createChartInfrastructure } from '@/utils/chart';
import { createChartSession, type ChartSessionKeyInput } from './chartSession';
import { createChartSessionAdapter } from './chartSessionAdapter';
import { createChartRendering } from './chartRendering';
import { createChartMeasurement } from './chartMeasurement';
import {
  DEFAULT_CHART_INTERACTION_MODE,
  type ChartInteractionMode,
} from './chartInteractionMode';
import Indicator from './Indicator/Indicator.vue';
import { CloseCircleOutline } from '@/icons';

export default defineComponent({
  name: 'ChartArea',
  components: { CloseCircleOutline, DesignScope, Indicator, NButton, NIcon },
  props: {
    interactionMode: {
      type: String as PropType<ChartInteractionMode>,
      default: DEFAULT_CHART_INTERACTION_MODE,
    },
  },
  setup(props, { expose }) {
    const candlesticksStore = useCandlesticksStore();
    const indicatorsStore = useIndicatorsStore();
    const currentMarketStore = useCurrentMarketStore();
    const currentTimeframeStore = useCurrentTimeframeStore();
    const backtestOverlayStore = useBacktestOverlayStore();
    const infrastructure = markRaw(createChartInfrastructure());
    const chartContainer = ref<HTMLElement | null>(null);
    const instance = getCurrentInstance();
    const measurement = createChartMeasurement({
      infrastructure,
      getMode: () => props.interactionMode,
      getMinMove: () => currentMarketStore.min_move,
      hasCandles: () => candlesticksStore.data.length > 0,
      hasSeries: () => rendering.state.ohlcSeriesRef !== null,
    });
    const rendering = createChartRendering({
      infrastructure,
      candlesticksStore,
      indicatorsStore,
      backtestOverlayStore,
      measurement,
      getChartContainer: () => chartContainer.value,
      getMinMove: () => currentMarketStore.min_move,
      getLegendElements: () => instance?.refs ?? {},
      requestOlderHistory: (request) => session.requestOlderHistory(request),
    });
    function currentChartSessionKey(): ChartSessionKeyInput {
      return {
        symbol: currentMarketStore.symbol,
        exchange: currentMarketStore.exchange,
        timeframe: currentTimeframeStore.value,
      };
    }
    const session = markRaw(
      createChartSession(
        createChartSessionAdapter({
          candlesticksStore,
          indicatorsStore,
          currentChartSessionKey,
          renderCandlesticks: rendering.renderCandlesticks,
          shouldScrollToRealTime: () => rendering.state.shouldScrollToRealTime,
        }),
      ),
    );
    function syncChartSession() {
      void session.setSession(
        currentChartSessionKey(),
        rendering.updateCurrentCandle,
      );
    }
    watch(
      () => currentMarketStore.min_move,
      (minMove) => {
        if (minMove && minMove > 0) infrastructure.setMinMove(minMove);
      },
    );
    function syncNavigation() {
      rendering.state.shouldScrollToRealTime = true;
      syncChartSession();
    }
    watch(
      () =>
        `${currentMarketStore.symbol || ''}|${currentMarketStore.exchange || ''}`,
      syncNavigation,
    );
    watch(() => currentTimeframeStore.value, syncNavigation);
    syncNavigation();
    watch(
      () => backtestOverlayStore.selectedRunId,
      rendering.refreshBacktestMarkers,
    );
    watch(
      () => backtestOverlayStore.closedTrades,
      rendering.refreshBacktestMarkers,
    );
    watch(() => props.interactionMode, measurement.applyInteractionMode);
    onMounted(rendering.initializeChartComponent);
    onBeforeUnmount(() => {
      void session.stop();
      rendering.dispose();
      indicatorsStore.configureHistoryCoverage(null);
      infrastructure.cleanup();
    });
    const activeBacktestRunTitle = computed(
      () =>
        backtestOverlayStore.selectedRun?.request.strategy.strategy_id ?? '',
    );
    const activeBacktestRunContext = computed(() => {
      const run = backtestOverlayStore.selectedRun;
      if (!run) return '';
      const symbol = run.request.symbols[0] ?? 'unknown';
      const market = run.request.exchange
        ? `${run.request.exchange}:${symbol}`
        : symbol;
      return `${run.request.timeframe} ${market}`;
    });
    const {
      backtestOverlayTarget,
      hoveredBacktestMarker,
      shouldScrollToRealTime,
    } = toRefs(rendering.state);
    expose({
      shouldScrollToRealTime,
      onWheelPassive: rendering.onWheelPassive,
    });
    return {
      chartContainer,
      backtestOverlayStore,
      backtestOverlayTarget,
      hoveredBacktestMarker,
      activeBacktestRunTitle,
      activeBacktestRunContext,
      chartReady: computed(() => rendering.state.isReady),
      indicatorManager: infrastructure.indicatorManager,
      getAllIndicators: () => indicatorsStore.all,
      removeBacktestOverlay: rendering.removeBacktestOverlay,
    };
  },
});
</script>

<style scoped>
#chart-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.chart-container {
  width: 100%;
  height: 100%;
}

.chart-container--measure-mode,
.chart-container--measure-mode :deep(*) {
  cursor: crosshair;
}

.backtest-overlay-container {
  margin-bottom: var(--design-space-sm);
}

.backtest-marker-legend,
.backtest-marker-details {
  padding: var(--design-space-sm) var(--design-space-md);
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
  background: var(--design-color-panel);
  border-radius: var(--design-radius-panel);
  pointer-events: none;
}

.backtest-marker-details {
  margin-top: var(--design-space-xs);
  color: var(--design-color-body);
}

.backtest-overlay-panel {
  display: flex;
  align-items: center;
  gap: var(--design-space-sm);
  min-width: 300px;
  width: min(350px, calc(100vw - 20px));
  max-width: 100%;
  padding: var(--design-space-sm) var(--design-space-md);
  color: var(--design-color-muted);
  font-size: var(--design-text-body);
  line-height: 1.3;
  background: var(--design-color-panel);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
}

.backtest-overlay-details {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  flex: 1 1 auto;
  gap: var(--design-space-xs) var(--design-space-sm);
  min-width: 0;
}

.backtest-overlay-title {
  font-weight: 700;
  color: var(--design-color-body);
}

.backtest-overlay-context {
  flex: 1 1 160px;
  min-width: 0;
  overflow: hidden;
  color: var(--design-color-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.backtest-overlay-remove {
  flex: 0 0 auto;
  color: var(--design-color-body);
}

.backtest-overlay-remove:hover {
  color: var(--design-color-error);
}

.legend {
  color: var(--design-color-body);
  font-size: var(--design-text-secondary);
  font-variant-numeric: tabular-nums;
  position: absolute;
  top: 50px;
  left: 10px;
}

.legend-value {
  margin-right: 10px;
}
</style>
