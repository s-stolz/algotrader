import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { ChartInfrastructure } from '@/utils/chart';
import { nextTick, type Ref } from 'vue';
import type { createChartRendering } from '../chartRendering';
import type { useCandlesticksStore } from '@/stores/candlesticksStore';
import type { useTradeNavigationStore } from '@/stores/tradeNavigationStore';
import type { ChartSession, ChartSessionKeyInput } from '../chartSession';

export function createLatestChart(options: {
  session: ChartSession;
  infrastructure: ChartInfrastructure;
  navigation: ReturnType<typeof useTradeNavigationStore>;
  key: () => ChartSessionKeyInput;
  rendering: ReturnType<typeof createChartRendering>;
  candles: ReturnType<typeof useCandlesticksStore>;
  loadedSession: Ref<string | null>;
  sync: () => void;
}) {
  const indicators = useIndicatorsStore();
  let pending = false;
  return {
    get pending() {
      return pending;
    },
    async open() {
      if (pending) return;
      if (
        !indicators.historicalMode &&
        options.loadedSession.value &&
        options.candles.data.length
      ) {
        const range = options.rendering.state.latestVisibleRange;
        const latest = options.candles.data.length - 1;
        if (!range || latest < range.from || latest > range.to)
          options.infrastructure.chartManager.chart
            ?.timeScale()
            .scrollToPosition(0, false);
        return;
      }
      pending = true;
      options.navigation.cancel();
      const revision = options.navigation.revision;
      options.loadedSession.value = null;
      options.rendering.resetIndicatorReadouts();
      options.rendering.state.pendingIndicatorMessages.clear();
      options.rendering.state.shouldScrollToRealTime = true;
      options.candles.clear();
      options.rendering.renderCandlesticks([]);
      // Let cancellation watchers finish before starting the replacement session.
      await nextTick();
      pending = false;
      if (revision !== options.navigation.revision) return options.sync();
      await options.session.stop();
      if (revision !== options.navigation.revision) return options.sync();
      await options.session.setSession(
        options.key(),
        options.rendering.updateCurrentCandle,
      );
    },
  };
}
