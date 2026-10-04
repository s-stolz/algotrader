import { flushPromises, mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { createPinia, setActivePinia, type Pinia } from 'pinia';
import { NCheckbox, NDataTable, NPagination, NSelect } from 'naive-ui';
import ExecutionLogDrawer from '@/components/Backtest/ExecutionLogDrawer.vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  cancelBacktestRun, controlBacktestBatch, deleteBacktestBatch, deleteBacktestRun, fetchBacktestClosedTrades, fetchBacktestEquityCurve,
  fetchBacktestFills, fetchBacktestQueue, getBacktestBatch, getBacktestRun, listBacktestBatchEvents,
  listBacktestBatchMembers, listBacktestBatches, listBacktestRuns,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestBatch, BacktestClosedTrade, BacktestFill, BacktestRun, EquityReplayResponse } from '@/types/backtesterContracts';
import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';

const routerMock = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('vue-router', () => ({ useRouter: () => routerMock }));
vi.mock('@/api/backtesterClient', () => ({
  cancelBacktestRun: vi.fn(),
  controlBacktestBatch: vi.fn(),
  deleteBacktestBatch: vi.fn(),
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

function batch(id: string, members: number): BacktestBatch {
  return {
    batch_id: id, submission_id: `${id}-submission`, status: 'completed',
    accepted_at_ms: 1_780_000_000_000, started_at_ms: 1_780_000_001_000,
    completed_at_ms: 1_780_000_002_000, active_member_ordinal: null,
    next_member_ordinal: null, lifecycle_revision: 1, definition_schema_version: 1,
    accepted_definition: { schema_version: 1,
      shared_request: { start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000 },
      normalized_selections: { markets: [{ symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }],
        timeframes: ['M15'], parameters: {}, allowed_directions: ['long_and_short'] } },
    strategy_metadata: { strategy_id: 'sma', strategy_version: 1,
      display_name: 'SMA', parameters: [] },
    raw_count: members, member_count: members, excluded_count: 0,
    total_count: members, settled_count: members, executed_count: members,
    outcome_counts: { queued: 0, running: 0, cancelling: 0, succeeded: members,
      failed: 0, cancelled: 0 },
    has_failed_members: false, markets: ['EURUSD'], exchanges: ['FX'],
    market_contexts: [{ symbol: 'EURUSD', exchange: 'FX' }], timeframes: ['M15'],
    strategy_id: 'sma', strategy_version: 1,
  };
}

function mountWorkspace(includeBatchDetail = false) {
  return mount(BacktestWorkspaceView, {
    global: { plugins: [pinia], stubs: { EquityReplayCharts: true,
      BacktestBatches: !includeBatchDetail } },
  });
}

async function toggleAnalysisColumns(wrapper: ReturnType<typeof mountWorkspace>, keys: string[]) {
  await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
  await flushPromises();
  for (const key of keys) {
    const checkbox = document.querySelector<HTMLElement>(`[data-testid="comparison-column-${key}"]`);
    expect(checkbox, `Column checkbox ${key}`).not.toBeNull();
    checkbox!.click();
    await flushPromises();
  }
  await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
  await flushPromises();
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
    vi.mocked(controlBacktestBatch).mockReset();
    vi.mocked(deleteBacktestRun).mockReset();
    vi.mocked(deleteBacktestBatch).mockReset();
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
    vi.mocked(deleteBacktestBatch).mockResolvedValue();
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

  it('selects all eligible runs and shows partial selection in the header checkbox', async () => {
    const members = [
      run('first', { batch_id: 'selection', member_ordinal: 0 }),
      run('second', { batch_id: 'selection', member_ordinal: 1 }),
      run('failed', { batch_id: 'selection', member_ordinal: 2, status: 'failed', metrics: null }),
    ];
    const accepted = batch('selection', members.length);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue(members);
    vi.mocked(getBacktestRun).mockImplementation(async (id) => members.find((member) => member.run_id === id)!);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.get('[data-testid="workspace-batch-selection"]').trigger('click');
    await flushPromises();
    const header = () => wrapper.findAllComponents(NCheckbox)
      .find((checkbox) => checkbox.attributes('data-testid') === 'comparison-select-all')!;

    header().vm.$emit('update:checked', false);
    await flushPromises();
    expect(header().props('checked')).toBe(false);
    expect(header().props('indeterminate')).toBe(false);
    await wrapper.get('[data-testid="comparison-select-first"]').setValue(true);
    expect(header().props('indeterminate')).toBe(true);

    header().vm.$emit('update:checked', true);
    await flushPromises();
    expect(header().props('checked')).toBe(true);
    expect(header().props('indeterminate')).toBe(false);
    expect(wrapper.get<HTMLInputElement>('[data-testid="comparison-select-second"]').element.checked).toBe(true);
    expect(wrapper.get<HTMLInputElement>('[data-testid="comparison-select-failed"]').element.checked).toBe(false);
    expect(fetchBacktestEquityCurve).not.toHaveBeenCalledWith('failed');

    header().vm.$emit('update:checked', false);
    await flushPromises();
    expect(wrapper.get<HTMLInputElement>('[data-testid="comparison-select-first"]').element.checked).toBe(false);
    expect(wrapper.get<HTMLInputElement>('[data-testid="comparison-select-second"]').element.checked).toBe(false);
    wrapper.unmount();
  });

  it('paginates all fetched members with global sorting, page sizes, and an All option', async () => {
    vi.useFakeTimers();
    const members = Array.from({ length: 105 }, (_, ordinal) =>
      run(`paged-${ordinal}`, { batch_id: 'paged', member_ordinal: ordinal }));
    const accepted = batch('paged', members.length);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue(members);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.get('[data-testid="workspace-batch-paged"]').trigger('click');
    await flushPromises();
    const table = () => wrapper.get('[data-testid="workspace-current-backtest"]');
    const pagination = () => wrapper.findAllComponents(NPagination).at(-1)!;
    const identities = () => table().findAll('.run-identity').map((cell) => cell.find('span').text());
    expect(identities()).toEqual(Array.from({ length: 20 }, (_, index) => `Run #${index + 1}`));
    expect(pagination().props('pageSize')).toBe(20);
    expect(pagination().props('pageSizes')).toEqual([
      { label: '20 rows', value: 20 },
      { label: '50 rows', value: 50 },
      { label: '100 rows', value: 100 },
      { label: 'All rows', value: Number.MAX_SAFE_INTEGER },
    ]);
    const memberReads = vi.mocked(listBacktestBatchMembers).mock.calls.length;
    pagination().vm.$emit('update:page', 3);
    await flushPromises();
    expect(identities()[0]).toBe('Run #41');
    wrapper.findAllComponents(NDataTable).at(-1)!.vm.sort('ordinal', 'descend');
    await flushPromises();
    expect(pagination().props('page')).toBe(1);
    expect(identities()).toEqual(Array.from({ length: 20 }, (_, index) => `Run #${105 - index}`));
    for (const size of [50, 100, Number.MAX_SAFE_INTEGER, 20]) {
      pagination().vm.$emit('update:pageSize', size);
      await flushPromises();
      expect(identities()).toHaveLength(Math.min(size, members.length));
      expect(pagination().props('page')).toBe(1);
      expect(pagination().exists()).toBe(true);
    }
    expect(listBacktestBatchMembers).toHaveBeenCalledTimes(memberReads);
    expect(fetchBacktestEquityCurve).not.toHaveBeenCalled();
    pagination().vm.$emit('update:page', 6);
    await flushPromises();
    expect(identities()).toHaveLength(5);
    wrapper.findComponent({ name: 'BacktestBatches' }).vm.$emit('members', 'paged', members.slice(0, 25));
    await flushPromises();
    expect(pagination().props('page')).toBe(2);
    expect(identities()).toEqual(['Run #5', 'Run #4', 'Run #3', 'Run #2', 'Run #1']);
    wrapper.unmount();
  });

  it('selects and deselects only successful page members while retaining off-page comparisons', async () => {
    const members = Array.from({ length: 25 }, (_, ordinal) =>
      run(`page-selection-${ordinal}`, { batch_id: 'page-selection', member_ordinal: ordinal,
        status: ordinal === 24 ? 'failed' : 'succeeded' }));
    const accepted = batch('page-selection', members.length);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue(members);
    vi.mocked(getBacktestRun).mockImplementation(async (id) => members.find((member) => member.run_id === id)!);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.get('[data-testid="workspace-batch-page-selection"]').trigger('click');
    await flushPromises();
    const header = () => wrapper.findAllComponents(NCheckbox)
      .find((checkbox) => checkbox.attributes('data-testid') === 'comparison-select-all')!;
    const pagination = () => wrapper.findAllComponents(NPagination).at(-1)!;
    header().vm.$emit('update:checked', true);
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(20);
    expect(fetchBacktestEquityCurve).not.toHaveBeenCalledWith('page-selection-20');
    pagination().vm.$emit('update:page', 2);
    await flushPromises();
    expect(header().props('checked')).toBe(false);
    expect(header().props('indeterminate')).toBe(false);
    await wrapper.get('[data-testid="comparison-select-page-selection-20"]').setValue(true);
    await flushPromises();
    expect(header().props('indeterminate')).toBe(true);
    header().vm.$emit('update:checked', true);
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(24);
    expect(fetchBacktestEquityCurve).not.toHaveBeenCalledWith('page-selection-24');
    expect(header().props('checked')).toBe(true);
    header().vm.$emit('update:checked', false);
    await flushPromises();
    expect(header().props('checked')).toBe(false);
    pagination().vm.$emit('update:page', 1);
    await flushPromises();
    expect(header().props('checked')).toBe(true);
    expect(wrapper.get<HTMLInputElement>('[data-testid="comparison-select-page-selection-0"]').element.checked).toBe(true);
    header().vm.$emit('update:checked', false);
    await flushPromises();
    expect(wrapper.findComponent({ name: 'EquityReplayCharts' }).exists()).toBe(false);
    wrapper.unmount();
  });

  it('shows real saved history, selects one run, and retains signed metric semantics', async () => {
    const success = run('success', {
      name: 'Baseline',
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
    await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
    await flushPromises();
    const groups = [...document.querySelectorAll('.column-group')];
    expect(groups.map((group) => group.getAttribute('aria-label')))
      .toEqual(['Run settings', 'Performance', 'Long / short']);
    expect(groups.reduce((count, group) => count + group.querySelectorAll('.column-options [role="checkbox"]').length, 0))
      .toBe(22);
    expect(wrapper.findAll('.comparison-controls button')).toHaveLength(1);
    await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
    await flushPromises();
    await toggleAnalysisColumns(wrapper, ['long-win', 'short-win', 'long-pnl', 'short-pnl']);
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('No trades');
    await toggleAnalysisColumns(wrapper, ['long-win', 'short-win', 'long-pnl', 'short-pnl']);
    expect(current.text()).toContain('10000');
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').findAll('td')
      .map((column) => column.text())).toContain('—');
    expect(wrapper.text()).toContain('Saved request and execution settings');
    wrapper.unmount();
  });

  it('shows mixed selection and enables and disables whole column groups without changing other groups or run selection', async () => {
    const saved = run('groups');
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    vi.mocked(getBacktestRun).mockResolvedValue(saved);
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-groups"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="comparison-select-groups"]').setValue(true);
    await flushPromises();
    await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
    await flushPromises();
    const group = (title: string) => document.querySelector<HTMLElement>(`[aria-label="${title}"]`)!;
    expect(group('Run settings').querySelector('[data-testid="comparison-group-Run settings"]')?.getAttribute('aria-checked')).toBe('mixed');
    expect(group('Performance').querySelector('[data-testid="comparison-group-Performance"]')?.getAttribute('aria-checked')).toBe('true');
    expect(group('Long / short').querySelector('[data-testid="comparison-group-Long / short"]')?.getAttribute('aria-checked')).toBe('false');
    for (const title of ['Run settings', 'Performance', 'Long / short']) {
      const checkbox = group(title).querySelector<HTMLElement>(`[data-testid="comparison-group-${title}"]`)!;
      if (checkbox.getAttribute('aria-checked') !== 'true') {
        checkbox.click();
        await flushPromises();
      }
      expect([...group(title).querySelectorAll<HTMLInputElement>('input')].every((input) => input.checked)).toBe(true);
      expect(checkbox.getAttribute('aria-checked')).toBe('true');
      checkbox.click();
      await flushPromises();
      expect([...group(title).querySelectorAll<HTMLInputElement>('input')].every((input) => !input.checked)).toBe(true);
      expect(checkbox.getAttribute('aria-checked')).toBe('false');
      if (title !== 'Performance') {
        expect(group('Performance').querySelector<HTMLInputElement>('input')!.checked).toBe(true);
      }
      checkbox.click();
      await flushPromises();
    }
    expect(wrapper.get<HTMLInputElement>('[data-testid="comparison-select-groups"]').element.checked).toBe(true);
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('Parameter: fast');
    await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
    wrapper.unmount();
  });

  it('updates column settings during pending replay without rebuilding the table', async () => {
    const saved = run('column-loading');
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    vi.mocked(getBacktestRun).mockResolvedValue(saved);
    vi.mocked(fetchBacktestEquityCurve).mockReturnValue(new Promise(() => {}));
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.get('[data-testid="workspace-run-column-loading"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="comparison-select-column-loading"]').setValue(true);
    await flushPromises();
    const table = wrapper.get('[data-testid="workspace-current-backtest"]').element;
    const detailCalls = vi.mocked(getBacktestRun).mock.calls.length;
    const replayCalls = vi.mocked(fetchBacktestEquityCurve).mock.calls.length;
    await wrapper.get('[data-testid="comparison-columns"]').trigger('click');
    await flushPromises();
    const checkbox = document.querySelector<HTMLInputElement>('[data-testid="comparison-column-long-win"]')!;
    try {
      checkbox.click();
      await nextTick();
      expect(checkbox.checked).toBe(true);
      expect(checkbox.disabled).toBe(false);
      expect(wrapper.get('[data-testid="workspace-current-backtest"]').text()).toContain('Long win rate');
      expect(getBacktestRun).toHaveBeenCalledTimes(detailCalls);
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(replayCalls);
      expect(wrapper.get('[data-testid="workspace-current-backtest"]').element).toBe(table);
      expect(wrapper.find('[data-testid="ending-loading-column-loading"]').exists()).toBe(true);
      checkbox.click();
      checkbox.click();
      await nextTick();
      expect(checkbox.checked).toBe(true);
    } finally {
      wrapper.unmount();
    }
  });

  it.each(['exact', 'unavailable', 'error'] as const)(
    'settles the ending-equity skeleton after %s replay without changing column settings', async (outcome) => {
      const saved = run('skeleton');
      vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
      vi.mocked(getBacktestRun).mockResolvedValue(saved);
      let resolveReplay!: (response: EquityReplayResponse) => void;
      let rejectReplay!: (error: Error) => void;
      vi.mocked(fetchBacktestEquityCurve).mockReturnValue(new Promise((resolve, reject) => {
        resolveReplay = resolve;
        rejectReplay = reject;
      }));
      const wrapper = mountWorkspace();
      try {
        await flushPromises();
        await wrapper.get('[data-testid="workspace-run-skeleton"]').trigger('click');
        await flushPromises();
        expect(wrapper.find('[data-testid="ending-loading-skeleton"]').exists()).toBe(true);
        await toggleAnalysisColumns(wrapper, ['ending']);
        expect(wrapper.find('[data-testid="ending-loading-skeleton"]').exists()).toBe(false);
        if (outcome === 'error') rejectReplay(new Error('Replay offline'));
        else resolveReplay({ availability: outcome, reason: outcome === 'unavailable' ? 'replay_metadata_missing' : null,
          source_point_count: 1, returned_point_count: outcome === 'exact' ? 1 : 0, sampled: false,
          equity_curve: outcome === 'exact' ? [{ timestamp_ms: 1000, equity: 10123, drawdown_pct: 0 }] : [] });
        await flushPromises();
        expect(wrapper.get('[data-testid="workspace-current-backtest"]').text()).not.toContain('Ending equity');
        await toggleAnalysisColumns(wrapper, ['ending']);
        expect(wrapper.find('[data-testid="ending-loading-skeleton"]').exists()).toBe(false);
        const ending = wrapper.get('td[data-col-key="ending"]');
        expect(ending.text()).toBe(outcome === 'exact' ? '10123' : '—');
        if (outcome === 'error') expect(wrapper.text()).toContain('Replay offline');
      } finally {
        wrapper.unmount();
      }
    });

  it('opens the real creation workflow from the primary header action', async () => {
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    const wrapper = mount(BacktestWorkspaceView, {
      global: { plugins: [pinia], stubs: { BacktestCreationDrawer: true,
        BacktestBatches: true, EquityReplayCharts: true } },
    });
    await flushPromises();
    expect(wrapper.getComponent(BacktestCreationDrawer).props('show')).toBe(false);
    await wrapper.get('[data-testid="workspace-create"]').trigger('click');
    expect(wrapper.getComponent(BacktestCreationDrawer).props('show')).toBe(true);
    wrapper.unmount();
  });

  it('opens a separate analysis page and restores history filters on return', async () => {
    const saved = run('navigation');
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    vi.mocked(getBacktestRun).mockResolvedValue(saved);
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.get('[aria-label="Current Backtest"]').attributes('style')).toContain('display: none');
    await wrapper.get('[data-testid="workspace-search"] input').setValue('navigation');
    await wrapper.get('[data-testid="workspace-run-navigation"]').trigger('click');
    await flushPromises();
    expect(routerMock.push).toHaveBeenCalledWith('/backtests/run/navigation');
    expect(wrapper.get('[aria-label="Saved Backtest Runs"]').attributes('style')).toContain('display: none');
    expect(wrapper.get('[aria-label="Current Backtest"]').attributes('style') ?? '').not.toContain('display: none');
    await wrapper.get('[data-testid="workspace-history-return"]').trigger('click');
    expect(wrapper.get('[aria-label="Saved Backtest Runs"]').attributes('style') ?? '').not.toContain('display: none');
    expect(wrapper.get<HTMLInputElement>('[data-testid="workspace-search"] input').element.value).toBe('navigation');
    wrapper.unmount();
  });

  it('opens Create from this without changing the saved run or selection', async () => {
    const saved = run('source');
    const original = structuredClone(saved);
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-source"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-create-from-source"]').trigger('click');
    await flushPromises();
    expect(useBacktestWorkspaceStore().reuseSource).toMatchObject({ kind: 'run', id: 'source',
      strategyVersion: null });
    expect(useBacktestWorkspaceStore().creationDraft?.strategy.strategy_id).toBe('sma');
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('source');
    expect(saved).toEqual(original);
    wrapper.unmount();
  });

  it('opens the accessible execution drawer without changing selection and filters trades while showing all fills', async () => {
    const first = run('first', { name: 'First run' });
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
    expect(document.body.textContent).toContain('01 May 2024, 01:00:00');
    expect(document.body.textContent).toContain('-3');
    expect(document.body.textContent).toContain('1.08');

    const log = wrapper.findComponent(ExecutionLogDrawer);
    log.findAllComponents(NSelect)[0].vm.$emit('update:value', 'short');
    await wrapper.vm.$nextTick();
    expect(document.body.querySelectorAll('[data-testid="execution-trades-table"] tbody tr')).toHaveLength(1);
    expect(document.body.textContent).toContain('stop loss');
    log.findAllComponents(NSelect)[1].vm.$emit('update:value', 'signal');
    await wrapper.vm.$nextTick();
    expect(document.body.textContent).toContain('No Closed Trades match these filters.');

    document.body.querySelector<HTMLButtonElement>('[data-testid="execution-fills-tab"]')!.click();
    await wrapper.vm.$nextTick();
    expect(document.body.querySelectorAll('[data-testid="execution-fills-table"] tbody tr')).toHaveLength(2);
    expect(document.body.textContent).toContain('sell');
    expect(document.body.querySelector('[data-testid="execution-log-drawer"] input[type="search"]')).toBeNull();
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
    document.body.querySelector<HTMLButtonElement>('.n-drawer-header__close')!.click();
    await wrapper.vm.$nextTick();
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
    expect(wrapper.find('[data-testid="workspace-current-backtest"] .run-identity span').text()).toBe('First run');
    wrapper.unmount();
  });

  it('disables unavailable execution logs while distinguishing empty, filtered, and failed reads', async () => {
    const success = run('success');
    const failed = run('failed', { status: 'failed', metrics: null });
    const legacy = run('legacy', { result_schema_version: 2 });
    vi.mocked(listBacktestRuns).mockResolvedValue([success, failed, legacy]);
    const wrapper = mountWorkspace();
    await flushPromises();

    for (const id of ['failed', 'legacy']) {
      const button = wrapper.get(`[data-testid="workspace-log-${id}"]`);
      expect(button.attributes('disabled')).toBeDefined();
      expect(button.attributes('aria-label')).toContain('Execution log unavailable');
      expect(button.find('.unavailable-log-icon').exists()).toBe(true);
      await button.trigger('click');
    }
    expect(wrapper.findComponent(ExecutionLogDrawer).exists()).toBe(false);
    expect(fetchBacktestFills).not.toHaveBeenCalled();

    await wrapper.get('[data-testid="workspace-log-failed"]').element.parentElement?.dispatchEvent(new MouseEvent('mouseenter'));
    await vi.waitFor(() => expect(document.body.textContent).toContain('failed run has no completed execution log'));

    await wrapper.find('[data-testid="workspace-log-success"]').trigger('click');
    await flushPromises();
    expect(document.body.textContent).toContain('This successful run has no executions.');
    expect(fetchBacktestFills).toHaveBeenCalledTimes(1);

    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([trade(0, 'long', 'signal')]);
    vi.mocked(fetchBacktestFills).mockResolvedValue([fill(0, 'buy')]);
    document.body.querySelector<HTMLButtonElement>('.n-drawer-header__close')!.click();
    await wrapper.vm.$nextTick();
    await wrapper.find('[data-testid="workspace-log-success"]').trigger('click');
    await flushPromises();
    wrapper.findComponent(ExecutionLogDrawer).findAllComponents(NSelect)[0].vm.$emit('update:value', 'short');
    await wrapper.vm.$nextTick();
    expect(document.body.textContent).toContain('No Closed Trades match these filters.');

    vi.mocked(fetchBacktestClosedTrades).mockRejectedValue(new Error('Storage unavailable'));
    document.body.querySelector<HTMLButtonElement>('.n-drawer-header__close')!.click();
    await wrapper.vm.$nextTick();
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
    expect(document.body.textContent).toContain('Execution log · Unnamed standalone run');
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
        long_trade_count: 1,
        short_trade_count: 1,
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
    await toggleAnalysisColumns(wrapper, ['long-win', 'short-win', 'long-pnl', 'short-pnl']);
    const pnlCells = wrapper.find('[data-testid="workspace-current-backtest"]')
      .findAll('td').map((cell) => cell.text());
    expect(pnlCells).toContain('-0.003');
    expect(pnlCells).toContain('+0.002');
    await toggleAnalysisColumns(wrapper, ['long-win', 'short-win', 'long-pnl', 'short-pnl']);

    const cells = wrapper.find('[data-testid="workspace-current-backtest"]')
      .findAll('td').map((cell) => cell.text());
    expect(cells).toContain('-0.004%');
    expect(cells).toContain('0.004%');
    wrapper.unmount();
  });

  it('displays saved names and unnamed fallbacks with UUIDs and searches and sorts the visible names', async () => {
    const named = run('alpha-run-full-uuid', { name: 'Alpha research' });
    const unnamed = run('void-run-full-uuid', { request: {
      ...run('x').request, run_metadata: { name: 'Ignored legacy name', label: 'Ignored legacy label' },
    } });
    const namedSweep = { ...batch('beta-batch-full-uuid', 1), name: 'Beta research' };
    const unnamedSweep = batch('empty-batch-full-uuid', 1);
    vi.mocked(listBacktestRuns).mockResolvedValue([named, unnamed]);
    vi.mocked(listBacktestBatches).mockResolvedValue([namedSweep, unnamedSweep]);
    vi.mocked(getBacktestRun).mockImplementation(async (id) => id === named.run_id ? named : unnamed);
    const wrapper = mountWorkspace();
    await flushPromises();
    const history = () => wrapper.get('[data-testid="workspace-history"]');
    for (const [kind, id, label] of [['run', named.run_id, 'Alpha research'],
      ['run', unnamed.run_id, 'Unnamed standalone run'],
      ['batch', namedSweep.batch_id, 'Beta research'],
      ['batch', unnamedSweep.batch_id, 'Unnamed parameter sweep']] as const) {
      await wrapper.get('[data-testid="workspace-search"] input').setValue('');
      const identity = history().get(`[data-testid="workspace-${kind}-${id}"] .run-identity`);
      expect(identity.get('span').text()).toBe(label);
      expect(identity.get('small').text()).toBe(id.slice(0, 8));
      expect(identity.get('span').attributes('title')).toBe(id);
      await wrapper.get('[data-testid="workspace-search"] input').setValue(`  ${label.toUpperCase()}  `);
      expect(history().findAll('tbody tr')).toHaveLength(1);
      expect(history().find(`[data-testid="workspace-${kind}-${id}"]`).exists()).toBe(true);
    }
    await wrapper.get('[data-testid="workspace-search"] input').setValue('Ignored legacy name');
    expect(history().find('[data-testid="workspace-run-void-run-full-uuid"]').exists()).toBe(false);
    for (const query of [named.run_id, namedSweep.batch_id, namedSweep.submission_id]) {
      await wrapper.get('[data-testid="workspace-search"] input').setValue(query);
      expect(history().findAll('tbody tr')).toHaveLength(1);
    }
    await wrapper.get('[data-testid="workspace-search"] input').setValue('');
    wrapper.findAllComponents(NDataTable)[0].vm.sort('name', 'ascend');
    await flushPromises();
    expect(history().findAll('.run-identity span').map((identity) => identity.text()))
      .toEqual(['Alpha research', 'Beta research', 'Unnamed parameter sweep', 'Unnamed standalone run']);
    await history().get(`[data-testid="workspace-run-${named.run_id}"]`).trigger('click');
    await flushPromises();
    expect(wrapper.get('.strategy-name').text()).toBe('Alpha research');
    wrapper.unmount();
  });

  it('filters by search, status, Market, Strategy, and Timeframe', async () => {
    const euro = run('euro', {
      name: 'Euro setup',
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
    expect(wrapper.find('[data-testid="workspace-member-member-0"] .run-identity span').text()).toBe('Run #1');
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

  it('compares ten successful members while retaining selection, failures, and settings', async () => {
    const members = Array.from({ length: 10 }, (_, ordinal) => run(`member-${ordinal}`, {
      batch_id: 'comparison', member_ordinal: ordinal,
      request: { ...run('base').request,
        symbols: ordinal === 1 ? ['GBPUSD'] : ['EURUSD'],
        strategy: { strategy_id: 'sma', strategy_version: 1,
          parameters: { fast: ordinal, note: `value ${ordinal}` } } },
      metrics: { ...run('base').metrics, total_return_pct: ordinal % 2 ? -1.25 : 2.5 },
    }));
    const noTrade = run('no-trade', { batch_id: 'comparison', member_ordinal: 10 });
    const failed = run('failed-member', { batch_id: 'comparison', member_ordinal: 11,
      status: 'failed', metrics: null });
    const cancelled = run('cancelled-member', { batch_id: 'comparison', member_ordinal: 12,
      status: 'cancelled', metrics: null });
    const saved = [...members, noTrade, failed, cancelled];
    const accepted = batch('comparison', saved.length);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue(saved);
    vi.mocked(getBacktestRun).mockImplementation(async (id) => saved.find((item) => item.run_id === id)!);
    vi.mocked(fetchBacktestEquityCurve).mockImplementation(async (id) => {
      if (id === 'member-1') throw new Error('Replay service unavailable');
      if (id === 'member-2') return { availability: 'unavailable',
        reason: 'fingerprint_mismatch', source_point_count: 0, returned_point_count: 0,
        sampled: false, equity_curve: [] };
      return { availability: 'exact', reason: null, source_point_count: 2,
        returned_point_count: 2, sampled: false,
        equity_curve: [
          { timestamp_ms: 1_714_521_600_000, equity: 10000, drawdown_pct: 0 },
          { timestamp_ms: 1_714_608_000_000, equity: id === 'member-0' ? 10200 : 9800,
            drawdown_pct: -2 },
        ] };
    });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.find('[data-testid="workspace-batch-comparison"]').trigger('click');
    await flushPromises();
    const table = () => wrapper.find('[data-testid="workspace-current-backtest"]');
    expect(table().findAll('tbody tr')).toHaveLength(13);
    expect(table().findAll('th').slice(0, 2).map((header) => header.text())).toEqual(['', 'Run']);
    expect(table().findAll('th').at(-1)!.text()).toBe('Actions');
    expect(table().findAll('th').some((header) => header.text() === 'Cancel')).toBe(false);
    expect(table().find('[data-testid^="workspace-cancel-"]').exists()).toBe(false);
    expect(table().get('[data-testid="workspace-member-member-0"] td:nth-child(2) .run-identity span').text()).toBe('Run #1');
    expect(table().get('[data-testid="workspace-member-member-0"] td').find('button').exists()).toBe(false);
    const dataTable = wrapper.findAllComponents(NDataTable).at(-1)!;
    expect(dataTable.props('maxHeight')).toBe(360);
    expect(dataTable.props('scrollX')).toBeGreaterThan(1000);
    expect((dataTable.props('columns') ?? []).slice(0, 2).map((column: { fixed?: string }) =>
      column.fixed)).toEqual(['left', 'left']);
    expect(table().find('[data-testid="workspace-member-failed-member"]').text()).toContain('—');
    expect(table().find('[data-testid="comparison-select-failed-member"]').attributes('disabled'))
      .toBeDefined();
    expect(table().find('[data-testid="comparison-select-cancelled-member"]').attributes('disabled'))
      .toBeDefined();

    for (let index = 0; index < 10; index++) {
      await table().find(`[data-testid="comparison-select-member-${index}"]`).setValue(true);
    }
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledWith('member-0');
    expect(fetchBacktestEquityCurve).toHaveBeenCalledWith('member-9');
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(10);
    expect(wrapper.find('[data-testid="comparison-compatibility"]').text()).toContain('Market');
    expect(wrapper.find('[data-testid="curve-status-member-1"]').text())
      .toContain('Replay service unavailable');
    expect(wrapper.find('[data-testid="curve-status-member-2"]').text())
      .toContain('Candle data changed');
    expect(table().find('[data-testid="workspace-member-member-1"]').text()).toContain('-1.25%');
    expect(table().find('[data-testid="workspace-member-member-1"]').text()).toContain('—');
    expect(table().find('[data-testid="workspace-member-member-0"]').text()).toContain('10200');

    expect(table().findAll('tbody tr')).toHaveLength(saved.length);
    expect(table().find('[data-testid="comparison-select-member-0"]').attributes('checked'))
      .toBeDefined();
    expect(table().find('[data-testid="comparison-select-member-9"]').attributes('checked'))
      .toBeDefined();
    const returnHeader = table().findAll('th').find((header) => header.text().includes('Return (%)'));
    await returnHeader?.trigger('click');
    const rowOrder = () => table().findAll('tbody tr').map((row) => row.attributes('data-testid'));
    const sortedOrder = rowOrder();
    expect(sortedOrder).not.toEqual(saved.map((run) => `workspace-member-${run.run_id}`));
    await toggleAnalysisColumns(wrapper, ['parameter:fast', 'parameter:note']);
    expect(table().text()).toContain('Parameter: fast');
    expect(table().text()).toContain('Parameter: note');
    expect(rowOrder()).toEqual(sortedOrder);
    expect(table().find('[data-testid="comparison-select-member-9"]').attributes('checked'))
      .toBeDefined();
    await toggleAnalysisColumns(wrapper, ['long-win', 'short-win', 'long-pnl', 'short-pnl']);
    expect(table().find('[data-testid="workspace-member-no-trade"]').text()).toContain('No trades');
    expect(table().find('[data-testid="workspace-member-no-trade"]').text()).toContain('0');
    expect(rowOrder()).toEqual(sortedOrder);
    await toggleAnalysisColumns(wrapper, ['long-win', 'short-win', 'long-pnl', 'short-pnl']);
    await table().find('[data-testid="workspace-log-member-0"]').trigger('click');
    await flushPromises();
    expect(table().find('[data-testid="comparison-select-member-0"]').attributes('checked'))
      .toBeDefined();
    wrapper.unmount();
  }, 30000);

  it('keeps settled replay series loaded across unchanged batch polling', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const members = [0, 1].map((ordinal) => run(`member-${ordinal}`,
      { batch_id: 'stable', member_ordinal: ordinal }));
    const accepted = batch('stable', 2);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue(members);
    vi.mocked(getBacktestRun).mockImplementation(async (id) => members.find((run) => run.run_id === id)!);
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({ availability: 'exact',
      reason: null, source_point_count: 1, returned_point_count: 1, sampled: false,
      equity_curve: [{ timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 }] });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.find('[data-testid="workspace-batch-stable"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="comparison-select-member-0"]').setValue(true);
    await wrapper.find('[data-testid="comparison-select-member-1"]').setValue(true);
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(2);
    expect(wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'))
      .toEqual(expect.arrayContaining([expect.objectContaining({ runId: 'member-0',
        points: [{ timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 }] })]));
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(listBacktestBatchMembers).toHaveBeenCalledTimes(2);
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(2);
    expect(wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'))
      .toEqual(expect.arrayContaining([expect.objectContaining({ runId: 'member-0',
        points: [{ timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 }] })]));
    expect(wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'))
      .toEqual(expect.arrayContaining([expect.objectContaining({ runId: 'member-1',
        points: [{ timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 }] })]));
    wrapper.unmount();
  });

  it('keeps selected content steady while background detail reads are pending', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const saved = run('steady');
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    vi.mocked(getBacktestRun).mockResolvedValue(saved);
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-steady"]').trigger('click');
    await flushPromises();
    const selectedTable = wrapper.get('[data-testid="workspace-current-backtest"]').text();
    vi.mocked(getBacktestRun).mockImplementation(() => new Promise(() => {}));
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.get('[data-testid="workspace-current-backtest"]').text()).toBe(selectedTable);
    const reads = vi.mocked(getBacktestRun).mock.calls.length;
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(getBacktestRun).toHaveBeenCalledTimes(reads);
    wrapper.unmount();
  });

  it('keeps completed curves visible while another batch member settles', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const success = run('settled', { batch_id: 'active', member_ordinal: 0 });
    const pending = run('pending', { batch_id: 'active', member_ordinal: 1,
      status: 'running', metrics: null });
    const accepted = batch('active', 2);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([success, pending]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({ availability: 'exact', reason: null,
      source_point_count: 1, returned_point_count: 1, sampled: false,
      equity_curve: [{ timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 }] });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.find('[data-testid="workspace-batch-active"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="comparison-select-settled"]').setValue(true);
    await flushPromises();
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([success, { ...pending, status: 'failed' }]);
    vi.mocked(fetchBacktestEquityCurve).mockImplementation(() => new Promise(() => {}));
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'))
      .toEqual(expect.arrayContaining([expect.objectContaining({ runId: 'settled',
        points: [{ timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 }] })]));
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it('preserves member logs and standalone log filters across history polls', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const saved = run('standalone');
    const member = run('member', { batch_id: 'logs', member_ordinal: 0 });
    const accepted = batch('logs', 1);
    vi.mocked(listBacktestRuns).mockImplementation(async () => [structuredClone(saved)]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([member]);
    vi.mocked(getBacktestRun).mockResolvedValue(member);
    vi.mocked(fetchBacktestFills).mockResolvedValue([fill(0, 'sell')]);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.find('[data-testid="workspace-log-standalone"]').trigger('click');
    await flushPromises();
    document.body.querySelector<HTMLButtonElement>('[data-testid="execution-fills-tab"]')!.click();
    await wrapper.vm.$nextTick();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(document.body.querySelector('[data-testid="execution-fills-table"]')).not.toBeNull();
    expect(fetchBacktestFills).toHaveBeenCalledTimes(1);
    document.body.querySelector<HTMLButtonElement>('.n-drawer-header__close')!.click();
    await wrapper.vm.$nextTick();
    await wrapper.find('[data-testid="workspace-batch-logs"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-log-member"]').trigger('click');
    await flushPromises();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(document.body.textContent).toContain('Execution log · Run #1');
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
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const success = run('success');
    vi.mocked(listBacktestRuns).mockResolvedValueOnce([success]).mockRejectedValueOnce(
      new Error('Service unavailable'),
    ).mockResolvedValueOnce([]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    vi.stubGlobal('confirm', vi.fn(() => true));

    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-refresh"]').exists()).toBe(false);
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.get('[data-testid="workspace-refresh"]').text()).toBe('Retry now');
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain('current lifecycle status is unknown');
    expect(wrapper.find('[data-testid="workspace-run-success"]').exists()).toBe(true);

    await wrapper.find('[data-testid="workspace-delete-success"]').trigger('click');
    await flushPromises();
    expect(deleteBacktestRun).toHaveBeenCalledWith('success');
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(3);
    expect(wrapper.text()).toContain('No saved Backtest Runs or Batches.');
    expect(wrapper.text()).not.toContain('current lifecycle status is unknown');
    expect(wrapper.find('[data-testid="workspace-refresh"]').exists()).toBe(false);
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
    expect(wrapper.find('[data-testid="workspace-cancel-queued"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it('cancels one queued Batch member from the combined table and refreshes that member', async () => {
    const accepted = { ...batch('cancellable', 2), status: 'queued' as const };
    const queued = [0, 1].map((ordinal) => run(`member-${ordinal}`, {
      batch_id: 'cancellable', member_ordinal: ordinal,
      status: 'queued', started_at_ms: null, completed_at_ms: null,
      result_schema_version: null, metrics: null,
    }));
    const cancelled = { ...queued[0], status: 'cancelled' as const,
      completed_at_ms: 1_780_922_100_000,
      cancel_requested_at_ms: 1_780_922_100_000,
      cancellation_source: 'user' as const, cancellation_reason: 'user_requested' as const };
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValueOnce(queued)
      .mockResolvedValue([cancelled, queued[1]]);
    vi.mocked(cancelBacktestRun).mockResolvedValue(cancelled);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.find('[data-testid="workspace-batch-cancellable"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-cancel-member-0"]').trigger('click');
    await flushPromises();
    expect(cancelBacktestRun).toHaveBeenCalledOnce();
    expect(cancelBacktestRun).toHaveBeenCalledWith('member-0');
    expect(wrapper.find('[data-testid="workspace-cancel-member-0"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="workspace-cancel-member-1"]').attributes('disabled'))
      .toBeUndefined();
    expect(wrapper.find('[data-testid="workspace-batch-members"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it('refreshes combined history and queue health after cancelling an entire Batch', async () => {
    const queued = { ...batch('whole-batch', 2), status: 'queued' as const,
      completed_at_ms: null, settled_count: 0, executed_count: 0,
      outcome_counts: { queued: 2, running: 0, cancelling: 0, succeeded: 0,
        failed: 0, cancelled: 0 } };
    const cancelled = { ...queued, status: 'cancelled' as const,
      completed_at_ms: 1_780_922_100_000, settled_count: 2,
      cancel_requested_at_ms: 1_780_922_100_000,
      outcome_counts: { queued: 0, running: 0, cancelling: 0, succeeded: 0,
        failed: 0, cancelled: 2 } };
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValueOnce([queued]).mockResolvedValue([cancelled]);
    vi.mocked(getBacktestBatch).mockResolvedValueOnce(queued).mockResolvedValue(cancelled);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([]);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(controlBacktestBatch).mockResolvedValue({ batch_id: 'whole-batch',
      command_id: 'cancel-command', status: 'cancelled', lifecycle_revision: 2 });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.find('[data-testid="workspace-batch-whole-batch"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-cancel-batch"]').trigger('click');
    await flushPromises();
    expect(controlBacktestBatch).toHaveBeenCalledWith('whole-batch', 'cancel', expect.any(String));
    expect(listBacktestBatches).toHaveBeenCalledTimes(2);
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(wrapper.find('[data-testid="workspace-batch-whole-batch"]').text()).toContain('cancelled');
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

  it('keeps a Batch visible after delete conflict, then refreshes and clears its selection', async () => {
    const accepted = batch('delete-me', 1);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValueOnce([accepted]).mockResolvedValueOnce([]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([run('member-1', {
      batch_id: 'delete-me', member_ordinal: 0,
    })]);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(deleteBacktestBatch).mockRejectedValueOnce(new Error('Conflict'));
    vi.stubGlobal('confirm', vi.fn(() => true));
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-batch-delete-me"]').trigger('click');
    await flushPromises();
    const overlay = useBacktestOverlayStore();
    overlay.selectedRunId = 'member-1';
    overlay.selectedRun = run('member-1', { batch_id: 'delete-me', member_ordinal: 0 });

    await wrapper.find('[data-testid="workspace-delete-batch-delete-me"]').trigger('click');
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-batch-delete-me"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Conflict');
    expect(listBacktestBatches).toHaveBeenCalledTimes(1);

    await wrapper.find('[data-testid="workspace-delete-batch-delete-me"]').trigger('click');
    await flushPromises();
    expect(deleteBacktestBatch).toHaveBeenCalledTimes(2);
    expect(wrapper.find('[data-testid="workspace-batch-delete-me"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('removed from the chart overlay');
    expect(overlay.selectedRunId).toBeNull();
    expect(wrapper.text()).not.toContain('Conflict');
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

  it('coalesces a retry requested during an active recovery poll', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    let resolveRead!: (runs: BacktestRun[]) => void;
    vi.mocked(listBacktestRuns)
      .mockRejectedValueOnce(new Error('Service unavailable'))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveRead = resolve; }))
      .mockResolvedValueOnce([run('active', { status: 'succeeded' })]);
    const wrapper = mountWorkspace();
    await flushPromises();

    expect(wrapper.get('[data-testid="workspace-refresh"]').text()).toBe('Retry now');
    vi.advanceTimersByTime(5000);
    await flushPromises();
    await wrapper.find('[data-testid="workspace-refresh"]').trigger('click');
    expect(listBacktestRuns).toHaveBeenCalledTimes(2);
    resolveRead([run('active', { status: 'running', metrics: null })]);
    await flushPromises();

    expect(listBacktestRuns).toHaveBeenCalledTimes(3);
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
    expect(wrapper.find('[data-testid="workspace-current-backtest"] [role="img"][aria-label="Failed"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it('ignores a late curve after switching the open Backtest', async () => {
    const first = run('first');
    const second = run('second');
    vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
    vi.mocked(getBacktestRun).mockImplementation(async (id) => id === 'first' ? first : second);
    let resolveFirst!: (value: Awaited<ReturnType<typeof fetchBacktestEquityCurve>>) => void;
    vi.mocked(fetchBacktestEquityCurve).mockImplementation((id) => id === 'first'
      ? new Promise((resolve) => { resolveFirst = resolve; })
      : Promise.resolve({ availability: 'exact', reason: null,
        source_point_count: 1, returned_point_count: 1, sampled: false,
        equity_curve: [{ timestamp_ms: 1_714_521_600_000, equity: 11000, drawdown_pct: 0 }] }));
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-first"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-second"]').trigger('click');
    await flushPromises();
    resolveFirst({ availability: 'exact', reason: null,
      source_point_count: 1, returned_point_count: 1, sampled: false,
      equity_curve: [{ timestamp_ms: 1_714_521_600_000, equity: 9000, drawdown_pct: -1 }] });
    await flushPromises();
    expect(wrapper.find('[data-testid="curve-status-second"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="curve-status-first"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('11000');
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
    expect(wrapper.find('[data-testid="workspace-current-backtest"]').text()).toContain('9875');
    expect(wrapper.find('[data-testid="curve-status-success"]').exists()).toBe(false);
    expect(wrapper.findComponent({ name: 'EquityReplayCharts' }).props('sampled')).toBe(true);
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
    expect(wrapper.find('[data-testid="workspace-open-chart"]').exists()).toBe(false);
    await wrapper.find('[data-testid="workspace-chart-success"]').trigger('click');
    await flushPromises();

    expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('success');
    expect(routerMock.push).toHaveBeenCalledWith('/');
    wrapper.unmount();
  });


  it('opens a batch row directly on the chart while preserving selection and comparison', async () => {
    const members = [
      run('z-first', { batch_id: 'direct', member_ordinal: 0 }),
      run('a-tenth', { batch_id: 'direct', member_ordinal: 9 }),
      run('m-second', { batch_id: 'direct', member_ordinal: 1 }),
    ];
    const accepted = batch('direct', members.length);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue(members);
    vi.mocked(getBacktestRun).mockImplementation(async (id) => members.find((member) => member.run_id === id)!);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper.get('[data-testid="workspace-batch-direct"]').trigger('click');
    await flushPromises();
    const table = wrapper.get('[data-testid="workspace-current-backtest"]');
    const identities = () => table.findAll('.run-identity').map((cell) => cell.find('span').text());
    expect(identities()).toEqual(['Run #1', 'Run #2', 'Run #10']);
    const dataTable = wrapper.findAllComponents(NDataTable).at(-1)!;
    dataTable.vm.sort('ordinal', 'descend');
    await flushPromises();
    expect(identities()).toEqual(['Run #10', 'Run #2', 'Run #1']);
    dataTable.vm.sort('ordinal', 'ascend');
    await flushPromises();
    expect(identities()).toEqual(['Run #1', 'Run #2', 'Run #10']);
    await wrapper.get('[data-testid="workspace-member-z-first"]').trigger('click');
    await flushPromises();
    const chart = wrapper.get('[data-testid="workspace-chart-a-tenth"]');
    expect(chart.attributes('aria-label')).toBe('Open Run #10 on chart');
    await chart.trigger('keydown', { key: 'Enter' });
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('z-first');
    await chart.trigger('click');
    await flushPromises();
    expect(useBacktestOverlayStore().selectedRunId).toBe('a-tenth');
    expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('a-tenth');
    expect(routerMock.push).toHaveBeenCalledWith('/');
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('z-first');
    expect(wrapper.get<HTMLInputElement>('[data-testid="comparison-select-z-first"]').element.checked).toBe(true);
    expect(wrapper.get<HTMLInputElement>('[data-testid="comparison-select-a-tenth"]').element.checked).toBe(false);
    wrapper.unmount();
  });

  it.each([
    ['unfinished', { status: 'running', metrics: null }],
    ['no-symbol', { request: { ...run('base').request, symbols: [] } }],
    ['multi-symbol', { request: { ...run('base').request, symbols: ['EURUSD', 'GBPUSD'] } }],
    ['missing-market', { request: { ...run('base').request, symbols: ['GBPUSD'] } }],
  ] as [string, Partial<BacktestRun>][])('disables the chart action for %s runs', async (id, overrides) => {
    const saved = run(id, overrides);
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    vi.mocked(getBacktestRun).mockResolvedValue(saved);
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.get(`[data-testid="workspace-run-${id}"]`).trigger('click');
    await flushPromises();
    expect(wrapper.get(`[data-testid="workspace-chart-${id}"]`).attributes('disabled')).toBeDefined();
    if (saved.status === 'succeeded') {
      expect(wrapper.get(`[data-testid="workspace-log-${id}"]`).attributes('disabled')).toBeUndefined();
    } else {
      expect(wrapper.get(`[data-testid="workspace-log-${id}"]`).attributes('disabled')).toBeDefined();
    }
    expect(routerMock.push).not.toHaveBeenCalledWith('/');
    wrapper.unmount();
  });

  it('prevents repeated chart opens during loading and allows retry after a failed read', async () => {
    const saved = run('retry');
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    vi.mocked(getBacktestRun).mockResolvedValue(saved);
    let rejectRead!: (reason: Error) => void;
    vi.mocked(fetchBacktestClosedTrades).mockImplementationOnce(() =>
      new Promise((_, reject) => { rejectRead = reject; }));
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.get('[data-testid="workspace-run-retry"]').trigger('click');
    await flushPromises();
    const chart = wrapper.get('[data-testid="workspace-chart-retry"]');
    await chart.trigger('click');
    expect(chart.attributes('disabled')).toBeDefined();
    await chart.trigger('click');
    expect(fetchBacktestClosedTrades).toHaveBeenCalledTimes(1);
    rejectRead(new Error('Trades unavailable'));
    await flushPromises();
    expect(wrapper.text()).toContain('Trades unavailable');
    expect(routerMock.push).not.toHaveBeenCalledWith('/');
    expect(chart.attributes('disabled')).toBeUndefined();
    await chart.trigger('click');
    await flushPromises();
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
    expect(wrapper.find('[data-testid="workspace-chart-legacy"]').attributes('disabled')).toBeDefined();
    await wrapper.find('[data-testid="workspace-chart-legacy"]').element.parentElement?.dispatchEvent(new MouseEvent('mouseenter'));
    await vi.waitFor(() => expect(document.body.textContent).toContain('Backtest Run result schema is unsupported.'));
    expect(routerMock.push).not.toHaveBeenCalledWith('/');
    wrapper.unmount();
  });
});
