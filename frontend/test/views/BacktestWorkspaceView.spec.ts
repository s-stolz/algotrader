import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia, type Pinia } from 'pinia';
import { NSelect } from 'naive-ui';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  deleteBacktestRun, fetchBacktestClosedTrades, getBacktestRun, listBacktestRuns,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestRun } from '@/types/backtesterContracts';
import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';

const routerMock = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('vue-router', () => ({ useRouter: () => routerMock }));
vi.mock('@/api/backtesterClient', () => ({
  deleteBacktestRun: vi.fn(),
  fetchBacktestClosedTrades: vi.fn(),
  getBacktestRun: vi.fn(),
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

function mountWorkspace() {
  return mount(BacktestWorkspaceView, {
    global: { plugins: [pinia] },
  });
}

let pinia: Pinia;
describe('production Backtest Workspace', () => {
  beforeEach(() => {
    pinia = createPinia();
    setActivePinia(pinia);
    localStorage.clear();
    routerMock.push.mockReset();
    vi.mocked(listBacktestRuns).mockReset();
    vi.mocked(getBacktestRun).mockReset();
    vi.mocked(deleteBacktestRun).mockReset();
    vi.mocked(fetchBacktestClosedTrades).mockReset();
    vi.mocked(deleteBacktestRun).mockResolvedValue();
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([]);
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
    expect(wrapper.text()).toContain('current lifecycle status is unknown');
    expect(wrapper.find('[data-testid="workspace-run-success"]').exists()).toBe(true);

    await wrapper.find('[data-testid="workspace-delete-success"]').trigger('click');
    await flushPromises();
    expect(deleteBacktestRun).toHaveBeenCalledWith('success');
    expect(wrapper.text()).toContain('No saved Backtest Runs.');
    expect(wrapper.text()).not.toContain('current lifecycle status is unknown');
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

  it('refreshes lifecycle state periodically only while mounted', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    vi.mocked(listBacktestRuns)
      .mockResolvedValueOnce([run('active', { status: 'running', metrics: null })])
      .mockResolvedValueOnce([run('active', { status: 'succeeded' })]);
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-run-active"]').text()).toContain('running');

    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-run-active"]').text()).toContain('succeeded');

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
