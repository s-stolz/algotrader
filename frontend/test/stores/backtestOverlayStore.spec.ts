import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchBacktestClosedTrades, getBacktestRun } from '@/api/backtesterClient';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestClosedTrade, BacktestRun } from '@/types/backtesterContracts';
import type { Market } from '@/types/contracts';
import { STORAGE_KEYS } from '@/utils/localStorage';

vi.mock('@/api/backtesterClient', () => ({
  fetchBacktestClosedTrades: vi.fn(),
  getBacktestRun: vi.fn(),
}));

const eurUsdMarket: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const gbpUsdMarket: Market = {
  symbol_id: 2,
  symbol: 'GBPUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const closedTrades: BacktestClosedTrade[] = [
  {
    sequence: 0,
    trade_id: 'trade-1',
    symbol: 'EURUSD',
    quantity: 1_000,
    entry_timestamp_ms: 1_714_525_200_000,
    entry_price: 1.0715,
    exit_timestamp_ms: 1_714_532_400_000,
    exit_price: 1.074,
    realized_pnl: 2.5,
    fees: 0.3,
    exit_reason: 'signal',
    stop_loss_price: 1.069,
    take_profit_price: 1.075,
  },
  {
    sequence: 1,
    trade_id: 'trade-2',
    symbol: 'EURUSD',
    quantity: 1_000,
    entry_timestamp_ms: 1_714_608_000_000,
    entry_price: 1.081,
    exit_timestamp_ms: 1_714_611_600_000,
    exit_price: 1.083,
    realized_pnl: 2,
    fees: 0.3,
    exit_reason: 'take_profit',
    stop_loss_price: null,
    take_profit_price: 1.083,
  },
];

describe('backtestOverlayStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    vi.mocked(fetchBacktestClosedTrades).mockReset();
    vi.mocked(getBacktestRun).mockReset();
  });

  it('selects a supported Backtest Run, switches chart context, caches trades, and persists the run ID', async () => {
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue(closedTrades);
    useMarketsStore().all = [eurUsdMarket, gbpUsdMarket];
    useCurrentMarketStore().setMarket(gbpUsdMarket);

    const store = useBacktestOverlayStore();

    await expect(store.selectRun(backtestRun())).resolves.toEqual({
      selectable: true,
      reason: null,
    });

    expect(fetchBacktestClosedTrades).toHaveBeenCalledOnce();
    expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('run-123');
    expect(store.selectedRunId).toBe('run-123');
    expect(store.selectedRun).toEqual(backtestRun());
    expect(store.closedTrades).toEqual(closedTrades);
    expect(store.getClosedTradesForRange(1_714_520_000_000, 1_714_540_000_000)).toEqual([
      closedTrades[0],
    ]);
    expect(store.error).toBeNull();
    expect(useCurrentMarketStore().symbol).toBe('EURUSD');
    expect(useCurrentMarketStore().exchange).toBe('FX');
    expect(useCurrentTimeframeStore().value).toBe('M15');
    expect(JSON.parse(localStorage.getItem(STORAGE_KEYS.SELECTED_BACKTEST_RUN) ?? 'null')).toBe(
      'run-123',
    );
  });

  it('reloads a persisted selected Backtest Run when it still exists and is supported', async () => {
    localStorage.setItem(STORAGE_KEYS.SELECTED_BACKTEST_RUN, JSON.stringify('run-123'));
    vi.mocked(getBacktestRun).mockResolvedValue(backtestRun());
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue(closedTrades);
    useMarketsStore().all = [eurUsdMarket];

    const store = useBacktestOverlayStore();

    expect(store.selectedRunId).toBe('run-123');

    await expect(store.restorePersistedSelection()).resolves.toEqual({
      selectable: true,
      reason: null,
    });

    expect(getBacktestRun).toHaveBeenCalledWith('run-123');
    expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('run-123');
    expect(store.selectedRun).toEqual(backtestRun());
    expect(store.closedTrades).toEqual(closedTrades);
    expect(useCurrentMarketStore().symbol).toBe('EURUSD');
    expect(useCurrentTimeframeStore().value).toBe('M15');
  });

  it('clears a persisted selected Backtest Run when reload finds an unsupported run', async () => {
    localStorage.setItem(STORAGE_KEYS.SELECTED_BACKTEST_RUN, JSON.stringify('run-old'));
    vi.mocked(getBacktestRun).mockResolvedValue(backtestRun({
      run_id: 'run-old',
      result_schema_version: 1,
    }));
    useMarketsStore().all = [eurUsdMarket];

    const store = useBacktestOverlayStore();

    await expect(store.restorePersistedSelection()).resolves.toEqual({
      selectable: false,
      reason: 'Backtest Run result schema is unsupported.',
    });

    expect(fetchBacktestClosedTrades).not.toHaveBeenCalled();
    expect(store.selectedRunId).toBeNull();
    expect(store.selectedRun).toBeNull();
    expect(store.closedTrades).toEqual([]);
    expect(store.error).toBe('Backtest Run result schema is unsupported.');
    expect(localStorage.getItem(STORAGE_KEYS.SELECTED_BACKTEST_RUN)).toBeNull();
  });

  it('leaves the chart unchanged and surfaces an error when the run market is missing', async () => {
    useMarketsStore().all = [gbpUsdMarket];
    useCurrentMarketStore().setMarket(gbpUsdMarket);
    useCurrentTimeframeStore().setCurrentTimeframe({ label: 'H1', value: 'H1' });

    const store = useBacktestOverlayStore();

    await expect(store.selectRun(backtestRun())).resolves.toEqual({
      selectable: false,
      reason: 'Market FX:EURUSD is not available in the chart market list.',
    });

    expect(fetchBacktestClosedTrades).not.toHaveBeenCalled();
    expect(store.selectedRunId).toBeNull();
    expect(store.closedTrades).toEqual([]);
    expect(store.error).toBe('Market FX:EURUSD is not available in the chart market list.');
    expect(useCurrentMarketStore().symbol).toBe('GBPUSD');
    expect(useCurrentTimeframeStore().value).toBe('H1');
    expect(localStorage.getItem(STORAGE_KEYS.SELECTED_BACKTEST_RUN)).toBeNull();
  });

  it('classifies unsupported Backtest Runs with clear non-selectable reasons', () => {
    const store = useBacktestOverlayStore();

    expect(store.getBacktestRunSelectability(backtestRun({ status: 'running' }))).toEqual({
      selectable: false,
      reason: 'Only succeeded Backtest Runs can be opened.',
    });
    expect(store.getBacktestRunSelectability(backtestRun({ result_schema_version: 1 }))).toEqual({
      selectable: false,
      reason: 'Backtest Run result schema is unsupported.',
    });
    expect(store.getBacktestRunSelectability(backtestRunWithSymbols([]))).toEqual({
      selectable: false,
      reason: 'Backtest Run has no symbol.',
    });
    expect(store.getBacktestRunSelectability(backtestRunWithSymbols(['EURUSD', 'GBPUSD']))).toEqual({
      selectable: false,
      reason: 'Backtest Run has multiple symbols.',
    });
  });

  it('classifies supported-shape Backtest Runs as non-selectable when the market is missing', () => {
    useMarketsStore().all = [gbpUsdMarket];

    const store = useBacktestOverlayStore();

    expect(store.getBacktestRunSelectability(backtestRun())).toEqual({
      selectable: false,
      reason: 'Market FX:EURUSD is not available in the chart market list.',
    });
  });

  it('clears selected run metadata, cached trades, errors, and persistence', async () => {
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue(closedTrades);
    useMarketsStore().all = [eurUsdMarket];
    const store = useBacktestOverlayStore();

    await store.selectRun(backtestRun());
    await store.selectRun(backtestRun({ status: 'failed' }));

    expect(store.selectedRunId).toBe('run-123');
    expect(store.error).toBe('Only succeeded Backtest Runs can be opened.');

    store.clearOverlay();

    expect(store.selectedRunId).toBeNull();
    expect(store.selectedRun).toBeNull();
    expect(store.closedTrades).toEqual([]);
    expect(store.error).toBeNull();
    expect(localStorage.getItem(STORAGE_KEYS.SELECTED_BACKTEST_RUN)).toBeNull();
  });
});

function backtestRun(overrides: Partial<BacktestRun> = {}): BacktestRun {
  return {
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
      start_ms: 1_714_521_600_000,
      end_ms: 1_714_608_000_000,
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
    metrics: { total_return_pct: 1.25, trade_count: 1 },
    diagnostics: { execution_duration_ms: 240_000 },
    error_code: null,
    error_message: null,
    ...overrides,
  };
}

function backtestRunWithSymbols(symbols: string[]): BacktestRun {
  const run = backtestRun();

  return {
    ...run,
    request: {
      ...run.request,
      symbols,
    },
  };
}
