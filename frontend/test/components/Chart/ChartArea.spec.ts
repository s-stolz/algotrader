import { flushPromises, mount } from '@vue/test-utils';
import type { ComponentPublicInstance } from 'vue';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  CandleUpdateMessage,
  ChartCandle,
  IndicatorInfo,
  IndicatorUpdateMessage,
  TimeframeCode,
} from '@/types/contracts';
import { fetchCandles } from '@/api/candleClient';
import { useCandlesticksStore } from '@/stores/candlesticksStore';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { ChartLogicalRange } from '@/utils/chart';

import ChartArea from '@/components/Chart/ChartArea.vue';
import type {
  ChartSessionKey,
  ChartSessionSubscriptionsAdapter,
} from '@/components/Chart/chartSession';

interface MockCrosshairParam {
  time: number;
  point: { x: number; y: number };
  seriesData: Map<object, object>;
}

type MockCrosshairHandler = (param: MockCrosshairParam) => void;
type MockMessageHandler = (message: CandleUpdateMessage | IndicatorUpdateMessage) => void;

const chartAreaMocks = vi.hoisted(() => {
  const ohlcSeries = { id: 'ohlc-series' };
  const ohlcSeriesInfo = {
    series: {
      barsInLogicalRange: vi.fn(() => ({ barsBefore: 50, barsAfter: 0 })),
    },
    type: 'candlestick',
    data: [],
    options: {},
  };
  const seriesMap = new Map([['ohlc', ohlcSeriesInfo]]);
  const indicatorManager = {
    addIndicatorSeries: vi.fn(),
    refreshIndicatorSeries: vi.fn(),
    removeIndicatorSeriesAndData: vi.fn(),
    updateIndicatorStyles: vi.fn(),
    updateIndicatorSeriesPoint: vi.fn(),
    updateMissingPaneHtmlElements: vi.fn(),
  };
  const infrastructure = {
    chartManager: {},
    indicatorManager,
    chartInitialized: false,
    chartError: null,
    init: vi.fn(() => true),
    getSeries: vi.fn(() => seriesMap),
    addCandlestickData: vi.fn(() => ohlcSeries),
    updateCandlestick: vi.fn(() => true),
    setMinMove: vi.fn(() => true),
    subscribeCrosshairMove: vi.fn((handler) => {
      chartAreaMocks.crosshairHandler = handler;
    }),
    unsubscribeCrosshairMove: vi.fn(),
    subscribeVisibleLogicalRangeChange: vi.fn((handler) => {
      chartAreaMocks.visibleRangeHandler = handler;
    }),
    unsubscribeVisibleLogicalRangeChange: vi.fn(),
    scrollToRealTime: vi.fn(),
    cleanup: vi.fn(),
  };

  return {
    chartSessionAdapters: [] as unknown[],
    chartSessions: [] as Array<{
      requestOlderHistory: ReturnType<typeof vi.fn>;
      setSession: ReturnType<typeof vi.fn>;
      stop: ReturnType<typeof vi.fn>;
    }>,
    crosshairHandler: null as MockCrosshairHandler | null,
    createChartSession: vi.fn((adapter: unknown) => {
      const session = {
        requestOlderHistory: vi.fn(),
        setSession: vi.fn(() => Promise.resolve()),
        stop: vi.fn(() => Promise.resolve()),
      };

      chartAreaMocks.chartSessionAdapters.push(adapter);
      chartAreaMocks.chartSessions.push(session);

      return session;
    }),
    indicatorHandlers: new Set<MockMessageHandler>(),
    infrastructure,
    ohlcSeries,
    ohlcSeriesInfo,
    visibleRangeHandler: null as ((range: ChartLogicalRange | null) => void) | null,
    wsOff: vi.fn(),
    wsOn: vi.fn(),
    wsSend: vi.fn(),
  };
});

vi.mock('@/utils/chart', () => ({
  createChartInfrastructure: vi.fn(() => chartAreaMocks.infrastructure),
}));

vi.mock('@/api/candleClient', () => ({
  fetchCandles: vi.fn(),
}));

vi.mock('@/utils/websocketService', () => ({
  wsService: {
    send: chartAreaMocks.wsSend,
    on: chartAreaMocks.wsOn,
    off: chartAreaMocks.wsOff,
  },
}));

vi.mock('@/components/Chart/chartSession', () => ({
  createChartSession: chartAreaMocks.createChartSession,
}));

const indicatorInfo: IndicatorInfo = {
  id: 1,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: false,
  inputs: [],
  outputs: {
    timestamp: { type: 'time' },
    sma: { type: 'line' },
  },
  parameters: {},
};

const candle = (timestampMs: number, close = 1.5): ChartCandle => ({
  timestamp_ms: timestampMs,
  time: Math.floor(timestampMs / 1000),
  open: 1,
  high: 2,
  low: 0.5,
  close,
  volume: 10,
});

const eurUsdM5Key: ChartSessionKey = { symbol: 'EURUSD', exchange: 'FX', timeframe: 'M5' };

type MockChartSession = (typeof chartAreaMocks.chartSessions)[number];

function setupStores(timeframe: TimeframeCode = 'M5') {
  const currentMarketStore = useCurrentMarketStore();
  const currentTimeframeStore = useCurrentTimeframeStore();
  const candlesticksStore = useCandlesticksStore();
  const indicatorsStore = useIndicatorsStore();

  currentMarketStore.setMarket({
    symbol_id: 1,
    symbol: 'EURUSD',
    exchange: 'FX',
    market_type: 'forex',
    min_move: 0.0001,
    timezone: 'UTC',
  });
  currentTimeframeStore.setCurrentTimeframe({ label: timeframe, value: timeframe });
  candlesticksStore.data = [candle(300_000)];
  vi.mocked(fetchCandles).mockResolvedValue([candle(300_000)]);
  vi.spyOn(indicatorsStore, 'requestAllIndicators').mockImplementation(() => undefined);
  vi.spyOn(indicatorsStore, 'fetchOlderForAll').mockResolvedValue();
  vi.spyOn(indicatorsStore, 'unsubscribeAllLive').mockResolvedValue();
  vi.spyOn(indicatorsStore, 'resetHistoryFlags').mockImplementation(() => undefined);

  return {
    candlesticksStore,
    currentMarketStore,
    currentTimeframeStore,
    indicatorsStore,
  };
}

function mountChartArea() {
  return mount(ChartArea, {
    global: {
      stubs: {
        Indicator: true,
      },
    },
  });
}

function latestChartSession(): MockChartSession {
  const session = chartAreaMocks.chartSessions[chartAreaMocks.chartSessions.length - 1];
  if (!session) {
    throw new Error('Expected ChartArea to create a chart session');
  }

  return session;
}

function latestChartSessionAdapter(): ChartSessionSubscriptionsAdapter {
  const adapter = chartAreaMocks.chartSessionAdapters[
    chartAreaMocks.chartSessionAdapters.length - 1
  ];
  if (!adapter) {
    throw new Error('Expected ChartArea to create a chart session adapter');
  }

  return adapter as ChartSessionSubscriptionsAdapter;
}

function latestLiveCandleReceiver(): (message: CandleUpdateMessage) => void {
  const calls = latestChartSession().setSession.mock.calls;
  const lastCall = calls[calls.length - 1] as
    | [unknown, (message: CandleUpdateMessage) => void]
    | undefined;

  if (!lastCall) {
    throw new Error('Expected ChartArea to sync a chart session');
  }

  return lastCall[1];
}

describe('ChartArea', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    chartAreaMocks.chartSessionAdapters.length = 0;
    chartAreaMocks.chartSessions.length = 0;
    chartAreaMocks.indicatorHandlers.clear();
    chartAreaMocks.crosshairHandler = null;
    chartAreaMocks.visibleRangeHandler = null;
    chartAreaMocks.ohlcSeriesInfo.series.barsInLogicalRange.mockReturnValue({
      barsBefore: 50,
      barsAfter: 0,
    });
    Object.values(chartAreaMocks.infrastructure.indicatorManager).forEach((mock) => {
      mock.mockClear();
    });
    chartAreaMocks.infrastructure.init.mockClear();
    chartAreaMocks.infrastructure.getSeries.mockClear();
    chartAreaMocks.infrastructure.addCandlestickData.mockClear();
    chartAreaMocks.infrastructure.updateCandlestick.mockClear();
    chartAreaMocks.infrastructure.setMinMove.mockClear();
    chartAreaMocks.infrastructure.subscribeCrosshairMove.mockClear();
    chartAreaMocks.infrastructure.subscribeVisibleLogicalRangeChange.mockClear();
    chartAreaMocks.infrastructure.scrollToRealTime.mockClear();
    chartAreaMocks.infrastructure.cleanup.mockClear();
    chartAreaMocks.createChartSession.mockClear();
    vi.mocked(fetchCandles).mockReset();
    chartAreaMocks.wsSend.mockReset();
    chartAreaMocks.wsSend.mockResolvedValue(undefined);
    chartAreaMocks.wsOn.mockReset();
    chartAreaMocks.wsOn.mockImplementation((event: string, handler: MockMessageHandler) => {
      if (event === 'indicatorUpdate') {
        chartAreaMocks.indicatorHandlers.add(handler);
      }
    });
    chartAreaMocks.wsOff.mockReset();
    chartAreaMocks.wsOff.mockImplementation((event: string, handler: MockMessageHandler) => {
      if (event === 'indicatorUpdate') {
        chartAreaMocks.indicatorHandlers.delete(handler);
      }
    });
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    vi.spyOn(performance, 'now').mockReturnValue(1_000);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('initializes chart seams and cleans them up on unmount', async () => {
    setupStores();
    const wrapper = mountChartArea();

    await flushPromises();

    expect(chartAreaMocks.createChartSession).toHaveBeenCalledWith(expect.any(Object));
    expect(chartAreaMocks.infrastructure.init).toHaveBeenCalledWith(expect.any(HTMLElement));
    expect(chartAreaMocks.infrastructure.subscribeCrosshairMove).toHaveBeenCalled();
    expect(chartAreaMocks.infrastructure.subscribeVisibleLogicalRangeChange).toHaveBeenCalled();
    expect(chartAreaMocks.wsOn).toHaveBeenCalledWith('indicatorUpdate', expect.any(Function));

    const session = latestChartSession();
    wrapper.unmount();

    expect(session.stop).toHaveBeenCalled();
    expect(chartAreaMocks.infrastructure.cleanup).toHaveBeenCalled();
    expect(chartAreaMocks.wsOff).toHaveBeenCalledWith('indicatorUpdate', expect.any(Function));
  });

  it('updates the OHLC legend from the chart crosshair callback', async () => {
    setupStores();
    const wrapper = mountChartArea();
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [candle(300_000)]);

    chartAreaMocks.crosshairHandler?.({
      time: 300,
      point: { x: 1, y: 1 },
      seriesData: new Map([
        [chartAreaMocks.ohlcSeries, {
          open: 1.1,
          high: 1.3,
          low: 1,
          close: 1.2,
        }],
      ]),
    });

    expect(wrapper.find('.legend').text()).toContain('O: 1.1');
    expect(wrapper.find('.legend').text()).toContain('H: 1.3');
    expect(wrapper.find('.legend').text()).toContain('L: 1');
    expect(wrapper.find('.legend').text()).toContain('C: 1.2');
  });

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

  it('applies live candle receiver updates through the store and chart infrastructure', async () => {
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
    expect(chartAreaMocks.infrastructure.updateCandlestick).toHaveBeenCalledWith(
      expect.objectContaining({ timestamp_ms: 600_000, time: 600, close: 2.5 }),
    );
  });

  it('constructs a chart session adapter over stores, websocket, and chart infrastructure', async () => {
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
    expect(chartAreaMocks.infrastructure.addCandlestickData).toHaveBeenCalledWith(
      [candle(600_000, 2.5)],
      expect.objectContaining({
        priceFormat: expect.objectContaining({ minMove: 0.0001, precision: 4 }),
      }),
    );
    expect(indicatorsStore.requestAllIndicators).toHaveBeenCalledWith('EURUSD', 'M5', 'FX');
    expect(indicatorsStore.unsubscribeAllLive).toHaveBeenCalled();
    expect(indicatorsStore.fetchOlderForAll).toHaveBeenCalledWith('EURUSD', 'M5', 'FX', 500);
    expect(indicatorsStore.resetHistoryFlags).toHaveBeenCalled();
    expect(adapter.getOldestCandleTimestampMs()).toBe(600_000);
  });

  it('bridges visible range events into the chart session after wheel settling', async () => {
    setupStores('M5');
    const wrapper = mountChartArea();
    await flushPromises();
    const vm = wrapper.vm as ComponentPublicInstance & {
      onWheelPassive: () => void;
      shouldScrollToRealTime: boolean;
    };
    vm.shouldScrollToRealTime = false;
    chartAreaMocks.ohlcSeriesInfo.series.barsInLogicalRange.mockReturnValue({
      barsBefore: 99,
      barsAfter: 0,
    });

    chartAreaMocks.visibleRangeHandler?.({ from: 0, to: 10 } as ChartLogicalRange);

    expect(latestChartSession().requestOlderHistory).toHaveBeenCalledWith({
      barsBefore: 99,
      nowMs: 1_000,
      scrollToRealtime: false,
    });

    latestChartSession().requestOlderHistory.mockClear();
    vm.onWheelPassive();
    chartAreaMocks.visibleRangeHandler?.({ from: 0, to: 10 } as ChartLogicalRange);

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
