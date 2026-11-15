import { nextTick, type Ref } from 'vue';
import type { createChartRendering } from '../chartRendering';
import type { useCandlesticksStore } from '@/stores/candlesticksStore';
import type { useTradeNavigationStore } from '@/stores/tradeNavigationStore';
import type {
  ChartSession,
  ChartSessionKeyInput,
  ChartSessionLiveCandleReceiver,
} from '../chartSession';

export function createLatestChart(options: {
  session: ChartSession;
  navigation: ReturnType<typeof useTradeNavigationStore>;
  key: () => ChartSessionKeyInput;
  receive: ChartSessionLiveCandleReceiver;
  rendering: ReturnType<typeof createChartRendering>;
  candles: ReturnType<typeof useCandlesticksStore>;
  loadedSession: Ref<string | null>;
  sync: () => void;
}) {
  let pending = false;
  return {
    get pending() {
      return pending;
    },
    async open() {
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
      await options.session.setSession(options.key(), options.receive);
    },
  };
}
