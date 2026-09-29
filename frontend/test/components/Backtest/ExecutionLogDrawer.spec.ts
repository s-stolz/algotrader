import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia, type Pinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NSelect } from 'naive-ui';

import {
  fetchBacktestClosedTrades, fetchBacktestFills, getBacktestRun, listBacktestBatches, listBacktestRuns,
} from '@/api/backtesterClient';
import ExecutionLogDrawer from '@/components/Backtest/ExecutionLogDrawer.vue';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestClosedTrade, BacktestFill, BacktestRun } from '@/types/backtesterContracts';
import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn(),
  currentRoute: { value: { query: {} } } }) }));
vi.mock('@/api/backtesterClient', () => ({
  deleteBacktestRun: vi.fn(),
  fetchBacktestClosedTrades: vi.fn(),
  fetchBacktestFills: vi.fn(),
  getBacktestRun: vi.fn(),
  listBacktestBatches: vi.fn(),
  listBacktestRuns: vi.fn(),
}));

function run(runId: string): BacktestRun {
  return {
    run_id: runId, status: 'succeeded', submitted_at_ms: 1_780_921_805_123,
    request_schema_version: 2, result_schema_version: 3,
    request: {
      symbols: ['EURUSD'], exchange: 'FX', timeframe: 'M15',
      start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000,
      engine: 'event_driven', data_granularity: 'bar', initial_capital: 10_000,
      strategy: { strategy_id: 'sma', parameters: {} },
      execution: {
        signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
        allow_partial_fills: false, allowed_directions: 'long_and_short',
        trade_accounting_policy: 'average_cost', gap_policy: 'skip',
        intrabar_exit_policy: 'conservative', commission_bps: 1, slippage_bps: 0,
      },
      persist_result: true,
    },
    metrics: { trade_count: 2, total_return_pct: 1.25 },
  };
}

function trade(sequence: number, direction: 'long' | 'short',
  entry: number, exit: number): BacktestClosedTrade {
  return {
    sequence, trade_id: `trade-${sequence}`, symbol: 'EURUSD', trade_direction: direction,
    quantity: 1000, entry_timestamp_ms: entry, entry_price: 1.0715,
    exit_timestamp_ms: exit, exit_price: 1.074, realized_pnl: direction === 'long' ? 2.5 : -3,
    fees: 0.3, exit_reason: 'signal', stop_loss_price: null, take_profit_price: null,
  };
}

function fill(sequence: number, side: 'buy' | 'sell',
  timestamp: number, quantity: number): BacktestFill {
  return { sequence, timestamp_ms: timestamp, symbol: 'EURUSD', side,
    quantity, price: 1.074, fees: 0.3, exit_reason: null };
}

let pinia: Pinia;
beforeEach(() => {
  pinia = createPinia();
  setActivePinia(pinia);
  vi.mocked(fetchBacktestClosedTrades).mockReset();
  vi.mocked(fetchBacktestFills).mockReset();
  vi.mocked(getBacktestRun).mockReset();
  vi.mocked(listBacktestRuns).mockReset();
  vi.mocked(listBacktestBatches).mockReset().mockResolvedValue([]);
  useMarketsStore().all = [{
    symbol_id: 1, symbol: 'EURUSD', exchange: 'FX', market_type: 'Forex',
    min_move: 0.00001, timezone: 'UTC',
  }];
});

describe('execution-log drawer', () => {
  it('shows one flip Fill closing a long and opening a short without deriving Trade Direction from Fill side', async () => {
    const entry = 1_714_525_200_000;
    const flip = 1_714_532_400_000;
    const shortExit = 1_714_539_600_000;
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([
      trade(0, 'long', entry, flip), trade(1, 'short', flip, shortExit),
    ]);
    vi.mocked(fetchBacktestFills).mockResolvedValue([
      fill(0, 'buy', entry, 1000), fill(1, 'sell', flip, 2000),
      fill(2, 'buy', shortExit, 1000),
    ]);
    const wrapper = mount(ExecutionLogDrawer, { props: { run: run('flip'), show: true } });
    await flushPromises();

    expect(document.body.textContent).toContain('Closed Trades (2)');
    expect(document.body.textContent).toContain('Fills (3)');
    const tradeRows = [...document.body.querySelectorAll<HTMLTableRowElement>(
      '[data-testid="execution-trades-table"] tbody tr',
    )];
    expect(tradeRows.map((row) => row.cells[1].textContent)).toEqual(['long', 'short']);
    expect(tradeRows[0].cells[2].textContent).toBe('01 May 2024, 01:00:00');
    expect(tradeRows[0].cells[4].textContent).toBe('01 May 2024, 03:00:00');
    expect(tradeRows[1].cells[2].textContent).toBe('01 May 2024, 03:00:00');

    document.body.querySelector<HTMLButtonElement>('[data-testid="execution-fills-tab"]')!.click();
    await wrapper.vm.$nextTick();
    const fillRows = [...document.body.querySelectorAll<HTMLTableRowElement>(
      '[data-testid="execution-fills-table"] tbody tr',
    )];
    expect(fillRows.map((row) => row.cells[2].textContent)).toEqual(['buy', 'sell', 'buy']);
    expect(fillRows[0].cells[1].textContent).toBe('01 May 2024, 01:00:00');
    expect(fillRows[1].cells[1].textContent).toBe(tradeRows[0].cells[4].textContent);
    expect(fillRows[1].cells[3].textContent).toBe('2000');
    wrapper.unmount();
  });

  it('combines the Naive UI trade filters and keeps Fills unfiltered across tab changes', async () => {
    const timestamp = 1_714_525_200_000;
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([
      trade(0, 'long', timestamp, timestamp + 60_000),
      { ...trade(1, 'short', timestamp, timestamp + 60_000), exit_reason: 'stop_loss' },
      { ...trade(2, 'long', timestamp, timestamp + 60_000), exit_reason: 'take_profit' },
    ]);
    vi.mocked(fetchBacktestFills).mockResolvedValue([
      fill(0, 'buy', timestamp, 1000), fill(1, 'sell', timestamp + 60_000, 1000),
    ]);
    const wrapper = mount(ExecutionLogDrawer, { props: { run: run('filters'), show: true } });
    await flushPromises();
    const rows = () => [...document.body.querySelectorAll<HTMLTableRowElement>(
      '[data-testid="execution-trades-table"] tbody tr',
    )].map((row) => row.cells[0].textContent);
    expect(document.body.querySelector('[data-testid="execution-log-drawer"] input[type="search"]')).toBeNull();
    expect(document.body.querySelector('[data-testid="execution-log-drawer"] select')).toBeNull();
    expect(rows()).toEqual(['0', '1', '2']);

    wrapper.findAllComponents(NSelect)[0].vm.$emit('update:value', 'long');
    await wrapper.vm.$nextTick();
    expect(rows()).toEqual(['0', '2']);
    wrapper.findAllComponents(NSelect)[1].vm.$emit('update:value', 'take_profit');
    await wrapper.vm.$nextTick();
    expect(rows()).toEqual(['2']);
    wrapper.findAllComponents(NSelect)[0].vm.$emit('update:value', 'short');
    await wrapper.vm.$nextTick();
    expect(document.body.textContent).toContain('No Closed Trades match these filters.');

    document.body.querySelector<HTMLElement>('[data-testid="execution-fills-tab"]')!.click();
    await wrapper.vm.$nextTick();
    expect(wrapper.findAllComponents(NSelect)).toHaveLength(0);
    expect(document.body.querySelectorAll('[data-testid="execution-fills-table"] tbody tr')).toHaveLength(2);
    document.body.querySelector<HTMLElement>('[data-testid="execution-trades-tab"]')!.click();
    await wrapper.vm.$nextTick();
    wrapper.findAllComponents(NSelect)[0].vm.$emit('update:value', 'all');
    wrapper.findAllComponents(NSelect)[1].vm.$emit('update:value', 'all');
    await wrapper.vm.$nextTick();
    expect(rows()).toEqual(['0', '1', '2']);
    wrapper.unmount();
  });

  it('ignores a pending log read after close and leaves a later run and Workspace selection intact', async () => {
    const first = run('first');
    const second = run('second');
    const timestamp = 1_714_525_200_000;
    let resolveFirst!: (trades: BacktestClosedTrade[]) => void;
    vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
    vi.mocked(getBacktestRun).mockResolvedValue(first);
    vi.mocked(fetchBacktestClosedTrades).mockImplementation((id) => id === 'first'
      ? new Promise((resolve) => { resolveFirst = resolve; })
      : Promise.resolve([trade(1, 'short', timestamp, timestamp + 60_000)]));
    vi.mocked(fetchBacktestFills).mockResolvedValue([]);
    const wrapper = mount(BacktestWorkspaceView, { global: { plugins: [pinia],
      stubs: { EquityReplayCharts: true } } });
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-first"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-log-first"]').trigger('click');
    await flushPromises();
    expect(document.body.textContent).toContain('Loading execution log');

    document.body.querySelector<HTMLButtonElement>('.n-drawer-header__close')!.click();
    await wrapper.vm.$nextTick();
    expect(document.body.querySelector('[data-testid="execution-log-drawer"]')).toBeNull();
    resolveFirst([trade(0, 'long', timestamp, timestamp + 60_000)]);
    await flushPromises();
    expect(document.body.querySelector('[data-testid="execution-log-drawer"]')).toBeNull();
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
    await wrapper.find('[data-testid="workspace-log-second"]').trigger('click');
    await flushPromises();

    expect(document.body.textContent).toContain('Execution log · second');
    expect(document.body.textContent).toContain('short');
    expect(document.body.textContent).not.toContain('long');
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('1.25%');
    wrapper.unmount();
  });
});
