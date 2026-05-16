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
    candleHandlers: new Set<MockMessageHandler>(),
    crosshairHandler: null as MockCrosshairHandler | null,
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

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });

  return {
    promise,
    resolve,
  };
}

interface ChartAreaPublic {
  shouldScrollToRealTime: boolean;
}

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
  vi.spyOn(candlesticksStore, 'fetch').mockResolvedValue();
  vi.spyOn(indicatorsStore, 'requestAllIndicators').mockImplementation(() => undefined);
  vi.spyOn(indicatorsStore, 'fetchOlderForAll').mockResolvedValue();

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

describe('ChartArea', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    chartAreaMocks.candleHandlers.clear();
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
    vi.mocked(fetchCandles).mockReset();
    chartAreaMocks.wsSend.mockReset();
    chartAreaMocks.wsSend.mockResolvedValue(undefined);
    chartAreaMocks.wsOn.mockReset();
    chartAreaMocks.wsOn.mockImplementation((event: string, handler: MockMessageHandler) => {
      if (event === 'candleUpdate') {
        chartAreaMocks.candleHandlers.add(handler);
      }
      if (event === 'indicatorUpdate') {
        chartAreaMocks.indicatorHandlers.add(handler);
      }
    });
    chartAreaMocks.wsOff.mockReset();
    chartAreaMocks.wsOff.mockImplementation((event: string, handler: MockMessageHandler) => {
      if (event === 'candleUpdate') {
        chartAreaMocks.candleHandlers.delete(handler);
      }
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

    expect(chartAreaMocks.infrastructure.init).toHaveBeenCalledWith(expect.any(HTMLElement));
    expect(chartAreaMocks.infrastructure.subscribeCrosshairMove).toHaveBeenCalled();
    expect(chartAreaMocks.infrastructure.subscribeVisibleLogicalRangeChange).toHaveBeenCalled();
    expect(chartAreaMocks.wsOn).toHaveBeenCalledWith('indicatorUpdate', expect.any(Function));

    wrapper.unmount();

    expect(chartAreaMocks.infrastructure.cleanup).toHaveBeenCalled();
    expect(chartAreaMocks.wsOff).toHaveBeenCalledWith('indicatorUpdate', expect.any(Function));
  });

  it('removes candle handlers after unmount while a subscription send is pending', async () => {
    const sendResolvers: Array<() => void> = [];
    chartAreaMocks.wsSend.mockImplementation(() => new Promise<void>((resolve) => {
      sendResolvers.push(resolve);
    }));
    setupStores();

    const wrapper = mountChartArea();
    wrapper.unmount();

    for (const resolve of sendResolvers) {
      resolve();
    }
    await flushPromises();

    expect(chartAreaMocks.wsOn).toHaveBeenCalledWith('candleUpdate', expect.any(Function));
    expect(chartAreaMocks.wsOff).toHaveBeenCalledWith('candleUpdate', expect.any(Function));
    expect(chartAreaMocks.candleHandlers.size).toBe(0);
  });

  it('updates the OHLC legend from the chart crosshair callback', async () => {
    setupStores();
    const wrapper = mountChartArea();
    await flushPromises();

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

  it('ignores M1 candle updates when the active timeframe is larger', async () => {
    const { candlesticksStore } = setupStores('M5');
    mountChartArea();
    await flushPromises();
    chartAreaMocks.infrastructure.updateCandlestick.mockClear();

    const message: CandleUpdateMessage = {
      type: 'candleUpdate',
      symbol: 'EURUSD',
      timeframe: 'M1',
      timestamp_ms: 360_000,
      open: 2,
      high: 3,
      low: 0.4,
      close: 2.5,
      volume: 5,
    };

    expect(chartAreaMocks.candleHandlers.size).toBe(1);
    for (const handler of chartAreaMocks.candleHandlers) {
      handler(message);
    }

    expect(candlesticksStore.data).toEqual([candle(300_000)]);
    expect(chartAreaMocks.infrastructure.updateCandlestick).not.toHaveBeenCalled();
  });

  it('applies same-timeframe candle updates through the active live subscription', async () => {
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

    expect(chartAreaMocks.candleHandlers.size).toBe(1);
    for (const handler of chartAreaMocks.candleHandlers) {
      handler(message);
    }

    expect(candlesticksStore.data).toEqual([
      candle(300_000),
      {
        timestamp_ms: 600_000,
        time: 600,
        open: 2,
        high: 3,
        low: 1.8,
        close: 2.5,
        volume: 5,
      },
    ]);
    expect(chartAreaMocks.infrastructure.updateCandlestick).toHaveBeenCalledWith({
      timestamp_ms: 600_000,
      time: 600,
      open: 2,
      high: 3,
      low: 1.8,
      close: 2.5,
      volume: 5,
    });
  });

  it('does not let stale session fetches replace store-backed candle data', async () => {
    const { candlesticksStore, currentMarketStore } = setupStores('M5');
    const firstFetch = deferred<ChartCandle[]>();
    const currentCandles = [candle(600_000, 2.5)];
    const staleCandles = [candle(300_000, 9.9)];

    vi.mocked(fetchCandles).mockImplementation((symbol) => {
      if (symbol === 'EURUSD') {
        return firstFetch.promise;
      }
      return Promise.resolve(currentCandles);
    });

    mountChartArea();
    await vi.waitFor(() => {
      expect(fetchCandles).toHaveBeenCalledWith('EURUSD', 'M5', {
        limit: 500,
        exchange: 'FX',
      });
    });

    currentMarketStore.setMarket({
      symbol_id: 2,
      symbol: 'GBPUSD',
      exchange: 'FX',
      market_type: 'forex',
      min_move: 0.0001,
      timezone: 'UTC',
    });
    await vi.waitFor(() => {
      expect(fetchCandles).toHaveBeenCalledWith('GBPUSD', 'M5', {
        limit: 500,
        exchange: 'FX',
      });
    });
    await flushPromises();

    expect(candlesticksStore.data).toEqual(currentCandles);
    chartAreaMocks.infrastructure.addCandlestickData.mockClear();

    firstFetch.resolve(staleCandles);
    await flushPromises();

    expect(candlesticksStore.data).toEqual(currentCandles);
    expect(chartAreaMocks.infrastructure.addCandlestickData).not.toHaveBeenCalledWith(
      staleCandles,
      expect.anything(),
    );
  });

  it('loads older candle and indicator history near the left visible range', async () => {
    const { candlesticksStore, indicatorsStore } = setupStores('M5');
    const wrapper = mountChartArea();
    await flushPromises();
    const vm = wrapper.vm as ComponentPublicInstance & ChartAreaPublic;
    vm.shouldScrollToRealTime = false;
    vi.mocked(candlesticksStore.fetch).mockClear();
    vi.mocked(indicatorsStore.fetchOlderForAll).mockClear();
    chartAreaMocks.ohlcSeriesInfo.series.barsInLogicalRange.mockReturnValue({
      barsBefore: 99,
      barsAfter: 0,
    });

    chartAreaMocks.visibleRangeHandler?.({ from: 0, to: 10 } as ChartLogicalRange);
    await flushPromises();

    expect(candlesticksStore.fetch).toHaveBeenCalledWith('EURUSD', 'M5', {
      endMs: 300_000,
      limit: 500,
      append: true,
      exchange: 'FX',
    });
    expect(indicatorsStore.fetchOlderForAll).toHaveBeenCalledWith(
      'EURUSD',
      'M5',
      'FX',
      500,
    );
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
