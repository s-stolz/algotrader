import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h, type ComponentPublicInstance } from 'vue';
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
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import type { BacktestClosedTrade, BacktestRun } from '@/types/backtesterContracts';
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

const NButtonStub = defineComponent({
  name: 'NButton',
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      onClick: (event: MouseEvent) => emit('click', event),
    }, slots.default?.());
  },
});

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
  const chartManager = {
    getPaneHtmlElement: vi.fn(() => Promise.resolve(chartAreaMocks.mainPaneElement)),
  };
  const infrastructure = {
    chartManager,
    indicatorManager,
    chartInitialized: false,
    chartError: null,
    init: vi.fn(() => true),
    getSeries: vi.fn(() => seriesMap),
    addCandlestickData: vi.fn(() => ohlcSeries),
    updateCandlestick: vi.fn(() => true),
    setMinMove: vi.fn(() => true),
    setCandlestickMarkers: vi.fn((_markers: readonly unknown[]) => true),
    setCandlestickProtectiveLines: vi.fn((_segments: readonly unknown[]) => true),
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
    mainPaneElement: null as HTMLElement | null,
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
const eurUsdM15Key: ChartSessionKey = { symbol: 'EURUSD', exchange: 'FX', timeframe: 'M15' };

const backtestRun = (overrides: Partial<BacktestRun> = {}): BacktestRun => ({
  run_id: 'run-123',
  status: 'succeeded',
  submitted_at_ms: 1_780_921_805_123,
  started_at_ms: 1_780_921_900_000,
  completed_at_ms: 1_780_922_100_000,
  request_schema_version: 1,
  request: {
    symbols: ['EURUSD'],
    exchange: 'FX',
    timeframe: 'M15',
    start_ms: 60_000,
    end_ms: 900_000,
    engine: 'event_driven',
    data_granularity: 'bar',
    initial_capital: 10_000,
    strategy: {
      strategy_id: 'sma_crossover',
      parameters: { fast_window: 10, slow_window: 20 },
    },
    execution: {
      signal_timing: 'close',
      fill_timing: 'next_open',
      price_source: 'open',
      allow_partial_fills: false,
      allow_short: false,
      trade_accounting_policy: 'average_cost',
      gap_policy: 'skip',
      intrabar_exit_policy: 'conservative',
      commission_bps: 1,
      slippage_bps: 0.5,
    },
    persist_result: true,
    run_metadata: null,
  },
  result_schema_version: 2,
  metrics: null,
  diagnostics: null,
  error_code: null,
  error_message: null,
  ...overrides,
});

const closedTrade = (overrides: Partial<BacktestClosedTrade> = {}): BacktestClosedTrade => ({
  sequence: 0,
  trade_id: 'trade-1',
  symbol: 'EURUSD',
  quantity: 1_000,
  entry_timestamp_ms: 300_000,
  entry_price: 101.25,
  exit_timestamp_ms: 600_000,
  exit_price: 104.5,
  realized_pnl: 3.25,
  fees: 0.25,
  exit_reason: 'signal',
  stop_loss_price: null,
  take_profit_price: null,
  ...overrides,
});

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
  vi.spyOn(indicatorsStore, 'ensureCoverageForAll').mockResolvedValue();
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
        NButton: NButtonStub,
        NIcon: { template: '<span><slot /></span>' },
        'n-button': NButtonStub,
        'n-icon': { template: '<span><slot /></span>' },
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
    chartAreaMocks.mainPaneElement = document.createElement('div');
    document.body.appendChild(chartAreaMocks.mainPaneElement);
    chartAreaMocks.infrastructure.chartManager.getPaneHtmlElement.mockClear();
    chartAreaMocks.infrastructure.chartManager.getPaneHtmlElement.mockImplementation(() => (
      Promise.resolve(chartAreaMocks.mainPaneElement)
    ));
    Object.values(chartAreaMocks.infrastructure.indicatorManager).forEach((mock) => {
      mock.mockClear();
    });
    chartAreaMocks.infrastructure.init.mockClear();
    chartAreaMocks.infrastructure.getSeries.mockClear();
    chartAreaMocks.infrastructure.addCandlestickData.mockClear();
    chartAreaMocks.infrastructure.updateCandlestick.mockClear();
    chartAreaMocks.infrastructure.setMinMove.mockClear();
    chartAreaMocks.infrastructure.setCandlestickMarkers.mockClear();
    chartAreaMocks.infrastructure.setCandlestickProtectiveLines.mockClear();
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
    chartAreaMocks.mainPaneElement?.remove();
    chartAreaMocks.mainPaneElement = null;
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

  it('renders selected Backtest Run markers and protective lines inside the loaded candle range', async () => {
    setupStores('M15');
    const backtestOverlayStore = useBacktestOverlayStore();
    backtestOverlayStore.selectedRunId = 'run-123';
    backtestOverlayStore.selectedRun = backtestRun();
    backtestOverlayStore.closedTrades = [
      closedTrade({
        trade_id: 'entry-only',
        entry_timestamp_ms: 300_000,
        entry_price: 101.25,
        exit_timestamp_ms: 1_200_000,
        exit_price: 110,
        exit_reason: 'signal',
        stop_loss_price: 99.5,
        take_profit_price: 109.75,
      }),
      closedTrade({
        trade_id: 'exit-only',
        entry_timestamp_ms: 60_000,
        entry_price: 95,
        exit_timestamp_ms: 600_000,
        exit_price: 104.5,
        exit_reason: 'take_profit',
        stop_loss_price: null,
        take_profit_price: 104,
      }),
      closedTrade({
        trade_id: 'outside-range',
        entry_timestamp_ms: 1_500_000,
        exit_timestamp_ms: 1_800_000,
        exit_reason: 'stop_loss',
        stop_loss_price: 97,
        take_profit_price: 110,
      }),
    ];
    mountChartArea();
    await flushPromises();
    chartAreaMocks.infrastructure.setCandlestickMarkers.mockClear();
    chartAreaMocks.infrastructure.setCandlestickProtectiveLines.mockClear();

    await latestChartSessionAdapter().renderCandles(eurUsdM15Key, [
      candle(300_000),
      candle(600_000),
      candle(900_000),
    ]);

    expect(chartAreaMocks.infrastructure.setCandlestickMarkers).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'entry-only:entry',
        time: 300,
        position: 'belowBar',
        shape: 'arrowUp',
        text: 'Buy @ 101.25',
      }),
      expect.objectContaining({
        id: 'exit-only:exit',
        time: 600,
        position: 'aboveBar',
        shape: 'arrowDown',
        text: 'Sell @ 104.5',
      }),
    ]);
    const markersJson = JSON.stringify(
      chartAreaMocks.infrastructure.setCandlestickMarkers.mock.calls.at(-1)?.[0],
    );
    expect(markersJson).not.toContain('signal');
    expect(markersJson).not.toContain('stop_loss');
    expect(markersJson).not.toContain('take_profit');

    expect(chartAreaMocks.infrastructure.setCandlestickProtectiveLines).toHaveBeenLastCalledWith([
      {
        id: 'entry-only:stop-loss',
        startTime: 300,
        endTime: 1_200,
        price: 99.5,
        color: '#dc2626',
      },
      {
        id: 'entry-only:take-profit',
        startTime: 300,
        endTime: 1_200,
        price: 109.75,
        color: '#2563eb',
      },
      {
        id: 'exit-only:take-profit',
        startTime: 60,
        endTime: 600,
        price: 104,
        color: '#2563eb',
      },
    ]);
  });

  it('refreshes Backtest Run overlays after older candles and live candles extend the loaded range', async () => {
    const { candlesticksStore } = setupStores('M5');
    const backtestOverlayStore = useBacktestOverlayStore();
    backtestOverlayStore.selectedRunId = 'run-123';
    backtestOverlayStore.selectedRun = backtestRun();
    backtestOverlayStore.closedTrades = [
      closedTrade({
        trade_id: 'range-extension',
        entry_timestamp_ms: 60_000,
        entry_price: 99,
        exit_timestamp_ms: 900_000,
        exit_price: 105,
        stop_loss_price: 96,
        take_profit_price: 106,
      }),
    ];
    mountChartArea();
    await flushPromises();
    chartAreaMocks.infrastructure.setCandlestickMarkers.mockClear();
    chartAreaMocks.infrastructure.setCandlestickProtectiveLines.mockClear();

    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
      candle(600_000),
    ]);

    expect(chartAreaMocks.infrastructure.setCandlestickMarkers).toHaveBeenLastCalledWith([]);
    expect(chartAreaMocks.infrastructure.setCandlestickProtectiveLines).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'range-extension:stop-loss',
        startTime: 60,
        endTime: 900,
      }),
      expect.objectContaining({
        id: 'range-extension:take-profit',
        startTime: 60,
        endTime: 900,
      }),
    ]);

    latestChartSessionAdapter().prependOlderCandles(eurUsdM5Key, [candle(60_000)]);
    latestChartSessionAdapter().renderOlderCandles(eurUsdM5Key);

    expect(chartAreaMocks.infrastructure.setCandlestickMarkers).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'range-extension:entry',
        time: 60,
        text: 'Buy @ 99',
      }),
    ]);
    expect(chartAreaMocks.infrastructure.setCandlestickProtectiveLines).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'range-extension:stop-loss',
        startTime: 60,
        endTime: 900,
      }),
      expect.objectContaining({
        id: 'range-extension:take-profit',
        startTime: 60,
        endTime: 900,
      }),
    ]);

    const message: CandleUpdateMessage = {
      type: 'candleUpdate',
      symbol: 'EURUSD',
      timeframe: 'M5',
      timestamp_ms: 900_000,
      open: 2,
      high: 3,
      low: 1.8,
      close: 2.5,
      volume: 5,
    };

    latestLiveCandleReceiver()(message);

    expect(candlesticksStore.data.at(-1)).toEqual(
      expect.objectContaining({ timestamp_ms: 900_000, time: 900 }),
    );
    expect(chartAreaMocks.infrastructure.updateCandlestick).toHaveBeenCalledWith(
      expect.objectContaining({ timestamp_ms: 900_000, time: 900 }),
    );
    expect(chartAreaMocks.infrastructure.setCandlestickMarkers).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'range-extension:entry',
        time: 60,
        text: 'Buy @ 99',
      }),
      expect.objectContaining({
        id: 'range-extension:exit',
        time: 900,
        text: 'Sell @ 105',
      }),
    ]);
    expect(chartAreaMocks.infrastructure.setCandlestickProtectiveLines).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'range-extension:stop-loss',
        startTime: 60,
        endTime: 900,
      }),
      expect.objectContaining({
        id: 'range-extension:take-profit',
        startTime: 60,
        endTime: 900,
      }),
    ]);
  });

  it('shows a compact Backtest Run overlay panel and removes the selected overlay', async () => {
    setupStores('M15');
    const backtestOverlayStore = useBacktestOverlayStore();
    backtestOverlayStore.selectedRunId = 'run-123';
    backtestOverlayStore.selectedRun = backtestRun();
    backtestOverlayStore.closedTrades = [closedTrade()];
    const wrapper = mountChartArea();
    await flushPromises();

    const paneOverlay = chartAreaMocks.mainPaneElement?.querySelector('.indicators-wrapper');
    const panel = paneOverlay?.querySelector('.backtest-overlay-panel');
    const title = paneOverlay?.querySelector('.backtest-overlay-title');
    expect(paneOverlay).toBeInstanceOf(HTMLDivElement);
    expect(panel).toBeInstanceOf(HTMLDivElement);
    expect(panel?.textContent).not.toContain('Backtest Run');
    expect(title?.textContent).toBe('sma_crossover');
    expect(panel?.textContent).toContain('FX:EURUSD');
    expect(panel?.textContent).toContain('M15');
    expect(panel?.textContent).toContain('sma_crossover');
    expect(panel?.textContent).not.toContain('run-123');
    expect(wrapper.find('.legend').exists()).toBe(true);
    expect(wrapper.find('.backtest-overlay-panel').exists()).toBe(false);

    chartAreaMocks.infrastructure.setCandlestickMarkers.mockClear();
    chartAreaMocks.infrastructure.setCandlestickProtectiveLines.mockClear();

    const removeButton = paneOverlay?.querySelector('[data-testid="remove-backtest-overlay"]');
    expect(removeButton).toBeInstanceOf(HTMLButtonElement);
    removeButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(backtestOverlayStore.selectedRunId).toBeNull();
    expect(backtestOverlayStore.selectedRun).toBeNull();
    expect(backtestOverlayStore.closedTrades).toEqual([]);
    expect(chartAreaMocks.infrastructure.setCandlestickMarkers).toHaveBeenCalledWith([]);
    expect(chartAreaMocks.infrastructure.setCandlestickProtectiveLines).toHaveBeenCalledWith([]);
    expect(paneOverlay?.querySelector('.backtest-overlay-panel')).toBeNull();
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

    const requestCoverageOptions = vi.mocked(indicatorsStore.requestAllIndicators).mock.calls[0][3]!;
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
