import { fetchCandles as fetchHistoricalCandles } from '@/api/candleClient';
import { wsService } from '@/utils/websocketService';
import { timeframeToMinutes } from '@/utils/timeframes';
import type { useCandlesticksStore } from '@/stores/candlesticksStore';
import type { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { ChartCandle } from '@/types/contracts';
import type {
  ChartSessionKey,
  ChartSessionKeyInput,
  ChartSessionSubscriptionsAdapter,
} from './chartSession';

interface ChartSessionAdapterOptions {
  candlesticksStore: ReturnType<typeof useCandlesticksStore>;
  indicatorsStore: ReturnType<typeof useIndicatorsStore>;
  currentChartSessionKey: () => ChartSessionKeyInput;
  renderCandlesticks: (
    candles: readonly ChartCandle[],
    options?: { scrollToRealtime?: boolean },
  ) => void;
  shouldScrollToRealTime: () => boolean;
}

export function createChartSessionAdapter({
  candlesticksStore,
  indicatorsStore,
  currentChartSessionKey,
  renderCandlesticks,
  shouldScrollToRealTime,
}: ChartSessionAdapterOptions): ChartSessionSubscriptionsAdapter {
  const indicatorBatchSize = 500;
  const candlesFetchLimit = 500;

  indicatorsStore.configureHistoryCoverage({
    batchSize: indicatorBatchSize,
    getLoadedCandleRange: () => {
      const key = currentChartSessionKey();
      return key.timeframe
        ? getIndicatorLoadedCandleRange(key.timeframe)
        : null;
    },
  });

  const indicatorCoverageOptions = (key: ChartSessionKey) => ({
    batchSize: indicatorBatchSize,
    getLoadedCandleRange: () => getIndicatorLoadedCandleRange(key.timeframe),
  });

  return {
    subscribeCandles: (key) =>
      wsService.send('subscribeCandles', {
        symbol: key.symbol,
        timeframe: key.timeframe,
      }),
    unsubscribeCandles: (key) =>
      wsService.send('unsubscribeCandles', {
        symbol: key.symbol,
        timeframe: key.timeframe,
      }),
    onCandleUpdate: (handler) => {
      wsService.on('candleUpdate', handler);
    },
    offCandleUpdate: (handler) => {
      wsService.off('candleUpdate', handler);
    },
    fetchCandles: (key) =>
      fetchHistoricalCandles(key.symbol, key.timeframe, {
        limit: candlesFetchLimit,
        exchange: key.exchange,
      }),
    renderCandles: (_key, candles) => {
      candlesticksStore.replace(candles);
      renderCandlesticks(candlesticksStore.data, {
        scrollToRealtime: shouldScrollToRealTime(),
      });
    },
    requestIndicators: (key) => {
      indicatorsStore.requestAllIndicators(
        key.symbol,
        key.timeframe,
        key.exchange,
        indicatorCoverageOptions(key),
      );
    },
    unsubscribeIndicators: () => indicatorsStore.unsubscribeAllLive(),
    getOldestCandleTimestampMs: () => {
      return candlesticksStore.data[0]?.timestamp_ms ?? null;
    },
    fetchOlderCandles: (key, endMs) =>
      fetchHistoricalCandles(key.symbol, key.timeframe, {
        endMs,
        limit: candlesFetchLimit,
        exchange: key.exchange,
      }),
    prependOlderCandles: (_key, candles) => {
      candlesticksStore.prepend(candles);
    },
    renderOlderCandles: (key) => {
      renderCandlesticks(candlesticksStore.data);
      void indicatorsStore.ensureCoverageForAll(
        key.symbol,
        key.timeframe,
        key.exchange,
        indicatorCoverageOptions(key),
      );
    },
    requestOlderIndicators: (key) => {
      return indicatorsStore.ensureCoverageForAll(
        key.symbol,
        key.timeframe,
        key.exchange,
        indicatorCoverageOptions(key),
      );
    },
    resetIndicatorHistory: () => {
      indicatorsStore.resetHistoryFlags();
    },
    reportCandleFetchError: (_key, error) => {
      console.error('Failed to fetch candlestick data:', error);
    },
    reportOlderCandleFetchError: (_key, error) => {
      console.error('Failed to fetch older candlestick data:', error);
    },
    reportOlderIndicatorFetchError: (_key, error) => {
      console.error('Failed to fetch older indicator data:', error);
    },
    reportLiveTailBufferOverflow: (key, candle) => {
      console.error(
        'Live candle tail buffer overflow; refetching chart session.',
        {
          candle,
          key,
        },
      );
    },
    reportSubscriptionError: (operation, _key, error) => {
      console.error(`Failed to ${operation} candle subscription:`, error);
    },
  };

  function getIndicatorLoadedCandleRange(timeframe: string) {
    const firstCandle = candlesticksStore.data[0];
    const lastCandle =
      candlesticksStore.data[candlesticksStore.data.length - 1];
    if (!firstCandle || !lastCandle) return null;

    return {
      oldestTimestampMs: firstCandle.timestamp_ms,
      newestTimestampMs: lastCandle.timestamp_ms,
      exclusiveEndMs:
        lastCandle.timestamp_ms + timeframeToMinutes(timeframe) * 60_000,
    };
  }
}
