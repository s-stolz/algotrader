<template>
  <div class="chart-wrapper">
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
            v-if="!backtestOverlayStore.matchesChart || runIndicatorError"
            text
            circle
            title="Restore backtest view"
            aria-label="Restore backtest view"
            @click="restoreBacktestView"
            ><n-icon size="20"><SyncOutline /></n-icon
          ></n-button>
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
        <div
          v-if="runIndicatorError"
          class="backtest-overlay-error"
          role="alert"
          >{{ runIndicatorError }}</div
        >
      </div>
    </Teleport>

    <ChartGoLive
      :ready="chartReady"
      :loading="tradeNavigation.loading"
      @activate="goToLatest"
    />

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
        :readout="indicatorReadouts[indicator._id]"
        :indicator-manager="indicatorManager"
      />
    </div>
  </div>
</template>

<script lang="ts">
import {
  createMarketSessionKey,
  chartSessionIdentity,
} from './chartSessionIdentity';
import {
  computed,
  defineComponent,
  getCurrentInstance,
  markRaw,
  onBeforeUnmount,
  onActivated,
  onDeactivated,
  onMounted,
  ref,
  toRefs,
  watch,
  type PropType,
} from 'vue';
import { NButton, NIcon } from 'naive-ui';
import ChartGoLive from './trade-navigation/ChartGoLive.vue';
import { createLatestChart } from './trade-navigation/latestChart';
import { TradeHistory } from './trade-navigation/tradeHistory';
import { waitForIndicatorRequest } from '@/stores/indicators/pendingRequests';
import { createTradeHistoryAdapter } from './trade-navigation/tradeHistoryAdapter';
import { useTradeNavigationStore } from '@/stores/tradeNavigationStore';
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
import { createBacktestIndicators } from './backtestIndicators';
import { timeframeToMinutes } from '@/utils/timeframes';
import {
  DEFAULT_CHART_INTERACTION_MODE,
  type ChartInteractionMode,
} from './chartInteractionMode';
import Indicator from './Indicator/Indicator.vue';
import CloseCircleOutline from '@vicons/ionicons5/es/CloseCircleOutline';
import SyncOutline from '@vicons/ionicons5/es/SyncOutline';

export default defineComponent({
  name: 'ChartArea',
  components: {
    ChartGoLive,
    CloseCircleOutline,
    SyncOutline,
    Indicator,
    NButton,
    NIcon,
  },
  props: {
    interactionMode: {
      type: String as PropType<ChartInteractionMode>,
      default: DEFAULT_CHART_INTERACTION_MODE,
    },
  },
  emits: ['candles-loaded'],
  setup(props, { expose, emit }) {
    const tradeNavigation = useTradeNavigationStore();
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
      canShowBacktest: () => loadedSession.value === sessionIdentity(),
      canReadIndicators: () => loadedSession.value === sessionIdentity(),
      requestOlderHistory: (request) => session.requestOlderHistory(request),
    });
    function currentChartSessionKey(): ChartSessionKeyInput {
      return createMarketSessionKey(
        currentMarketStore,
        currentTimeframeStore.value,
      );
    }
    const loadedSession = ref<string | null>(null);
    const sessionIdentity = (key = currentChartSessionKey()) =>
      chartSessionIdentity(key);
    const runIndicators = createBacktestIndicators({
      store: indicatorsStore,
      manager: infrastructure.indicatorManager,
      getRange: () => {
        const first = candlesticksStore.data[0];
        const last = candlesticksStore.data.at(-1);
        const timeframe = currentTimeframeStore.value;
        return first && last && timeframe
          ? {
              oldestTimestampMs: first.timestamp_ms,
              newestTimestampMs: last.timestamp_ms,
              exclusiveEndMs:
                last.timestamp_ms + timeframeToMinutes(timeframe) * 60_000,
            }
          : null;
      },
    });
    let active = true;
    let runIndicatorLoad: Promise<void> = Promise.resolve();
    function syncRunIndicators() {
      const run = backtestOverlayStore.selectedRun;
      runIndicators.invalidate(backtestOverlayStore.selectedRunId);
      rendering.refreshBacktestMarkers();
      const key = currentChartSessionKey();
      if (
        active &&
        run &&
        backtestOverlayStore.matchesChart &&
        rendering.state.isReady &&
        loadedSession.value === sessionIdentity() &&
        key.symbol &&
        key.timeframe
      ) {
        runIndicatorLoad = runIndicators.load(run, {
          symbol: key.symbol,
          timeframe: key.timeframe,
          exchange: key.exchange ?? null,
        });
      }
    }
    function restoreBacktestView() {
      backtestOverlayStore.restoreChartView();
      syncRunIndicators();
    }
    const session = markRaw(
      createChartSession(
        createChartSessionAdapter({
          candlesticksStore,
          indicatorsStore,
          tradeHistory: new TradeHistory(
            createTradeHistoryAdapter({
              candles: candlesticksStore,
              indicators: indicatorsStore,
              infrastructure,
              render: rendering.renderCandlesticks,
              reset: () => resetNavigation(false),
              initializeIndicators: async (key) => {
                loadedSession.value = sessionIdentity(key);
                indicatorsStore.requestAllIndicators(
                  key.symbol,
                  key.timeframe,
                  key.exchange,
                );
                await Promise.all([
                  runIndicatorLoad,
                  ...indicatorsStore.all.map(waitForIndicatorRequest),
                ]);
              },
              loading: (value) => {
                tradeNavigation.loading = value;
              },
            }),
          ),
          currentChartSessionKey,
          renderCandlesticks: rendering.renderCandlesticks,
          shouldScrollToRealTime: () => rendering.state.shouldScrollToRealTime,
          onCandlesLoaded: (key) => {
            loadedSession.value = sessionIdentity(key);
            emit('candles-loaded');
          },
        }),
      ),
    );
    const latestChart = createLatestChart({
      session,
      infrastructure,
      navigation: tradeNavigation,
      key: currentChartSessionKey,
      sync: syncChartSession,
      rendering,
      candles: candlesticksStore,
      loadedSession,
      reset: resetNavigation,
    });
    let consumedDestination: number | null = null;
    function syncChartSession() {
      if (
        !active ||
        latestChart.pending ||
        (tradeNavigation.preparing && !tradeNavigation.destination)
      )
        return;
      const destination = tradeNavigation.destination;
      if (
        destination &&
        destination.id !== consumedDestination &&
        !rendering.state.isReady
      )
        return;
      const timestamp =
        destination &&
        destination.id !== consumedDestination &&
        destination.runId === backtestOverlayStore.selectedRunId &&
        backtestOverlayStore.matchesChart &&
        rendering.state.isReady
          ? destination.timestampMs
          : undefined;
      if (timestamp !== undefined) consumedDestination = destination!.id;
      void session.setSession(
        currentChartSessionKey(),
        rendering.updateCurrentCandle,
        timestamp,
      );
    }
    watch(
      () => currentMarketStore.min_move,
      (minMove) => {
        if (minMove && minMove > 0) infrastructure.setMinMove(minMove);
      },
    );
    function resetNavigation(scrollToRealtime: boolean) {
      loadedSession.value = null;
      rendering.resetIndicatorReadouts();
      rendering.state.pendingIndicatorMessages.clear();
      rendering.state.shouldScrollToRealTime = scrollToRealtime;
    }
    function syncNavigation() {
      resetNavigation(true);
      syncChartSession();
    }
    watch(() => sessionIdentity(), syncNavigation);
    syncNavigation();
    watch(
      () => [
        backtestOverlayStore.selectedRun,
        backtestOverlayStore.selectedRunId,
        sessionIdentity(),
        loadedSession.value,
        rendering.state.isReady,
      ],
      syncRunIndicators,
      { immediate: true, flush: 'sync' },
    );
    watch(
      () => backtestOverlayStore.selectedRunId,
      (runId) => {
        if (
          tradeNavigation.destination &&
          tradeNavigation.destination.runId !== runId
        )
          tradeNavigation.cancel();
        rendering.refreshBacktestMarkers();
      },
    );
    watch(
      () => backtestOverlayStore.closedTrades,
      rendering.refreshBacktestMarkers,
    );
    watch(() => props.interactionMode, measurement.applyInteractionMode);
    watch(
      () => tradeNavigation.revision,
      () => {
        loadedSession.value = null;
        void session.stop();
        runIndicators.invalidate(backtestOverlayStore.selectedRunId);
      },
    );
    watch(
      () => [
        tradeNavigation.destination,
        tradeNavigation.preparing,
        rendering.state.isReady,
      ],
      syncChartSession,
    );
    onActivated(() => {
      active = true;
      syncChartSession();
    });
    onDeactivated(() => {
      active = false;
      loadedSession.value = null;
      tradeNavigation.cancel();
      runIndicators.invalidate(backtestOverlayStore.selectedRunId);
      void session.stop();
    });
    onMounted(rendering.initializeChartComponent);
    onBeforeUnmount(() => {
      runIndicators.dispose();
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
    const { backtestOverlayTarget, shouldScrollToRealTime, indicatorReadouts } =
      toRefs(rendering.state);
    expose({
      shouldScrollToRealTime,
      onWheelPassive: rendering.onWheelPassive,
    });
    return {
      tradeNavigation,
      goToLatest: latestChart.open,
      chartContainer,
      restoreBacktestView,
      runIndicatorError: runIndicators.error,
      backtestOverlayStore,
      backtestOverlayTarget,
      activeBacktestRunTitle,
      indicatorReadouts,
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
.chart-wrapper {
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

.backtest-overlay-error {
  margin-top: var(--design-space-xs);
  padding: var(--design-space-sm) var(--design-space-md);
  color: var(--design-color-body);
  font-size: var(--design-text-secondary);
  background: var(--design-color-panel);
  border-radius: var(--design-radius-panel);
  pointer-events: none;
}

.backtest-overlay-panel {
  display: flex;
  align-items: center;
  gap: var(--design-space-sm);
  box-sizing: border-box;
  width: max-content;
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
  align-items: baseline;
  flex: 1 1 auto;
  gap: var(--design-space-xs) var(--design-space-sm);
  min-width: 0;
}

.backtest-overlay-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
  color: var(--design-color-body);
}

.backtest-overlay-context {
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
  top: calc(var(--design-space-xs) - var(--design-space-xl));
  left: 0;
}

.legend-value {
  margin-right: 10px;
}
</style>
