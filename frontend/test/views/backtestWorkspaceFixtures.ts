import { installBacktestSocket } from '../backtestEventSocket';
import { flushPromises, mount } from '@vue/test-utils';
import { h } from 'vue';
import DesignScope from '@/components/Common/DesignScope.vue';

import { createPinia, setActivePinia, type Pinia } from 'pinia';

import { afterEach, beforeEach, expect, onTestFinished, vi } from 'vitest';

import {
  renameExperiment,
  cancelBacktestRun,
  controlBacktest,
  deleteBacktest,
  fetchBacktestClosedTrades,
  fetchBacktestEquityCurve,
  fetchBacktestFills,
  fetchBacktestQueue,
  getBacktest,
  getBacktestRun,
  listBacktestEvents,
  listBacktestMembers,
  listBacktests,
  listBacktestRuns,
} from '@/api/backtesterClient';

import { useMarketsStore } from '@/stores/marketsStore';
import type {
  Backtest,
  BacktestClosedTrade,
  BacktestFill,
  BacktestRun,
} from '@/types/backtesterContracts';
import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';

const routerMock = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('vue-router', () => ({ useRouter: () => routerMock }));
vi.mock('@/api/backtesterClient', () => ({
  fetchStrategyCatalog: vi.fn().mockResolvedValue([
    {
      strategy_id: 'sma',
      strategy_version: 1,
      display_name: 'SMA',
      parameters: [
        {
          name: 'fast',
          type: 'int',
          required: false,
          nullable: false,
          default: 5,
        },
      ],
    },
  ]),
  previewBacktest: vi
    .fn()
    .mockImplementation(() => new Promise<never>(() => {})),
  cancelBacktestRun: vi.fn(),
  controlBacktest: vi.fn(),
  renameExperiment: vi.fn(),
  deleteBacktest: vi.fn(),
  fetchBacktestClosedTrades: vi.fn(),
  fetchBacktestEquityCurve: vi.fn(),
  fetchBacktestFills: vi.fn(),
  fetchBacktestQueue: vi.fn(),
  fetchBacktestCapabilities: vi.fn().mockResolvedValue({
    max_backtest_candidate_count: 1000,
  }),
  getBacktestRun: vi.fn(),
  getBacktest: vi.fn(),
  listBacktestEvents: vi.fn(),
  listBacktestMembers: vi.fn(),
  listBacktests: vi.fn(),
  listBacktestRuns: vi.fn(),
}));

export function run(
  id: string,
  overrides: Partial<BacktestRun> = {},
): BacktestRun {
  return {
    backtest_id: 'backtest-1',
    run_ordinal: 0,
    run_id: id,
    status: 'succeeded',
    submitted_at_ms: 1_780_921_805_123,
    started_at_ms: 1_780_921_900_000,
    completed_at_ms: 1_780_922_100_000,
    request_schema_version: 2,
    request: {
      symbols: ['EURUSD'],
      exchange: 'FX',
      timeframe: 'M15',
      start_ms: 1_714_521_600_000,
      end_ms: 1_714_608_000_000,
      engine: 'event_driven',
      data_granularity: 'bar',
      initial_capital: 10000,
      strategy: { strategy_id: 'sma', parameters: { fast: 10 } },
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
    },
    result_schema_version: 3,
    metrics: {
      total_return_pct: -1.25,
      max_drawdown_pct: -2.5,
      trade_count: 0,
      long_trade_count: 0,
      short_trade_count: 0,
      long_win_rate_pct: 0,
      short_win_rate_pct: 0,
      long_realized_pnl: 0,
      short_realized_pnl: 0,
    },
    ...overrides,
  };
}

export function backtest(id: string, members: number): Backtest {
  return {
    backtest_id: id,
    submission_id: `${id}-submission`,
    status: 'completed',
    accepted_at_ms: 1_780_000_000_000,
    started_at_ms: 1_780_000_001_000,
    completed_at_ms: 1_780_000_002_000,
    active_run_ordinal: null,
    next_run_ordinal: null,
    lifecycle_revision: 1,
    definition_schema_version: 1,
    accepted_definition: {
      schema_version: 1,
      shared_request: {
        start_ms: 1_714_521_600_000,
        end_ms: 1_714_608_000_000,
      },
      normalized_selections: {
        markets: [{ symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }],
        timeframes: ['M15'],
        parameters: {},
        allowed_directions: ['long_and_short'],
      },
    },
    strategy_metadata: {
      strategy_id: 'sma',
      strategy_version: 1,
      display_name: 'SMA',
      parameters: [],
    },
    raw_count: members,
    member_count: members,
    excluded_count: 0,
    total_count: members,
    settled_count: members,
    executed_count: members,
    outcome_counts: {
      queued: 0,
      running: 0,
      cancelling: 0,
      succeeded: members,
      failed: 0,
      cancelled: 0,
    },
    has_failed_members: false,
    markets: ['EURUSD'],
    exchanges: ['FX'],
    market_contexts: [{ symbol: 'EURUSD', exchange: 'FX' }],
    timeframes: ['M15'],
    strategy_id: 'sma',
    strategy_version: 1,
  };
}

export function mountWorkspace(includeBacktestDetail = false) {
  const wrapper = mount(DesignScope, {
    slots: { default: () => h(BacktestWorkspaceView) },
    global: {
      plugins: [pinia],
      stubs: {
        EquityReplayCharts: true,
        BacktestOverview: !includeBacktestDetail,
      },
    },
  });
  onTestFinished(() => wrapper.unmount());
  return wrapper;
}

export async function toggleAnalysisColumns(
  wrapper: ReturnType<typeof mountWorkspace>,
  keys: string[],
) {
  await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
  await flushPromises();
  for (const key of keys) {
    const checkbox = document.querySelector<HTMLElement>(
      `[data-testid="comparison-column-${key}"]`,
    );
    expect(checkbox, `Column checkbox ${key}`).not.toBeNull();
    checkbox!.click();
    await flushPromises();
  }
  await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
  await flushPromises();
}

export function trade(
  sequence: number,
  direction: 'long' | 'short',
  reason: 'signal' | 'stop_loss' | 'take_profit',
): BacktestClosedTrade {
  return {
    sequence,
    trade_id: `trade-${sequence}`,
    symbol: 'EURUSD',
    trade_direction: direction,
    quantity: 1000,
    entry_timestamp_ms: 1_714_525_200_000,
    entry_price: 1.0715,
    exit_timestamp_ms: 1_714_532_400_000,
    exit_price: 1.074,
    realized_pnl: direction === 'long' ? 2.5 : -3,
    fees: 0.3,
    exit_reason: reason,
    stop_loss_price: direction === 'short' ? 1.08 : null,
    take_profit_price: 1.065,
  };
}

export function fill(sequence: number, side: 'buy' | 'sell'): BacktestFill {
  return {
    sequence,
    timestamp_ms: 1_714_525_200_000,
    symbol: 'EURUSD',
    side,
    quantity: 2000,
    price: 1.074,
    fees: 0.3,
    exit_reason: null,
  };
}

export let pinia: Pinia;
export function setupWorkspaceTests() {
  beforeEach(() => {
    installBacktestSocket();
    pinia = createPinia();
    setActivePinia(pinia);
    localStorage.clear();
    routerMock.push.mockReset();
    vi.mocked(listBacktestRuns).mockReset();
    vi.mocked(listBacktests).mockReset().mockResolvedValue([]);
    vi.mocked(getBacktest).mockReset();
    vi.mocked(listBacktestMembers).mockReset();
    vi.mocked(listBacktestEvents).mockReset();
    vi.mocked(getBacktestRun).mockReset();
    vi.mocked(renameExperiment).mockReset();
    vi.mocked(cancelBacktestRun).mockReset();
    vi.mocked(controlBacktest).mockReset();
    vi.mocked(deleteBacktest).mockReset();
    vi.mocked(fetchBacktestClosedTrades).mockReset();
    vi.mocked(fetchBacktestEquityCurve).mockReset();
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({
      availability: 'unavailable',
      reason: 'replay_metadata_missing',
      source_point_count: 0,
      returned_point_count: 0,
      sampled: false,
      equity_curve: [],
    });
    vi.mocked(fetchBacktestFills).mockReset();
    vi.mocked(fetchBacktestQueue).mockReset().mockResolvedValue({
      snapshot_at_ms: Date.now(),
      active_run: null,
      last_heartbeat_ms: Date.now(),
      availability: 'healthy',
      stale_after_ms: 30_000,
      operational_faults: [],
      queued: [],
    });
    vi.mocked(deleteBacktest).mockResolvedValue();
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([]);
    vi.mocked(fetchBacktestFills).mockResolvedValue([]);
    useMarketsStore().all = [
      {
        symbol_id: 1,
        symbol: 'EURUSD',
        exchange: 'FX',
        market_type: 'Forex',
        min_move: 0.00001,
        timezone: 'UTC',
      },
    ];
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
}

export { routerMock };

export function seedBacktest(members: BacktestRun[]) {
  const id = members[0].run_id;
  members.forEach((member, ordinal) => {
    member.backtest_id = id;
    member.run_ordinal = ordinal;
  });
  const accepted = backtest(id, members.length);
  vi.mocked(listBacktests).mockResolvedValue([accepted]);
  vi.mocked(getBacktest).mockResolvedValue(accepted);
  vi.mocked(listBacktestMembers).mockResolvedValue(members);
  vi.mocked(listBacktestEvents).mockResolvedValue([]);
  vi.mocked(getBacktestRun).mockImplementation(
    async (id) => members.find((run) => run.run_id === id)!,
  );
  return accepted;
}
