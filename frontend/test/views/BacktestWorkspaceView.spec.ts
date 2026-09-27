import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia, type Pinia } from 'pinia';
import { NSelect } from 'naive-ui';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  cancelBacktestRun, deleteBacktestRun, fetchBacktestClosedTrades, fetchBacktestEquityCurve,
  fetchBacktestFills, fetchBacktestQueue, getBacktestBatch, getBacktestRun, listBacktestBatchEvents,
  listBacktestBatchMembers, listBacktestBatches, listBacktestRuns,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestBatch, BacktestClosedTrade, BacktestFill, BacktestRun } from '@/types/backtesterContracts';
import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';

const routerMock = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('vue-router', () => ({ useRouter: () => routerMock }));
vi.mock('@/api/backtesterClient', () => ({
  cancelBacktestRun: vi.fn(),
  deleteBacktestRun: vi.fn(),
  fetchBacktestClosedTrades: vi.fn(),
  fetchBacktestEquityCurve: vi.fn(),
  fetchBacktestFills: vi.fn(),
  fetchBacktestQueue: vi.fn(),
  getBacktestRun: vi.fn(),
  getBacktestBatch: vi.fn(),
  listBacktestBatchEvents: vi.fn(),
  listBacktestBatchMembers: vi.fn(),
  listBacktestBatches: vi.fn(),
  listBacktestRuns: vi.fn(),
}));

function run(id: string, overrides: Partial<BacktestRun> = {}): BacktestRun {
  return {
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
      persist_result: true,
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

function mountWorkspace(includeBatchDetail = false) {
  return mount(BacktestWorkspaceView, {
    global: { plugins: [pinia], stubs: { EquityReplayCharts: true,
      BacktestBatches: !includeBatchDetail } },
  });
}

function trade(sequence: number, direction: 'long' | 'short',
  reason: 'signal' | 'stop_loss' | 'take_profit'): BacktestClosedTrade {
  return {
    sequence, trade_id: `trade-${sequence}`, symbol: 'EURUSD', trade_direction: direction,
    quantity: 1000, entry_timestamp_ms: 1_714_525_200_000,
    entry_price: 1.0715, exit_timestamp_ms: 1_714_532_400_000,
    exit_price: 1.074, realized_pnl: direction === 'long' ? 2.5 : -3,
    fees: 0.3, exit_reason: reason,
    stop_loss_price: direction === 'short' ? 1.08 : null,
    take_profit_price: 1.065,
  };
}

function fill(sequence: number, side: 'buy' | 'sell'): BacktestFill {
  return { sequence, timestamp_ms: 1_714_525_200_000, symbol: 'EURUSD',
    side, quantity: 2000, price: 1.074, fees: 0.3, exit_reason: null };
}

let pinia: Pinia;
describe('production Backtest Workspace', () => {
  beforeEach(() => {
    pinia = createPinia();
    setActivePinia(pinia);
    localStorage.clear();
    routerMock.push.mockReset();
    vi.mocked(listBacktestRuns).mockReset();
    vi.mocked(listBacktestBatches).mockReset().mockResolvedValue([]);
    vi.mocked(getBacktestBatch).mockReset();
    vi.mocked(listBacktestBatchMembers).mockReset();
    vi.mocked(listBacktestBatchEvents).mockReset();
    vi.mocked(getBacktestRun).mockReset();
    vi.mocked(cancelBacktestRun).mockReset();
    vi.mocked(deleteBacktestRun).mockReset();
    vi.mocked(fetchBacktestClosedTrades).mockReset();
    vi.mocked(fetchBacktestEquityCurve).mockReset();
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({
      availability: 'unavailable', reason: 'replay_metadata_missing',
      source_point_count: 0, returned_point_count: 0, sampled: false, equity_curve: [],
    });
    vi.mocked(fetchBacktestFills).mockReset();
    vi.mocked(fetchBacktestQueue).mockReset().mockResolvedValue({
      snapshot_at_ms: Date.now(), active_run: null, last_heartbeat_ms: Date.now(),
      availability: 'healthy', stale_after_ms: 30_000, operational_faults: [], queued: [],
    });
    vi.mocked(deleteBacktestRun).mockResolvedValue();
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([]);
    vi.mocked(fetchBacktestFills).mockResolvedValue([]);
    useMarketsStore().all = [{
      symbol_id: 1, symbol: 'EURUSD', exchange: 'FX', market_type: 'Forex',
      min_move: 0.00001, timezone: 'UTC',
    }];
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('shows real saved history, selects one run, and retains signed metric semantics', async () => {
    const success = run('success', {
      request: { ...run('x').request, run_metadata: { name: 'Baseline' } },
    });
    const failed = run('failed', { status: 'failed', metrics: null, error_message: 'No candles' });
    vi.mocked(listBacktestRuns).mockResolvedValue([success, failed]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);

    const wrapper = mountWorkspace();
    await flushPromises();

    expect(wrapper.find('[data-testid="workspace-history"]').text()).toContain('Baseline');
    expect(wrapper.find('[data-testid="workspace-history"]').text()).toContain('failed');
    expect(wrapper.text()).toContain('Version unavailable');

    await wrapper.find('[data-testid="workspace-run-success"]').trigger('click');
    await flushPromises();

    const current = wrapper.find('[data-testid="workspace-current-backtest"]');
    expect(current.text()).toContain('-1.25%');
    expect(current.text()).toContain('2.5%');
    expect(current.text()).toContain('No trades');
    expect(current.text()).toContain('10000');
    expect(current.text()).not.toContain('Ending equity');
    expect(wrapper.text()).toContain('Saved request and execution settings');
    wrapper.unmount();
  });

  it('opens the accessible execution drawer without changing selection and filters distinct trades and fills', async () => {
    const first = run('first', { request: { ...run('x').request, run_metadata: { name: 'First run' } } });
    const second = run('second');
    vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
    vi.mocked(getBacktestRun).mockResolvedValue(first);
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([
      trade(0, 'long', 'take_profit'), trade(1, 'short', 'stop_loss'),
    ]);
    vi.mocked(fetchBacktestFills).mockResolvedValue([fill(0, 'buy'), fill(1, 'sell')]);
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-first"]').trigger('click');
    await flushPromises();

    const icon = wrapper.find('[data-testid="workspace-current-backtest"] [data-testid="workspace-log-first"]');
    expect(icon.attributes('aria-label')).toBe('View execution log for First run');
    expect(icon.attributes('title')).toBeUndefined();
    await icon.trigger('click');
    await flushPromises();
    expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('first');
    expect(fetchBacktestFills).toHaveBeenCalledWith('first');
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
    expect(document.body.textContent).toContain('Closed Trades (2)');
    expect(document.body.textContent).toContain('Fills (2)');
    expect(document.body.textContent).toContain('2024-05-01T01:00:00.000Z');
    expect(document.body.textContent).toContain('-3');
    expect(document.body.textContent).toContain('1.08');

    const direction = document.body.querySelector<HTMLSelectElement>('[data-testid="execution-direction"]')!;
    direction.value = 'short';
    direction.dispatchEvent(new Event('change', { bubbles: true }));
    await wrapper.vm.$nextTick();
    expect(document.body.querySelectorAll('[data-testid="execution-trades-table"] tbody tr')).toHaveLength(1);
    expect(document.body.textContent).toContain('stop loss');
    const reason = document.body.querySelector<HTMLSelectElement>('[data-testid="execution-exit-reason"]')!;
    reason.value = 'signal';
    reason.dispatchEvent(new Event('change', { bubbles: true }));
    await wrapper.vm.$nextTick();
    expect(document.body.textContent).toContain('No Closed Trades match these filters.');

    document.body.querySelector<HTMLButtonElement>('[data-testid="execution-fills-tab"]')!.click();
    await wrapper.vm.$nextTick();
    expect(document.body.querySelectorAll('[data-testid="execution-fills-table"] tbody tr')).toHaveLength(2);
    expect(document.body.textContent).toContain('sell');
    const fillSearch = document.body.querySelector<HTMLInputElement>('[data-testid="execution-search"]')!;
    fillSearch.value = 'sell';
    fillSearch.dispatchEvent(new Event('input', { bubbles: true }));
    await wrapper.vm.$nextTick();
    expect(document.body.querySelectorAll('[data-testid="execution-fills-table"] tbody tr')).toHaveLength(1);
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
    document.body.querySelector<HTMLButtonElement>('.n-drawer-header__close')!.click();
    await wrapper.vm.$nextTick();
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('First run');
    wrapper.unmount();
  });

  it('distinguishes no executions, no matches, unavailable logs, and runs without completed logs', async () => {
    const success = run('success');
    const failed = run('failed', { status: 'failed', metrics: null });
    vi.mocked(listBacktestRuns).mockResolvedValue([success, failed]);
    const wrapper = mountWorkspace();
    await flushPromises();

    await wrapper.find('[data-testid="workspace-log-success"]').trigger('click');
    await flushPromises();
    expect(document.body.textContent).toContain('This successful run has no executions.');

    await wrapper.find('[data-testid="workspace-log-failed"]').trigger('click');
    await flushPromises();
    expect(document.body.textContent).toContain('failed run has no completed execution log');
    expect(fetchBacktestFills).toHaveBeenCalledTimes(1);

    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([trade(0, 'long', 'signal')]);
    vi.mocked(fetchBacktestFills).mockResolvedValue([fill(0, 'buy')]);
    await wrapper.find('[data-testid="workspace-log-success"]').trigger('click');
    await flushPromises();
    const search = document.body.querySelector<HTMLInputElement>('[data-testid="execution-search"]')!;
    search.value = 'unmatched';
    search.dispatchEvent(new Event('input', { bubbles: true }));
    await wrapper.vm.$nextTick();
    expect(document.body.textContent).toContain('No Closed Trades match these filters.');

    vi.mocked(fetchBacktestClosedTrades).mockRejectedValue(new Error('Storage unavailable'));
    await wrapper.find('[data-testid="workspace-log-failed"]').trigger('click');
    await wrapper.find('[data-testid="workspace-log-success"]').trigger('click');
    await flushPromises();
    expect(document.body.textContent).toContain('Execution log unavailable. Storage unavailable');
    wrapper.unmount();
  });

  it('ignores execution-log responses from a previous run or a closed drawer', async () => {
    const first = run('first');
    const second = run('second');
    vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
    let resolveFirst!: (trades: BacktestClosedTrade[]) => void;
    vi.mocked(fetchBacktestClosedTrades).mockImplementation((id) => id === 'first'
      ? new Promise((resolve) => { resolveFirst = resolve; })
      : Promise.resolve([trade(2, 'short', 'stop_loss')]));
    vi.mocked(fetchBacktestFills).mockResolvedValue([fill(0, 'sell')]);
    const wrapper = mountWorkspace();
    await flushPromises();

    const firstIcon = wrapper.find('[data-testid="workspace-log-first"]');
    expect(firstIcon.element.tagName).toBe('BUTTON');
    await firstIcon.trigger('keydown', { key: 'Enter' });
    expect(useBacktestWorkspaceStore().selectedRunId).toBeNull();
    await wrapper.find('[data-testid="workspace-log-first"]').trigger('click');
    await wrapper.find('[data-testid="workspace-log-second"]').trigger('click');
    await flushPromises();
    resolveFirst([trade(0, 'long', 'signal')]);
    await flushPromises();
    expect(document.body.textContent).toContain('Execution log · second');
    expect(document.body.textContent).toContain('short');
    expect(document.body.textContent).not.toContain('long');

    document.body.querySelector<HTMLButtonElement>('.n-drawer-header__close')!.click();
    await wrapper.vm.$nextTick();
    expect(document.body.querySelector('[data-testid="execution-log-drawer"]')).toBeNull();
    wrapper.unmount();
  });

  it('shows tiny saved Return, drawdown, and account-unit PnL values', async () => {
    const success = run('tiny', {
      metrics: {
        total_return_pct: -0.004,
        max_drawdown_pct: -0.004,
        long_realized_pnl: -0.003,
        short_realized_pnl: 0.002,
      },
    });
    vi.mocked(listBacktestRuns).mockResolvedValue([success]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-tiny"]').trigger('click');
    await flushPromises();

    const cells = wrapper.find('[data-testid="workspace-current-backtest"]')
      .findAll('td').map((cell) => cell.text());
    expect(cells).toContain('-0.004%');
    expect(cells).toContain('0.004%');
    expect(cells).toContain('-0.003');
    expect(cells).toContain('+0.002');
    wrapper.unmount();
  });

  it('filters by search, status, Market, Strategy, and Timeframe', async () => {
    const euro = run('euro', {
      request: { ...run('x').request, run_metadata: { name: 'Euro setup' } },
    });
    const pound = run('pound', {
      status: 'failed',
      request: {
        ...run('x').request,
        symbols: ['GBPUSD'],
        timeframe: 'H1',
        strategy: { strategy_id: 'breakout', parameters: {} },
      },
      metrics: null,
    });
    vi.mocked(listBacktestRuns).mockResolvedValue([euro, pound]);
    vi.mocked(getBacktestRun).mockResolvedValue(euro);
    const wrapper = mountWorkspace();
    await flushPromises();

    const history = () => wrapper.find('[data-testid="workspace-history"]');
    await wrapper.find('[data-testid="workspace-search"] input').setValue('Euro setup');
    expect(history().find('[data-testid="workspace-run-euro"]').exists()).toBe(true);
    expect(history().find('[data-testid="workspace-run-pound"]').exists()).toBe(false);
    await wrapper.find('[data-testid="workspace-search"] input').setValue('');

    for (const [index, value] of [
      [0, 'failed'],
      [2, 'FX:GBPUSD'],
      [3, 'breakout'],
      [4, 'H1'],
    ] as const) {
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', value);
      await wrapper.vm.$nextTick();
      expect(history().find('[data-testid="workspace-run-pound"]').exists()).toBe(true);
      expect(history().find('[data-testid="workspace-run-euro"]').exists()).toBe(false);
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', 'all');
      await wrapper.vm.$nextTick();
    }
    wrapper.unmount();
  });

  it('filters batches and standalone runs in one history without member rows', async () => {
    const standalone = run('standalone');
    const memberRun = run('member-0', { batch_id: 'batch-1', member_ordinal: 0,
      status: 'failed', metrics: null });
    const batch = {
      batch_id: 'batch-1', submission_id: 'submit-1', status: 'completed',
      accepted_at_ms: 1_780_000_000_000, lifecycle_revision: 1,
      started_at_ms: 1_780_000_001_000, completed_at_ms: 1_780_000_002_000,
      active_member_ordinal: null, next_member_ordinal: null,
      definition_schema_version: 1,
      accepted_definition: { schema_version: 1,
        shared_request: { start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000 },
        normalized_selections: { markets: [{ symbol_id: 2, symbol: 'GBPUSD', exchange: 'FX' },
          { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }],
          timeframes: ['H1', 'M15'], parameters: {}, allowed_directions: ['long_and_short'] } },
      strategy_metadata: { strategy_id: 'breakout', strategy_version: 1,
        display_name: 'Breakout', parameters: [] },
      raw_count: 2, member_count: 1, excluded_count: 1,
      total_count: 1, settled_count: 1, executed_count: 1,
      outcome_counts: { queued: 0, running: 0, cancelling: 0, succeeded: 0,
        failed: 1, cancelled: 0 },
      has_failed_members: true, markets: ['GBPUSD'], exchanges: ['FX'],
      market_contexts: [{ symbol: 'GBPUSD', exchange: 'FX' }], timeframes: ['H1'],
      strategy_id: 'breakout', strategy_version: 1,
    } as BacktestBatch;
    vi.mocked(listBacktestRuns).mockResolvedValue([standalone, memberRun]);
    vi.mocked(listBacktestBatches).mockResolvedValue([batch]);
    vi.mocked(getBacktestBatch).mockResolvedValue(batch);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([memberRun]);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([{ batch_id: 'batch-1', revision: 0,
      event_type: 'accepted', prior_status: null, status: 'queued', occurred_at_ms: batch.accepted_at_ms,
      trigger_run_id: null,
      reason: null }]);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    const history = () => wrapper.find('[data-testid="workspace-history"]');
    expect(history().findAll('tbody tr')).toHaveLength(2);
    expect(history().find('[data-testid="workspace-run-member-0"]').exists()).toBe(false);
    expect(history().find('[data-testid="workspace-batch-batch-1"]').text()).toContain('1 / 1');
    expect(history().find('[data-testid="workspace-batch-batch-1"]').text()).toContain('1 failed');
    await history().find('[data-testid="workspace-batch-batch-1"]').trigger('click');
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-batch-members"]').text()).toContain('member-0');
    expect(listBacktestBatchMembers).toHaveBeenCalledWith('batch-1');

    await wrapper.find('[data-testid="workspace-search"] input').setValue('submit-1');
    expect(history().find('[data-testid="workspace-batch-batch-1"]').exists()).toBe(true);
    expect(history().find('[data-testid="workspace-run-standalone"]').exists()).toBe(false);
    await wrapper.find('[data-testid="workspace-search"] input').setValue('');

    for (const [index, value] of [[0, 'completed'], [1, 'batch'], [2, 'FX:GBPUSD'],
      [3, 'breakout'], [4, 'H1'], [5, 'with_failed']] as const) {
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', value);
      await wrapper.vm.$nextTick();
      expect(history().find('[data-testid="workspace-batch-batch-1"]').exists()).toBe(true);
      expect(history().find('[data-testid="workspace-run-standalone"]').exists()).toBe(false);
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', 'all');
      await wrapper.vm.$nextTick();
    }
    for (const [index, excluded] of [[2, 'FX:EURUSD'], [4, 'M15']] as const) {
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', excluded);
      await wrapper.vm.$nextTick();
      expect(history().find('[data-testid="workspace-batch-batch-1"]').exists()).toBe(false);
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', 'all');
      await wrapper.vm.$nextTick();
    }
    const timeframeHeader = wrapper.findAll('th').find((header) => header.text().includes('Timeframe'));
    const orderedRows = () => history().findAll('tbody tr').map((row) => row.attributes('data-testid'));
    await timeframeHeader?.trigger('click');
    expect(orderedRows()).toEqual(['workspace-batch-batch-1', 'workspace-run-standalone']);
    await timeframeHeader?.trigger('click');
    expect(orderedRows()).toEqual(['workspace-run-standalone', 'workspace-batch-batch-1']);
    wrapper.unmount();
  });

  it('sorts history dates in both directions with deterministic rows', async () => {
    const older = run('older');
    const newer = run('newer', {
      request: { ...older.request, start_ms: older.request.start_ms + 86_400_000 },
    });
    vi.mocked(listBacktestRuns).mockResolvedValue([newer, older]);
    const wrapper = mountWorkspace();
    await flushPromises();

    const startHeader = wrapper.findAll('th').find((header) => header.text().includes('Start date'));
    expect(startHeader).toBeDefined();
    const rowIds = () => wrapper.find('[data-testid="workspace-history"]')
      .findAll('[data-testid^="workspace-run-"]')
      .map((row) => row.attributes('data-testid'));

    await startHeader?.trigger('click');
    expect(rowIds()).toEqual(['workspace-run-newer', 'workspace-run-older']);
    await startHeader?.trigger('click');
    expect(rowIds()).toEqual(['workspace-run-older', 'workspace-run-newer']);
    wrapper.unmount();
  });

  it('distinguishes failed reads from empty history and refreshes after deletion', async () => {
    const success = run('success');
    vi.mocked(listBacktestRuns).mockResolvedValueOnce([success]).mockRejectedValueOnce(
      new Error('Service unavailable'),
    ).mockResolvedValueOnce([]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    vi.stubGlobal('confirm', vi.fn(() => true));

    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-refresh"]').trigger('click');
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain('current lifecycle status is unknown');
    expect(wrapper.find('[data-testid="workspace-run-success"]').exists()).toBe(true);

    await wrapper.find('[data-testid="workspace-delete-success"]').trigger('click');
    await flushPromises();
    expect(deleteBacktestRun).toHaveBeenCalledWith('success');
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(3);
    expect(wrapper.text()).toContain('No saved Backtest Runs or Batches.');
    expect(wrapper.text()).not.toContain('current lifecycle status is unknown');
    wrapper.unmount();
  });

  it('cancels a queued standalone run once and refreshes its durable status', async () => {
    const queued = run('queued', {
      status: 'queued', started_at_ms: null, completed_at_ms: null,
      result_schema_version: null, metrics: null,
    });
    const cancelled = run('queued', {
      ...queued, status: 'cancelled', completed_at_ms: 1_780_922_100_000,
      cancel_requested_at_ms: 1_780_922_100_000,
      cancellation_source: 'user', cancellation_reason: 'user_requested',
    });
    vi.mocked(listBacktestRuns).mockResolvedValueOnce([queued]).mockResolvedValueOnce([cancelled]);
    vi.mocked(cancelBacktestRun).mockResolvedValue(cancelled);
    const wrapper = mountWorkspace();
    await flushPromises();

    const cancelButton = wrapper.find('[data-testid="workspace-cancel-queued"]');
    await cancelButton.trigger('click');
    await flushPromises();

    expect(cancelBacktestRun).toHaveBeenCalledOnce();
    expect(cancelBacktestRun).toHaveBeenCalledWith('queued');
    expect(wrapper.find('[data-testid="workspace-run-queued"]').text()).toContain('cancelled');
    expect(wrapper.find('[data-testid="workspace-cancel-queued"]').attributes('disabled'))
      .toBeDefined();
    wrapper.unmount();
  });

  it('sends one DELETE for rapid duplicate clicks and disables that run while deleting', async () => {
    const success = run('success');
    let finishDelete!: () => void;
    vi.mocked(listBacktestRuns).mockResolvedValueOnce([success]).mockResolvedValueOnce([]);
    vi.mocked(deleteBacktestRun)
      .mockImplementationOnce(() => new Promise((resolve) => { finishDelete = resolve; }))
      .mockRejectedValueOnce(new Error('404 Not Found'));
    const confirm = vi.fn(() => true);
    vi.stubGlobal('confirm', confirm);
    const wrapper = mountWorkspace();
    await flushPromises();

    const deleteButton = wrapper.find('[data-testid="workspace-delete-success"]');
    deleteButton.element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    deleteButton.element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await wrapper.vm.$nextTick();

    expect(deleteBacktestRun).toHaveBeenCalledOnce();
    expect(confirm).toHaveBeenCalledOnce();
    expect(wrapper.find('[data-testid="workspace-delete-success"]').attributes('disabled'))
      .toBeDefined();

    finishDelete();
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-run-success"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('404 Not Found');
    wrapper.unmount();
  });

  it('reports an unavailable initial history read without calling it empty', async () => {
    vi.mocked(listBacktestRuns).mockRejectedValue(new Error('Service unavailable'));
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.text()).toContain('current lifecycle status is unknown');
    expect(wrapper.text()).not.toContain('No saved Backtest Runs.');
    wrapper.unmount();
  });

  it('shows reconciled failure and preserves queued work on Workspace refresh', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const queued = run('waiting', { status: 'queued', metrics: null });
    const interrupted = run('active', {
      status: 'failed', metrics: null, error_code: 'worker_interrupted',
      error_message: 'Backtest worker was interrupted before completion',
    });
    vi.mocked(listBacktestRuns)
      .mockResolvedValueOnce([run('active', { status: 'running', metrics: null }), queued])
      .mockResolvedValueOnce([interrupted, queued]);
    vi.mocked(getBacktestRun).mockResolvedValue(interrupted);
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-run-active"]').text()).toContain('running');

    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-run-active"]').text()).toContain('failed');
    expect(wrapper.find('[data-testid="workspace-run-waiting"]').text()).toContain('queued');
    await wrapper.find('[data-testid="workspace-run-active"]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain(
      'Backtest worker was interrupted before completion',
    );

    wrapper.unmount();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(listBacktestRuns).toHaveBeenCalledTimes(2);
  });

  it('accepts a history response that takes longer than the polling interval', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    let resolveRead!: (runs: BacktestRun[]) => void;
    vi.mocked(listBacktestRuns).mockImplementationOnce(
      () => new Promise((resolve) => { resolveRead = resolve; }),
    );
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.text()).toContain('Loading saved runs');

    vi.advanceTimersByTime(6000);
    expect(listBacktestRuns).toHaveBeenCalledOnce();
    resolveRead([run('slow-success')]);
    await flushPromises();

    expect(wrapper.find('[data-testid="workspace-run-slow-success"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Loading saved runs');
    wrapper.unmount();
  });

  it('shows a slow read error after a polling interval instead of loading forever', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    let rejectRead!: (error: Error) => void;
    vi.mocked(listBacktestRuns).mockImplementationOnce(
      () => new Promise((_, reject) => { rejectRead = reject; }),
    );
    const wrapper = mountWorkspace();
    await flushPromises();

    vi.advanceTimersByTime(6000);
    expect(listBacktestRuns).toHaveBeenCalledOnce();
    rejectRead(new Error('Slow service failure'));
    await flushPromises();

    expect(wrapper.text()).toContain('Slow service failure');
    expect(wrapper.text()).toContain('current lifecycle status is unknown');
    expect(wrapper.text()).not.toContain('Loading saved runs');
    wrapper.unmount();
  });

  it('coalesces a manual refresh requested during an active history read', async () => {
    let resolveRead!: (runs: BacktestRun[]) => void;
    vi.mocked(listBacktestRuns)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveRead = resolve; }))
      .mockResolvedValueOnce([run('active', { status: 'succeeded' })]);
    const wrapper = mountWorkspace();
    await flushPromises();

    await wrapper.find('[data-testid="workspace-refresh"]').trigger('click');
    expect(listBacktestRuns).toHaveBeenCalledOnce();
    resolveRead([run('active', { status: 'running', metrics: null })]);
    await flushPromises();

    expect(listBacktestRuns).toHaveBeenCalledTimes(2);
    expect(wrapper.find('[data-testid="workspace-run-active"]').text()).toContain('succeeded');
    wrapper.unmount();
  });

  it('ignores detail responses for a selection that has since changed', async () => {
    const first = run('first');
    const second = run('second', { status: 'failed', metrics: null });
    let resolveFirst!: (value: BacktestRun) => void;
    vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
    vi.mocked(getBacktestRun).mockImplementation((id) => id === 'first'
      ? new Promise((resolve) => { resolveFirst = resolve; })
      : Promise.resolve(second));

    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-first"]').trigger('click');
    await wrapper.find('[data-testid="workspace-run-second"]').trigger('click');
    await flushPromises();
    resolveFirst(first);
    await flushPromises();

    expect(useBacktestWorkspaceStore().selectedRunId).toBe('second');
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('failed');
    wrapper.unmount();
  });

  it('shows sampled exact equity beside saved Return and Initial capital', async () => {
    const success = run('success');
    vi.mocked(listBacktestRuns).mockResolvedValue([success]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({
      availability: 'exact', reason: null, source_point_count: 5000,
      returned_point_count: 2, sampled: true,
      equity_curve: [
        { timestamp_ms: 1_714_521_600_000, equity: 10000, drawdown_pct: 0 },
        { timestamp_ms: 1_714_608_000_000, equity: 9875, drawdown_pct: -1.25 },
      ],
    });
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-success"]').trigger('click');
    await flushPromises();

    expect(fetchBacktestEquityCurve).toHaveBeenCalledWith('success');
    expect(wrapper.text()).toContain('Ending equity: 9875');
    expect(wrapper.text()).toContain('Showing 2 of 5000 exact points (sampled).');
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('-1.25%');
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('10000');
    wrapper.unmount();
  });

  it('hands eligible saved runs to the chart overlay and returns to the chart', async () => {
    const success = run('success');
    vi.mocked(listBacktestRuns).mockResolvedValue([success]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    routerMock.push.mockResolvedValue(undefined);

    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-success"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-open-chart"]').trigger('click');
    await flushPromises();

    expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('success');
    expect(routerMock.push).toHaveBeenCalledWith('/');
    wrapper.unmount();
  });

  it('keeps an unsupported result inspectable with an explanation instead of chart navigation', async () => {
    const legacy = run('legacy', { result_schema_version: 2 });
    vi.mocked(listBacktestRuns).mockResolvedValue([legacy]);
    vi.mocked(getBacktestRun).mockResolvedValue(legacy);
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-legacy"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('-1.25%');
    expect(wrapper.text()).toContain('Backtest Run result schema is unsupported.');
    expect(wrapper.find('[data-testid="workspace-open-chart"]').attributes('disabled')).toBeDefined();
    expect(routerMock.push).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
