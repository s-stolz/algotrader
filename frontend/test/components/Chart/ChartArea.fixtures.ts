import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, vi } from 'vitest';

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
import type {
  BacktestClosedTrade,
  BacktestRun,
} from '@/types/backtesterContracts';
import type { ChartLogicalRange } from '@/utils/chart';

import ChartArea from '@/components/Chart/ChartArea.vue';
import type {
  ChartSessionKey,
  ChartSessionSubscriptionsAdapter,
} from '@/components/Chart/chartSession';

interface MockCrosshairParam {
  hoveredObjectId?: unknown;
  paneIndex?: number;
  time: number;
  point: { x: number; y: number };
  seriesData: Map<object, object>;
}

type MockCrosshairHandler = (param: MockCrosshairParam) => void;
type MockMessageHandler = (
  message: CandleUpdateMessage | IndicatorUpdateMessage,
) => void;

const NButtonStub = defineComponent({
  name: 'NButton',
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () =>
      h(
        'button',
        {
          ...attrs,
          onClick: (event: MouseEvent) => emit('click', event),
        },
        slots.default?.(),
      );
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
    getPaneHtmlElement: vi.fn(() =>
      Promise.resolve(chartAreaMocks.mainPaneElement),
    ),
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
    setCandlestickProtectiveLines: vi.fn(
      (_segments: readonly unknown[]) => true,
    ),
    setCandlestickMeasurementOverlay: vi.fn((_model: unknown) => true),
    clearCandlestickMeasurementOverlay: vi.fn(() => true),
    coordinateToCandlestickPrice: vi.fn(
      (_coordinate: number) => null as number | null,
    ),
    coordinateToLogical: vi.fn((_coordinate: number) => null as number | null),
    setMouseDragScrollEnabled: vi.fn((_enabled: boolean) => true),
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
    visibleRangeHandler: null as
      | ((range: ChartLogicalRange | null) => void)
      | null,
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

export const indicatorInfo: IndicatorInfo = {
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

export const candle = (timestampMs: number, close = 1.5): ChartCandle => ({
  timestamp_ms: timestampMs,
  time: Math.floor(timestampMs / 1000),
  open: 1,
  high: 2,
  low: 0.5,
  close,
  volume: 10,
});

export const eurUsdM5Key: ChartSessionKey = {
  symbol: 'EURUSD',
  exchange: 'FX',
  timeframe: 'M5',
};
export const eurUsdM15Key: ChartSessionKey = {
  symbol: 'EURUSD',
  exchange: 'FX',
  timeframe: 'M15',
};

export const backtestRun = (
  overrides: Partial<BacktestRun> = {},
): BacktestRun => ({
  run_id: 'run-123',
  status: 'succeeded',
  submitted_at_ms: 1_780_921_805_123,
  started_at_ms: 1_780_921_900_000,
  completed_at_ms: 1_780_922_100_000,
  request_schema_version: 2,
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
      allowed_directions: 'long_and_short',
      trade_accounting_policy: 'average_cost',
      gap_policy: 'skip',
      intrabar_exit_policy: 'conservative',
      commission_bps: 1,
      slippage_bps: 0.5,
    },
    persist_result: true,
    run_metadata: null,
  },
  result_schema_version: 3,
  metrics: null,
  diagnostics: null,
  error_code: null,
  error_message: null,
  ...overrides,
});

export const closedTrade = (
  overrides: Partial<BacktestClosedTrade> = {},
): BacktestClosedTrade => ({
  sequence: 0,
  trade_id: 'trade-1',
  symbol: 'EURUSD',
  trade_direction: 'long',
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

export function setupStores(timeframe: TimeframeCode = 'M5') {
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
  currentTimeframeStore.setCurrentTimeframe({
    label: timeframe,
    value: timeframe,
  });
  candlesticksStore.data = [candle(300_000)];
  vi.mocked(fetchCandles).mockResolvedValue([candle(300_000)]);
  vi.spyOn(indicatorsStore, 'requestAllIndicators').mockImplementation(
    () => undefined,
  );
  vi.spyOn(indicatorsStore, 'ensureCoverageForAll').mockResolvedValue();
  vi.spyOn(indicatorsStore, 'unsubscribeAllLive').mockResolvedValue();
  vi.spyOn(indicatorsStore, 'resetHistoryFlags').mockImplementation(
    () => undefined,
  );

  return {
    candlesticksStore,
    currentMarketStore,
    currentTimeframeStore,
    indicatorsStore,
  };
}

export function mountChartArea(props: Record<string, unknown> = {}) {
  return mount(ChartArea, {
    props,
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

export function latestChartSession(): MockChartSession {
  const session =
    chartAreaMocks.chartSessions[chartAreaMocks.chartSessions.length - 1];
  if (!session) {
    throw new Error('Expected ChartArea to create a chart session');
  }

  return session;
}

export function latestChartSessionAdapter(): ChartSessionSubscriptionsAdapter {
  const adapter =
    chartAreaMocks.chartSessionAdapters[
      chartAreaMocks.chartSessionAdapters.length - 1
    ];
  if (!adapter) {
    throw new Error('Expected ChartArea to create a chart session adapter');
  }

  return adapter as ChartSessionSubscriptionsAdapter;
}

export function latestLiveCandleReceiver(): (
  message: CandleUpdateMessage,
) => void {
  const calls = latestChartSession().setSession.mock.calls;
  const lastCall = calls[calls.length - 1] as
    | [unknown, (message: CandleUpdateMessage) => void]
    | undefined;

  if (!lastCall) {
    throw new Error('Expected ChartArea to sync a chart session');
  }

  return lastCall[1];
}

export function stubMainPaneRect(): HTMLElement {
  if (!chartAreaMocks.mainPaneElement) {
    throw new Error('Expected main pane element');
  }

  chartAreaMocks.mainPaneElement.getBoundingClientRect = vi.fn(() => ({
    x: 100,
    y: 200,
    top: 200,
    right: 500,
    bottom: 500,
    left: 100,
    width: 400,
    height: 300,
    toJSON: () => ({}),
  }));

  return chartAreaMocks.mainPaneElement;
}

export function setupChartAreaTests() {
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
    chartAreaMocks.infrastructure.chartManager.getPaneHtmlElement.mockImplementation(
      () => Promise.resolve(chartAreaMocks.mainPaneElement),
    );
    Object.values(chartAreaMocks.infrastructure.indicatorManager).forEach(
      (mock) => {
        mock.mockClear();
      },
    );
    chartAreaMocks.infrastructure.init.mockClear();
    chartAreaMocks.infrastructure.getSeries.mockClear();
    chartAreaMocks.infrastructure.addCandlestickData.mockClear();
    chartAreaMocks.infrastructure.updateCandlestick.mockClear();
    chartAreaMocks.infrastructure.setMinMove.mockClear();
    chartAreaMocks.infrastructure.setCandlestickMarkers.mockClear();
    chartAreaMocks.infrastructure.setCandlestickProtectiveLines.mockClear();
    chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay.mockClear();
    chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay.mockClear();
    chartAreaMocks.infrastructure.coordinateToCandlestickPrice.mockClear();
    chartAreaMocks.infrastructure.coordinateToCandlestickPrice.mockReturnValue(
      null,
    );
    chartAreaMocks.infrastructure.coordinateToLogical.mockClear();
    chartAreaMocks.infrastructure.coordinateToLogical.mockReturnValue(null);
    chartAreaMocks.infrastructure.setMouseDragScrollEnabled.mockClear();
    chartAreaMocks.infrastructure.subscribeCrosshairMove.mockClear();
    chartAreaMocks.infrastructure.subscribeVisibleLogicalRangeChange.mockClear();
    chartAreaMocks.infrastructure.scrollToRealTime.mockClear();
    chartAreaMocks.infrastructure.cleanup.mockClear();
    chartAreaMocks.createChartSession.mockClear();
    vi.mocked(fetchCandles).mockReset();
    chartAreaMocks.wsSend.mockReset();
    chartAreaMocks.wsSend.mockResolvedValue(undefined);
    chartAreaMocks.wsOn.mockReset();
    chartAreaMocks.wsOn.mockImplementation(
      (event: string, handler: MockMessageHandler) => {
        if (event === 'indicatorUpdate') {
          chartAreaMocks.indicatorHandlers.add(handler);
        }
      },
    );
    chartAreaMocks.wsOff.mockReset();
    chartAreaMocks.wsOff.mockImplementation(
      (event: string, handler: MockMessageHandler) => {
        if (event === 'indicatorUpdate') {
          chartAreaMocks.indicatorHandlers.delete(handler);
        }
      },
    );
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
}

export { chartAreaMocks };
