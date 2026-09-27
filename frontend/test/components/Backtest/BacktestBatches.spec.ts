import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getBacktestBatch, listBacktestBatchEvents, listBacktestBatchMembers,
} from '@/api/backtesterClient';
import { isBacktestBatch, type BacktestBatch, type BacktestRun } from '@/types/backtesterContracts';
import BacktestBatches from '@/components/Backtest/BacktestBatches.vue';

vi.mock('@/api/backtesterClient', () => ({
  getBacktestBatch: vi.fn(), listBacktestBatchEvents: vi.fn(),
  listBacktestBatchMembers: vi.fn(),
}));

const batch: BacktestBatch = {
  batch_id: 'batch-1', submission_id: 'submit-1', status: 'queued',
  accepted_at_ms: 1_780_000_000_000, lifecycle_revision: 0,
  started_at_ms: null, completed_at_ms: null, active_member_ordinal: null,
  next_member_ordinal: 0,
  definition_schema_version: 1,
  accepted_definition: { schema_version: 1, shared_request: { start_ms: 1_714_521_600_000 },
    normalized_selections: { markets: [{ symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }],
      timeframes: ['M1'], parameters: { fast_window: { mode: 'range', values: [5, 6],
        range: { start: 5, stop: 6, step: 1 } } }, allowed_directions: ['long_and_short'] } },
  strategy_metadata: { strategy_id: 'sma_crossover', strategy_version: 1,
    display_name: 'SMA crossover', parameters: [] },
  raw_count: 3, member_count: 2, excluded_count: 1,
  total_count: 2, settled_count: 0, executed_count: 0,
  outcome_counts: { queued: 2, running: 0, cancelling: 0, succeeded: 0,
    failed: 0, cancelled: 0 },
  has_failed_members: false, markets: ['EURUSD'], exchanges: ['FX'],
  market_contexts: [{ symbol: 'EURUSD', exchange: 'FX' }], timeframes: ['M1'],
  strategy_id: 'sma_crossover', strategy_version: 1,
};

function member(ordinal: number): BacktestRun {
  return {
    run_id: `member-${ordinal}`, batch_id: 'batch-1', member_ordinal: ordinal,
    status: 'queued', submitted_at_ms: batch.accepted_at_ms, request_schema_version: 3,
    request: { symbols: ['EURUSD'], exchange: 'FX', timeframe: 'M1',
      start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000, engine: 'vectorized',
      data_granularity: 'bar', initial_capital: 10_000,
      strategy: { strategy_id: 'sma_crossover', strategy_version: 1,
        parameters: { fast_window: 5 + ordinal } },
      execution: { signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
        allow_partial_fills: false, allowed_directions: 'long_and_short',
        trade_accounting_policy: 'average_cost', gap_policy: 'skip',
        intrabar_exit_policy: 'conservative', commission_bps: 0, slippage_bps: 0 },
      persist_result: false },
  };
}

describe('accepted batch inspection', () => {
  it('validates actual-member context and aggregate failure projection', () => {
    expect(isBacktestBatch(batch)).toBe(true);
    expect(isBacktestBatch({ ...batch, has_failed_members: true })).toBe(false);
    expect(isBacktestBatch({ ...batch, market_contexts: [] })).toBe(false);
  });

  beforeEach(() => {
    vi.mocked(getBacktestBatch).mockReset().mockResolvedValue(batch);
    vi.mocked(listBacktestBatchMembers).mockReset().mockResolvedValue([member(0), member(1)]);
    vi.mocked(listBacktestBatchEvents).mockReset().mockResolvedValue([{ batch_id: 'batch-1',
      revision: 0, event_type: 'accepted', status: 'queued',
      prior_status: null, occurred_at_ms: batch.accepted_at_ms, trigger_run_id: null, reason: null }]);
  });

  it('shows one batch summary, saved definition, and actual ordered Ready members after reload', async () => {
    const reloaded = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(reloaded.text()).toContain('2 fixed members');
    expect(reloaded.text()).toContain('0 / 2 settled');
    expect(reloaded.text()).toContain('0 executed');
    expect(reloaded.find('[data-testid="workspace-batch-members"]').text()).toContain('member-1');
    expect(reloaded.findAll('[data-testid^="workspace-member-"]')).toHaveLength(2);
    expect(reloaded.text()).toContain('Accepted sweep settings and Strategy Metadata Snapshot');
    expect(reloaded.text()).not.toContain('0%');
    reloaded.unmount();
  });

  it('preserves successful results and shows partial failure, ordinals, and transitions after refresh', async () => {
    vi.mocked(getBacktestBatch).mockResolvedValueOnce({ ...batch, status: 'running',
      lifecycle_revision: 2, started_at_ms: batch.accepted_at_ms + 1000,
      active_member_ordinal: 1, next_member_ordinal: null,
      settled_count: 1, executed_count: 1,
      outcome_counts: { queued: 0, running: 1, cancelling: 0, succeeded: 0,
        failed: 1, cancelled: 0 }, has_failed_members: true })
      .mockResolvedValue({ ...batch, status: 'completed', lifecycle_revision: 3,
        started_at_ms: batch.accepted_at_ms + 1000,
        completed_at_ms: batch.accepted_at_ms + 3000,
        active_member_ordinal: null, next_member_ordinal: null,
        settled_count: 2, executed_count: 2,
        outcome_counts: { queued: 0, running: 0, cancelling: 0, succeeded: 1,
          failed: 1, cancelled: 0 }, has_failed_members: true });
    vi.mocked(listBacktestBatchMembers).mockResolvedValueOnce([
      { ...member(0), status: 'failed', error_message: 'Data unavailable' },
      { ...member(1), status: 'running' },
    ]).mockResolvedValue([
      { ...member(0), status: 'failed', error_message: 'Data unavailable' },
      { ...member(1), status: 'succeeded' },
    ]);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([
      { batch_id: 'batch-1', revision: 0, event_type: 'accepted', status: 'queued',
        prior_status: null, occurred_at_ms: batch.accepted_at_ms, trigger_run_id: null, reason: null },
      { batch_id: 'batch-1', revision: 1, event_type: 'started', status: 'running',
        prior_status: 'queued', occurred_at_ms: batch.accepted_at_ms + 1000,
        trigger_run_id: 'member-0', reason: null },
      { batch_id: 'batch-1', revision: 3, event_type: 'completed', status: 'completed',
        prior_status: 'running', occurred_at_ms: batch.accepted_at_ms + 3000,
        trigger_run_id: 'member-1', reason: null },
    ]);
    vi.useFakeTimers();
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(wrapper.text()).toContain('1 member failure');
    expect(wrapper.text()).toContain('Active member #2');
    expect(wrapper.find('[data-testid="workspace-batch-members"]').text())
      .toContain('Data unavailable');
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.text()).toContain('2 / 2 settled');
    expect(wrapper.text()).toContain('succeeded: 1');
    expect(wrapper.text()).toContain('running → completed');
    expect(wrapper.text()).toContain('Terminal:');
    expect(wrapper.text()).toContain('run member-1');
    wrapper.unmount();
    vi.useRealTimers();
  });
});
