import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getBacktestBatch, listBacktestBatchEvents, listBacktestBatchMembers, controlBacktestBatch,
} from '@/api/backtesterClient';
import { isBacktestBatch, type BacktestBatch, type BacktestRun } from '@/types/backtesterContracts';
import BacktestBatches from '@/components/Backtest/BacktestBatches.vue';

vi.mock('@/api/backtesterClient', () => ({
  controlBacktestBatch: vi.fn(),
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
    vi.mocked(controlBacktestBatch).mockReset();
    vi.mocked(getBacktestBatch).mockReset().mockResolvedValue(batch);
    vi.mocked(listBacktestBatchMembers).mockReset().mockResolvedValue([member(0), member(1)]);
    vi.mocked(listBacktestBatchEvents).mockReset().mockResolvedValue([{ batch_id: 'batch-1',
      revision: 0, event_type: 'accepted', status: 'queued',
      prior_status: null, occurred_at_ms: batch.accepted_at_ms, trigger_run_id: null, reason: null }]);
  });

  it('emits actual members to the workspace comparison table', async () => {
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(wrapper.emitted('members')?.[0]).toEqual(['batch-1', [member(0), member(1)]]);
    expect(wrapper.find('[data-testid="workspace-batch-members"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it('does not discard a batch read that takes longer than a poll interval', async () => {
    vi.useFakeTimers();
    let resolve!: (batch: BacktestBatch) => void;
    vi.mocked(getBacktestBatch).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    vi.advanceTimersByTime(10_000);
    await flushPromises();
    expect(getBacktestBatch).toHaveBeenCalledTimes(1);
    resolve(batch);
    await flushPromises();
    expect(wrapper.emitted('members')).toHaveLength(1);
    wrapper.unmount();
    vi.useRealTimers();
  });

  it('offers legal pause and resume controls and refreshes after command acceptance', async () => {
    vi.mocked(controlBacktestBatch).mockResolvedValueOnce({ batch_id: 'batch-1',
      status: 'paused', lifecycle_revision: 1 });
    vi.mocked(getBacktestBatch).mockResolvedValueOnce(batch)
      .mockResolvedValue({ ...batch, status: 'paused', lifecycle_revision: 1 });
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    await wrapper.get('button').trigger('click');
    await flushPromises();
    expect(controlBacktestBatch).toHaveBeenCalledWith('batch-1', 'pause', expect.any(String));
    expect(wrapper.text()).toContain('Batch paused.');
    expect(wrapper.get('button').text()).toBe('Resume Batch');
    expect(wrapper.get('p[role="status"]').text()).not.toContain('%');
    wrapper.unmount();
  });

  it('cancels an executing batch and keeps its active member visibly unsettled', async () => {
    const running = { ...batch, status: 'running' as const, active_member_ordinal: 0,
      outcome_counts: { ...batch.outcome_counts, queued: 1, running: 1 } };
    const cancelling = { ...running, status: 'cancelling' as const,
      cancel_requested_at_ms: batch.accepted_at_ms + 1, cancellation_source: 'user',
      cancellation_reason: 'user_requested', lifecycle_revision: 2,
      next_member_ordinal: null,
      outcome_counts: { ...batch.outcome_counts, queued: 0, running: 0, cancelling: 1, cancelled: 1 },
      settled_count: 1 };
    vi.mocked(getBacktestBatch).mockResolvedValueOnce(running).mockResolvedValue(cancelling);
    vi.mocked(listBacktestBatchMembers).mockResolvedValueOnce([
      { ...member(0), status: 'running' }, member(1),
    ]).mockResolvedValue([
      { ...member(0), status: 'cancelling', cancel_requested_at_ms: batch.accepted_at_ms + 1,
        cancellation_source: 'batch', cancellation_reason: 'batch_cancel_requested' },
      { ...member(1), status: 'cancelled', cancel_requested_at_ms: batch.accepted_at_ms + 1,
        completed_at_ms: batch.accepted_at_ms + 1,
        cancellation_source: 'batch', cancellation_reason: 'batch_cancel_requested' },
    ]);
    vi.mocked(controlBacktestBatch).mockImplementation(async (_id, _command, commandId) => ({
      batch_id: 'batch-1', command_id: commandId, status: 'cancelling', lifecycle_revision: 2,
    }));
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    await wrapper.get('[data-testid="workspace-cancel-batch"]').trigger('click');
    await flushPromises();
    expect(controlBacktestBatch).toHaveBeenCalledWith('batch-1', 'cancel', expect.any(String));
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuetext')).toContain('1 / 2 settled');
    expect(wrapper.text()).toContain('0 executed');
    expect(wrapper.text()).toContain('Cancellation will finish after cleanup');
    expect(wrapper.text()).toContain('Cancellation accepted:');
    expect(wrapper.find('[data-testid="workspace-cancel-batch"]').exists()).toBe(false);
    expect(wrapper.emitted('cancelled')).toHaveLength(1);
    wrapper.unmount();
  });

  it('shows draining state and retries a failed command with the same identity', async () => {
    const draining = { ...batch, status: 'pausing' as const, lifecycle_revision: 2,
      active_member_ordinal: 0 };
    vi.mocked(getBacktestBatch).mockResolvedValue(draining);
    vi.mocked(controlBacktestBatch).mockRejectedValueOnce(new Error('Connection lost'))
      .mockResolvedValueOnce({ batch_id: 'batch-1', status: 'running', lifecycle_revision: 3 });
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(wrapper.text()).toContain('Pausing after the active run finishes.');
    expect(wrapper.get('button').text()).toBe('Resume Batch');
    expect(wrapper.get('p[role="status"]').text()).not.toContain('%');
    await wrapper.get('button').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Connection lost');
    await wrapper.get('button').trigger('click');
    await flushPromises();
    const calls = vi.mocked(controlBacktestBatch).mock.calls;
    expect(calls[0][2]).toBe(calls[1][2]);
    wrapper.unmount();
  });

  it('retains a pending Pause identity when member cancellation advances the batch revision', async () => {
    vi.mocked(getBacktestBatch).mockResolvedValueOnce(batch)
      .mockResolvedValue({ ...batch, status: 'queued', lifecycle_revision: 1 });
    vi.mocked(listBacktestBatchEvents).mockResolvedValueOnce([{ batch_id: 'batch-1',
      revision: 0, event_type: 'accepted', status: 'queued', prior_status: null,
      occurred_at_ms: batch.accepted_at_ms, trigger_run_id: null, reason: null }])
      .mockResolvedValue([{ batch_id: 'batch-1', revision: 1,
        event_type: 'member_cancelled', status: 'queued', prior_status: 'queued',
        occurred_at_ms: batch.accepted_at_ms + 1, trigger_run_id: 'member-0',
        reason: 'user_requested', command_id: null }]);
    vi.mocked(controlBacktestBatch).mockRejectedValue(new Error('Connection lost'));
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    await wrapper.get('button').trigger('click');
    await flushPromises();
    await wrapper.get('button').trigger('click');
    await flushPromises();
    const calls = vi.mocked(controlBacktestBatch).mock.calls;
    expect(calls).toHaveLength(2);
    expect(calls[0][2]).toBe(calls[1][2]);
    wrapper.unmount();
  });

  it('uses a new Pause identity after a lost response, observed pause, and Resume', async () => {
    vi.mocked(getBacktestBatch).mockResolvedValueOnce(batch)
      .mockResolvedValueOnce({ ...batch, status: 'paused', lifecycle_revision: 1 })
      .mockResolvedValueOnce({ ...batch, status: 'running', lifecycle_revision: 2 })
      .mockResolvedValue({ ...batch, status: 'paused', lifecycle_revision: 3 });
    vi.mocked(controlBacktestBatch)
      .mockRejectedValueOnce(new Error('Pause response lost'))
      .mockResolvedValueOnce({ batch_id: 'batch-1', status: 'running', lifecycle_revision: 2 })
      .mockResolvedValueOnce({ batch_id: 'batch-1', status: 'paused', lifecycle_revision: 3 });

    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    await wrapper.get('button').trigger('click');
    await flushPromises();
    expect(wrapper.get('button').text()).toBe('Resume Batch');
    expect(wrapper.text()).toContain('revision 1');

    await wrapper.get('button').trigger('click');
    await flushPromises();
    expect(wrapper.get('button').text()).toBe('Pause Batch');
    expect(wrapper.text()).toContain('revision 2');

    await wrapper.get('button').trigger('click');
    await flushPromises();
    const calls = vi.mocked(controlBacktestBatch).mock.calls;
    expect(calls.map(([,, identity]) => identity)).toHaveLength(3);
    expect(calls.map(([, command]) => command)).toEqual(['pause', 'resume', 'pause']);
    expect(calls[2][2]).not.toBe(calls[0][2]);
    expect(wrapper.text()).toContain('revision 3');
    expect(wrapper.text()).toContain('Batch paused.');
    wrapper.unmount();
  });

  it('shows one batch summary, saved definition, and actual ordered Ready members after reload', async () => {
    const reloaded = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(reloaded.text()).toContain('2 of 3 combinations');
    expect(reloaded.get('[role="progressbar"]').attributes('aria-valuetext')).toContain('0 / 2 settled');
    expect(reloaded.text()).toContain('0 executed');
    expect(reloaded.emitted('members')?.[0]).toEqual(['batch-1', [member(0), member(1)]]);
    expect(reloaded.find('[data-testid="workspace-batch-members"]').exists()).toBe(false);
    expect(reloaded.text()).toContain('Full saved definition and strategy metadata');
    expect(reloaded.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('0');
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
    expect(wrapper.text()).toContain('1 run failed');
    expect(wrapper.text()).toContain('Running #2 of 2');
    expect(wrapper.emitted('members')?.[0]?.[1]).toEqual([
      { ...member(0), status: 'failed', error_message: 'Data unavailable' },
      { ...member(1), status: 'running' },
    ]);
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuetext')).toContain('2 / 2 settled');
    expect(wrapper.get('.outcome-grid .succeeded dd').text()).toBe('1');
    expect(wrapper.get('.status-badge').text()).toBe('Completed with failures');
    expect(wrapper.text()).toContain('running → completed');
    expect(wrapper.text()).toContain('Finished · UTC');
    expect(wrapper.text()).toContain('run member-1');
    expect(wrapper.emitted('members')?.[1]?.[1]).toEqual([
      { ...member(0), status: 'failed', error_message: 'Data unavailable' },
      { ...member(1), status: 'succeeded' },
    ]);
    wrapper.unmount();
    vi.useRealTimers();
  });

  it('shows live run context and elapsed time, then freezes the final duration', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(batch.accepted_at_ms + 10_000);
    vi.mocked(getBacktestBatch).mockResolvedValue({ ...batch, status: 'running',
      started_at_ms: batch.accepted_at_ms, active_member_ordinal: 0,
      next_member_ordinal: 1, outcome_counts: { ...batch.outcome_counts, running: 1, queued: 1 } });
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(wrapper.get('.activity-copy').text()).toContain('Running #1 of 2');
    expect(wrapper.get('.active-context').text()).toContain('Fast window: 5');
    expect(wrapper.get('.activity-copy').text()).toContain('Up next: run #2');
    expect(wrapper.get('.elapsed strong').text()).toBe('10s');
    vi.advanceTimersByTime(1000);
    await flushPromises();
    expect(wrapper.get('.elapsed strong').text()).toBe('11s');
    vi.mocked(getBacktestBatch).mockResolvedValue({ ...batch, status: 'completed',
      started_at_ms: batch.accepted_at_ms, completed_at_ms: batch.accepted_at_ms + 12_000,
      active_member_ordinal: null, next_member_ordinal: null, settled_count: 2, executed_count: 2,
      outcome_counts: { ...batch.outcome_counts, queued: 0, succeeded: 2 } });
    vi.advanceTimersByTime(4000);
    await flushPromises();
    expect(wrapper.get('.elapsed strong').text()).toBe('12s');
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('2');
    expect(wrapper.findAll('button')).toHaveLength(0);
    vi.advanceTimersByTime(10_000);
    await flushPromises();
    expect(wrapper.get('.elapsed strong').text()).toBe('12s');
    wrapper.unmount();
    expect(vi.getTimerCount()).toBe(0);
    vi.useRealTimers();
  });

  it('marks failed polling as unknown, retains counts, and recovers on the next poll', async () => {
    vi.useFakeTimers();
    vi.mocked(getBacktestBatch).mockResolvedValueOnce(batch)
      .mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValue(batch);
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.get('.status-badge').text()).toBe('Status unknown');
    expect(wrapper.get('[role="alert"]').text()).toContain('last saved snapshot');
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuemax')).toBe('2');
    expect(wrapper.text()).toContain('Updates interrupted');
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.get('.status-badge').text()).toBe('Queued');
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    wrapper.unmount();
    vi.useRealTimers();
  });

  it('counts cancelled runs as settled without counting them as executed', async () => {
    vi.mocked(getBacktestBatch).mockResolvedValue({ ...batch, status: 'cancelled',
      settled_count: 2, executed_count: 1, next_member_ordinal: null,
      outcome_counts: { ...batch.outcome_counts, queued: 0, succeeded: 1, cancelled: 1 } });
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuetext')).toBe('2 / 2 settled; 1 executed');
    expect(wrapper.get('.progress-percent').text()).toBe('100%');
    expect(wrapper.get('.status-badge').text()).toBe('Cancelled');
    expect(wrapper.get('.outcome-grid .cancelled dd').text()).toBe('1');
    expect(wrapper.findAll('button')).toHaveLength(0);
    wrapper.unmount();
  });

});
