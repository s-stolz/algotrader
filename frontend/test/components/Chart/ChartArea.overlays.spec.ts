import {
  chartAreaMocks,
  candle,
  eurUsdM5Key,
  eurUsdM15Key,
  backtestRun,
  closedTrade,
  setupStores,
  mountChartArea,
  latestChartSessionAdapter,
  latestLiveCandleReceiver,
  setupChartAreaTests,
} from './ChartArea.fixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import { type CandleUpdateMessage } from '@/types/contracts';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';

describe('ChartArea overlays', () => {
  setupChartAreaTests();

  it('renders loaded-range Backtest Run markers and protective lines', async () => {
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

    expect(
      chartAreaMocks.infrastructure.setCandlestickMarkers,
    ).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'entry-only:entry',
        time: 300,
        position: 'belowBar',
        shape: 'arrowUp',
        text: 'Buy @ 101.2500',
      }),
      expect.objectContaining({
        id: 'exit-only:exit',
        time: 600,
        position: 'aboveBar',
        shape: 'circle',
        text: 'Sell @ 104.5000',
      }),
    ]);
    const markersJson = JSON.stringify(
      chartAreaMocks.infrastructure.setCandlestickMarkers.mock.calls.at(
        -1,
      )?.[0],
    );
    expect(markersJson).not.toContain('signal');
    expect(markersJson).not.toContain('stop_loss');
    expect(markersJson).not.toContain('take_profit');

    expect(
      chartAreaMocks.infrastructure.setCandlestickProtectiveLines,
    ).toHaveBeenLastCalledWith([
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

  it('refreshes overlays as older and live Candles extend the range', async () => {
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

    expect(
      chartAreaMocks.infrastructure.setCandlestickMarkers,
    ).toHaveBeenLastCalledWith([]);
    expect(
      chartAreaMocks.infrastructure.setCandlestickProtectiveLines,
    ).toHaveBeenLastCalledWith([
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

    latestChartSessionAdapter().prependOlderCandles(eurUsdM5Key, [
      candle(60_000),
    ]);
    latestChartSessionAdapter().renderOlderCandles(eurUsdM5Key);

    expect(
      chartAreaMocks.infrastructure.setCandlestickMarkers,
    ).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'range-extension:entry',
        time: 60,
        text: 'Buy @ 99.0000',
      }),
    ]);
    expect(
      chartAreaMocks.infrastructure.setCandlestickProtectiveLines,
    ).toHaveBeenLastCalledWith([
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
    expect(
      chartAreaMocks.infrastructure.updateCandlestick,
    ).toHaveBeenCalledWith(
      expect.objectContaining({ timestamp_ms: 900_000, time: 900 }),
    );
    expect(
      chartAreaMocks.infrastructure.setCandlestickMarkers,
    ).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'range-extension:entry',
        time: 60,
        text: 'Buy @ 99.0000',
      }),
      expect.objectContaining({
        id: 'range-extension:exit',
        time: 900,
        text: 'Sell @ 105.0000',
      }),
    ]);
    expect(
      chartAreaMocks.infrastructure.setCandlestickProtectiveLines,
    ).toHaveBeenLastCalledWith([
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

  it('shows reversal details and clears hover outside markers', async () => {
    setupStores();
    const store = useBacktestOverlayStore();
    store.selectedRunId = 'run-123';
    store.selectedRun = backtestRun();
    store.closedTrades = [
      closedTrade({ trade_id: 'long', realized_pnl: -3.25 }),
      closedTrade({
        trade_id: 'short',
        trade_direction: 'short',
        entry_timestamp_ms: 600_000,
        entry_price: 104.5,
        exit_timestamp_ms: 900_000,
      }),
    ];
    mountChartArea();
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
      candle(600_000),
    ]);
    const pane = chartAreaMocks.mainPaneElement;
    const hover = async (hoveredObjectId?: unknown, paneIndex = 0, x = 1) => {
      chartAreaMocks.crosshairHandler?.({
        time: 600,
        point: { x, y: 1 },
        seriesData: new Map(),
        hoveredObjectId,
        paneIndex,
      });
      await flushPromises();
    };
    await hover('long:exit');
    expect(pane?.querySelector('[role="tooltip"]')?.textContent).toContain(
      'Close long @ 104.5000 · Realized PnL: -3.25 account units',
    );
    await hover('short:entry');
    expect(pane?.querySelector('[role="tooltip"]')?.textContent).toContain(
      'Open short @ 104.5000',
    );
    expect(pane?.querySelector('[role="tooltip"]')?.textContent).not.toContain(
      'PnL',
    );
    for (const args of [
      [undefined],
      ['unrelated'],
      ['long:exit', 1],
      ['long:exit', 0, -1],
    ] as const) {
      await hover(...args);
      expect(pane?.querySelector('[role="tooltip"]')).toBeNull();
    }
    await hover('long:exit');
    store.clearOverlay();
    await flushPromises();
    expect(pane?.querySelector('[role="tooltip"]')).toBeNull();
  });

  it('shows a compact Backtest Run overlay panel and removes the selected overlay', async () => {
    setupStores('M15');
    const backtestOverlayStore = useBacktestOverlayStore();
    backtestOverlayStore.selectedRunId = 'run-123';
    backtestOverlayStore.selectedRun = backtestRun();
    backtestOverlayStore.closedTrades = [closedTrade()];
    const wrapper = mountChartArea();
    await flushPromises();

    const paneOverlay = chartAreaMocks.mainPaneElement?.querySelector(
      '.indicators-wrapper',
    );
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

    const removeButton = paneOverlay?.querySelector(
      '[data-testid="remove-backtest-overlay"]',
    );
    expect(removeButton).toBeInstanceOf(HTMLButtonElement);
    removeButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(backtestOverlayStore.selectedRunId).toBeNull();
    expect(backtestOverlayStore.selectedRun).toBeNull();
    expect(backtestOverlayStore.closedTrades).toEqual([]);
    expect(
      chartAreaMocks.infrastructure.setCandlestickMarkers,
    ).toHaveBeenCalledWith([]);
    expect(
      chartAreaMocks.infrastructure.setCandlestickProtectiveLines,
    ).toHaveBeenCalledWith([]);
    expect(paneOverlay?.querySelector('.backtest-overlay-panel')).toBeNull();
  });
});
