import {
  chartAreaMocks,
  indicatorInfo,
  candle,
  eurUsdM5Key,
  setupStores,
  mountChartArea,
  latestChartSession,
  latestChartSessionAdapter,
  latestLiveCandleReceiver,
  setupChartAreaTests,
} from './ChartArea.fixtures';
import { flushPromises } from '@vue/test-utils';
import { type ComponentPublicInstance } from 'vue';
import { describe, expect, it, vi } from 'vitest';
import {
  type CandleUpdateMessage,
  type IndicatorUpdateMessage,
} from '@/types/contracts';
import { fetchCandles } from '@/api/candleClient';
import { type ChartLogicalRange } from '@/utils/chart';

describe('ChartArea sessions', () => {
  setupChartAreaTests();

  it('syncs market and timeframe changes into the chart session', async () => {
    const { currentMarketStore, currentTimeframeStore } = setupStores('M5');
    mountChartArea();
    await flushPromises();

    const session = latestChartSession();

    expect(session.setSession).toHaveBeenLastCalledWith(
      eurUsdM5Key,
      expect.any(Function),
    );

    currentTimeframeStore.setCurrentTimeframe({ label: 'H1', value: 'H1' });
    await flushPromises();

    expect(session.setSession).toHaveBeenLastCalledWith(
      { ...eurUsdM5Key, timeframe: 'H1' },
      expect.any(Function),
    );

    currentMarketStore.setMarket({
      symbol_id: 2,
      symbol: 'GBPUSD',
      exchange: 'CFD',
      market_type: 'forex',
      min_move: 0.0001,
      timezone: 'UTC',
    });
    await flushPromises();

    expect(session.setSession).toHaveBeenLastCalledWith(
      { symbol: 'GBPUSD', exchange: 'CFD', timeframe: 'H1' },
      expect.any(Function),
    );
  });

  it('renders live Candle receiver updates', async () => {
    const { candlesticksStore } = setupStores('M5');
    mountChartArea();
    await flushPromises();
    chartAreaMocks.infrastructure.updateCandlestick.mockClear();

    const message: CandleUpdateMessage = {
      type: 'candleUpdate',
      symbol: 'EURUSD',
      timeframe: 'M5',
      timestamp_ms: 600_000,
      open: 2,
      high: 3,
      low: 1.8,
      close: 2.5,
      volume: 5,
    };

    latestLiveCandleReceiver()(message);

    expect(candlesticksStore.data).toEqual([
      candle(300_000),
      expect.objectContaining({ timestamp_ms: 600_000, time: 600, close: 2.5 }),
    ]);
    expect(
      chartAreaMocks.infrastructure.updateCandlestick,
    ).toHaveBeenCalledWith(
      expect.objectContaining({ timestamp_ms: 600_000, time: 600, close: 2.5 }),
    );
  });

  it('adapts stores, WebSocket, and chart rendering to the session', async () => {
    const { candlesticksStore, indicatorsStore } = setupStores('M5');
    mountChartArea();
    await flushPromises();
    const adapter = latestChartSessionAdapter();
    const handler = vi.fn();

    await adapter.subscribeCandles(eurUsdM5Key);
    await adapter.unsubscribeCandles(eurUsdM5Key);
    adapter.onCandleUpdate(handler);
    adapter.offCandleUpdate(handler);
    await adapter.fetchCandles(eurUsdM5Key);
    await adapter.renderCandles(eurUsdM5Key, [candle(600_000, 2.5)]);
    await adapter.requestIndicators(eurUsdM5Key);
    await adapter.unsubscribeIndicators();
    await adapter.fetchOlderCandles(eurUsdM5Key, 300_000);
    await adapter.requestOlderIndicators(eurUsdM5Key);
    adapter.resetIndicatorHistory?.();

    expect(chartAreaMocks.wsSend).toHaveBeenCalledWith('subscribeCandles', {
      symbol: 'EURUSD',
      timeframe: 'M5',
    });
    expect(chartAreaMocks.wsSend).toHaveBeenCalledWith('unsubscribeCandles', {
      symbol: 'EURUSD',
      timeframe: 'M5',
    });
    expect(chartAreaMocks.wsOn).toHaveBeenCalledWith('candleUpdate', handler);
    expect(chartAreaMocks.wsOff).toHaveBeenCalledWith('candleUpdate', handler);
    expect(fetchCandles).toHaveBeenCalledWith('EURUSD', 'M5', {
      limit: 500,
      exchange: 'FX',
    });
    expect(fetchCandles).toHaveBeenCalledWith('EURUSD', 'M5', {
      endMs: 300_000,
      limit: 500,
      exchange: 'FX',
    });
    expect(candlesticksStore.data).toEqual([candle(600_000, 2.5)]);
    expect(
      chartAreaMocks.infrastructure.addCandlestickData,
    ).toHaveBeenCalledWith(
      [candle(600_000, 2.5)],
      expect.objectContaining({
        priceFormat: expect.objectContaining({ minMove: 0.0001, precision: 4 }),
      }),
    );
    expect(indicatorsStore.requestAllIndicators).toHaveBeenCalledWith(
      'EURUSD',
      'M5',
      'FX',
      expect.objectContaining({
        batchSize: 500,
        getLoadedCandleRange: expect.any(Function),
      }),
    );
    expect(indicatorsStore.unsubscribeAllLive).toHaveBeenCalled();
    expect(indicatorsStore.ensureCoverageForAll).toHaveBeenCalledWith(
      'EURUSD',
      'M5',
      'FX',
      expect.objectContaining({
        batchSize: 500,
        getLoadedCandleRange: expect.any(Function),
      }),
    );
    expect(indicatorsStore.resetHistoryFlags).toHaveBeenCalled();
    expect(adapter.getOldestCandleTimestampMs()).toBe(600_000);

    const requestCoverageOptions = vi.mocked(
      indicatorsStore.requestAllIndicators,
    ).mock.calls[0][3]!;
    expect(requestCoverageOptions.getLoadedCandleRange?.()).toEqual({
      oldestTimestampMs: 600_000,
      newestTimestampMs: 600_000,
      exclusiveEndMs: 900_000,
    });
  });

  it('bridges visible range events into the chart session after wheel settling', async () => {
    setupStores('M5');
    const wrapper = mountChartArea();
    await flushPromises();
    const vm = wrapper.vm as unknown as ComponentPublicInstance & {
      onWheelPassive: () => void;
      shouldScrollToRealTime: boolean;
    };
    vm.shouldScrollToRealTime = false;
    chartAreaMocks.ohlcSeriesInfo.series.barsInLogicalRange.mockReturnValue({
      barsBefore: 99,
      barsAfter: 0,
    });

    chartAreaMocks.visibleRangeHandler?.({
      from: 0,
      to: 10,
    } as ChartLogicalRange);

    expect(latestChartSession().requestOlderHistory).toHaveBeenCalledWith({
      barsBefore: 99,
      nowMs: 1_000,
      scrollToRealtime: false,
    });

    latestChartSession().requestOlderHistory.mockClear();
    vm.onWheelPassive();
    chartAreaMocks.visibleRangeHandler?.({
      from: 0,
      to: 10,
    } as ChartLogicalRange);

    expect(latestChartSession().requestOlderHistory).not.toHaveBeenCalled();
  });

  it('batches indicator live messages and flushes the latest point to the manager', async () => {
    const { indicatorsStore } = setupStores('M5');
    vi.spyOn(Date, 'now').mockReturnValue(12345);
    const indicatorId = indicatorsStore.addIndicator(indicatorInfo, [], 1);
    mountChartArea();
    await flushPromises();

    const message: IndicatorUpdateMessage = {
      type: 'indicatorUpdate',
      clientIndicatorId: indicatorId,
      timestamp_ms: 1_000,
      values: { sma: 1.2 },
    };

    for (const handler of chartAreaMocks.indicatorHandlers) {
      handler(message);
    }

    expect(
      chartAreaMocks.infrastructure.indicatorManager.updateIndicatorSeriesPoint,
    ).toHaveBeenCalledWith(indicatorId, {
      timestamp_ms: 1_000,
      sma: 1.2,
    });
  });
});
