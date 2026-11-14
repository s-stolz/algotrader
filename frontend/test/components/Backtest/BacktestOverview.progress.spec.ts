import {
  emitBacktestChange,
  emitBacktestEvent,
} from '../../backtestEventSocket';
import { installBacktestSocket } from '../../backtestEventSocket';
import { createPinia, setActivePinia } from 'pinia';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getBacktest,
  listBacktestEvents,
  listBacktestMembers,
  controlBacktest,
} from '@/api/backtesterClient';
import BacktestOverview from '@/components/Backtest/BacktestOverview.vue';

vi.mock('@/api/backtesterClient', () => ({
  controlBacktest: vi.fn(),
  renameExperiment: vi.fn(),
  getBacktest: vi.fn(),
  listBacktestEvents: vi.fn(),
  listBacktestMembers: vi.fn(),
}));

import { backtest, member } from './backtestOverviewFixtures';

describe('accepted backtest inspection: progress', () => {
  beforeEach(() => {
    installBacktestSocket();
    setActivePinia(createPinia());
    vi.mocked(controlBacktest).mockReset();
    vi.mocked(getBacktest).mockReset().mockResolvedValue(backtest);
    vi.mocked(listBacktestMembers)
      .mockReset()
      .mockResolvedValue([member(0), member(1)]);
    vi.mocked(listBacktestEvents)
      .mockReset()
      .mockResolvedValue([
        {
          backtest_id: 'backtest-1',
          revision: 0,
          event_type: 'accepted',
          status: 'queued',
          prior_status: null,
          occurred_at_ms: backtest.accepted_at_ms,
          trigger_run_id: null,
          reason: null,
        },
      ]);
  });

  it('restores a running stage received before mount and hides it after settlement', async () => {
    vi.mocked(getBacktest).mockResolvedValue({
      ...backtest,
      status: 'running',
    });
    vi.mocked(listBacktestMembers).mockResolvedValue([
      { ...member(0), status: 'running' },
    ]);
    emitBacktestEvent({
      type: 'backtestProgress',
      run_id: member(0).run_id,
      stage: 'simulating',
    });
    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    await flushPromises();
    expect(wrapper.get('.run-progress [aria-current="step"]').text()).toBe(
      'Simulating',
    );
    const reads = vi.mocked(getBacktest).mock.calls.length;
    emitBacktestEvent({
      type: 'backtestProgress',
      run_id: member(0).run_id,
      stage: 'simulating',
      processed_candles: 5000,
      total_candles: 10000,
    });
    await flushPromises();
    expect(wrapper.get('.candle-count').text()).toBe('5,000 / 10,000');
    expect(wrapper.get('.milestone-fill').attributes('style')).toContain(
      '62.5%',
    );
    emitBacktestEvent({
      type: 'backtestProgress',
      run_id: member(0).run_id,
      stage: 'saving',
    });
    await flushPromises();
    expect(wrapper.get('.run-progress [aria-current="step"]').text()).toBe(
      'Saving',
    );
    expect(wrapper.find('.candle-count').exists()).toBe(false);
    expect(vi.mocked(getBacktest).mock.calls).toHaveLength(reads);
    vi.mocked(listBacktestMembers).mockResolvedValue([
      { ...member(0), status: 'succeeded' },
    ]);
    emitBacktestChange();
    await flushPromises();
    expect(wrapper.find('.run-progress').exists()).toBe(false);
    emitBacktestEvent({
      type: 'backtestProgress',
      run_id: member(0).run_id,
      stage: 'simulating',
    });
    await flushPromises();
    expect(wrapper.find('.run-progress').exists()).toBe(false);
    wrapper.unmount();
  });

  it(
    'preserves successful results and shows partial failure, ordinals, ' +
      'and transitions after refresh',
    async () => {
      vi.mocked(getBacktest)
        .mockResolvedValueOnce({
          ...backtest,
          status: 'running',
          lifecycle_revision: 2,
          started_at_ms: backtest.accepted_at_ms + 1000,
          active_run_ordinal: 1,
          next_run_ordinal: null,
          settled_count: 1,
          executed_count: 1,
          outcome_counts: {
            queued: 0,
            running: 1,
            cancelling: 0,
            succeeded: 0,
            failed: 1,
            cancelled: 0,
          },
          has_failed_members: true,
        })
        .mockResolvedValue({
          ...backtest,
          status: 'completed',
          lifecycle_revision: 3,
          started_at_ms: backtest.accepted_at_ms + 1000,
          completed_at_ms: backtest.accepted_at_ms + 3000,
          active_run_ordinal: null,
          next_run_ordinal: null,
          settled_count: 2,
          executed_count: 2,
          outcome_counts: {
            queued: 0,
            running: 0,
            cancelling: 0,
            succeeded: 1,
            failed: 1,
            cancelled: 0,
          },
          has_failed_members: true,
        });
      vi.mocked(listBacktestMembers)
        .mockResolvedValueOnce([
          { ...member(0), status: 'failed', error_message: 'Data unavailable' },
          { ...member(1), status: 'running' },
        ])
        .mockResolvedValue([
          { ...member(0), status: 'failed', error_message: 'Data unavailable' },
          { ...member(1), status: 'succeeded' },
        ]);
      vi.mocked(listBacktestEvents).mockResolvedValue([
        {
          backtest_id: 'backtest-1',
          revision: 0,
          event_type: 'accepted',
          status: 'queued',
          prior_status: null,
          occurred_at_ms: backtest.accepted_at_ms,
          trigger_run_id: null,
          reason: null,
        },
        {
          backtest_id: 'backtest-1',
          revision: 1,
          event_type: 'started',
          status: 'running',
          prior_status: 'queued',
          occurred_at_ms: backtest.accepted_at_ms + 1000,
          trigger_run_id: 'member-0',
          reason: null,
        },
        {
          backtest_id: 'backtest-1',
          revision: 3,
          event_type: 'completed',
          status: 'completed',
          prior_status: 'running',
          occurred_at_ms: backtest.accepted_at_ms + 3000,
          trigger_run_id: 'member-1',
          reason: null,
        },
      ]);
      vi.useFakeTimers();
      const wrapper = mount(BacktestOverview, {
        props: { backtestId: 'backtest-1' },
      });
      await flushPromises();
      expect(
        wrapper.get('[role="progressbar"]').attributes('aria-valuenow'),
      ).toBe('1');
      expect(wrapper.get('.status-badge').text()).toBe('Running');
      expect(wrapper.emitted('members')?.[0]?.[1]).toEqual([
        { ...member(0), status: 'failed', error_message: 'Data unavailable' },
        { ...member(1), status: 'running' },
      ]);
      vi.advanceTimersByTime(5000);
      emitBacktestChange();
      await flushPromises();
      expect(wrapper.find('[role="progressbar"]').exists()).toBe(false);
      expect(
        wrapper.get('[data-testid="backtest-outcome-succeeded"]').text(),
      ).toBe('Succeeded 1');
      expect(wrapper.get('.status-badge').text()).toBe(
        'Completed with failures',
      );
      expect(wrapper.text()).toContain('running → completed');
      expect(wrapper.text()).toContain('Finished · UTC');
      expect(wrapper.text()).toContain('Run member-1');
      expect(wrapper.emitted('members')?.[1]?.[1]).toEqual([
        { ...member(0), status: 'failed', error_message: 'Data unavailable' },
        { ...member(1), status: 'succeeded' },
      ]);
      wrapper.unmount();
      vi.useRealTimers();
    },
  );

  it('shows live run context and elapsed time, then freezes the final duration', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(backtest.accepted_at_ms + 10_000);
    vi.mocked(getBacktest).mockResolvedValue({
      ...backtest,
      status: 'running',
      started_at_ms: backtest.accepted_at_ms,
      active_run_ordinal: 0,
      next_run_ordinal: 1,
      outcome_counts: { ...backtest.outcome_counts, running: 1, queued: 1 },
    });
    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    await flushPromises();
    expect(wrapper.get('.status-badge').text()).toBe('Running');
    expect(
      wrapper.get('[role="progressbar"]').attributes('aria-valuemax'),
    ).toBe('2');
    expect(wrapper.get('[data-testid="backtest-duration"]').text()).toBe('10s');
    vi.advanceTimersByTime(1000);
    await flushPromises();
    expect(wrapper.get('[data-testid="backtest-duration"]').text()).toBe('11s');
    vi.mocked(getBacktest).mockResolvedValue({
      ...backtest,
      status: 'completed',
      started_at_ms: backtest.accepted_at_ms,
      completed_at_ms: backtest.accepted_at_ms + 12_000,
      active_run_ordinal: null,
      next_run_ordinal: null,
      settled_count: 2,
      executed_count: 2,
      outcome_counts: { ...backtest.outcome_counts, queued: 0, succeeded: 2 },
    });
    vi.advanceTimersByTime(4000);
    emitBacktestChange();
    await flushPromises();
    expect(wrapper.get('[data-testid="backtest-duration"]').text()).toBe('12s');
    expect(wrapper.find('[role="progressbar"]').exists()).toBe(false);
    expect(wrapper.get('.status-badge').text()).toBe('Completed');
    expect(wrapper.findAll('.header-actions button')).toHaveLength(0);
    vi.advanceTimersByTime(10_000);
    emitBacktestChange();
    await flushPromises();
    expect(wrapper.get('[data-testid="backtest-duration"]').text()).toBe('12s');
    wrapper.unmount();
    expect(vi.getTimerCount()).toBe(0);
    vi.useRealTimers();
  });

  it('retains state after a failed refresh and recovers on the next event', async () => {
    vi.useFakeTimers();
    vi.mocked(getBacktest)
      .mockResolvedValueOnce(backtest)
      .mockRejectedValueOnce(new Error('Connection lost'))
      .mockResolvedValue(backtest);
    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    await flushPromises();
    vi.advanceTimersByTime(5000);
    emitBacktestChange();
    await flushPromises();
    expect(wrapper.get('.status-badge').text()).toBe('Status unknown');
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'Couldn’t refresh this backtest. Showing saved data.',
    );
    expect(
      wrapper.get('[role="progressbar"]').attributes('aria-valuemax'),
    ).toBe('2');
    vi.advanceTimersByTime(5000);
    emitBacktestChange();
    await flushPromises();
    expect(wrapper.get('.status-badge').text()).toBe('Queued');
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    wrapper.unmount();
    vi.useRealTimers();
  });

  it('shows terminal cancellation outcomes and disables active controls', async () => {
    vi.mocked(getBacktest).mockResolvedValue({
      ...backtest,
      status: 'cancelled',
      settled_count: 2,
      executed_count: 1,
      next_run_ordinal: null,
      outcome_counts: {
        ...backtest.outcome_counts,
        queued: 0,
        succeeded: 1,
        cancelled: 1,
      },
    });
    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    await flushPromises();
    expect(wrapper.find('[role="progressbar"]').exists()).toBe(false);
    expect(
      wrapper.get('[data-testid="backtest-outcome-succeeded"]').text(),
    ).toBe('Succeeded 1');
    expect(wrapper.get('.status-badge').text()).toBe('Cancelled');
    expect(
      wrapper.get('[data-testid="backtest-outcome-cancelled"]').text(),
    ).toBe('Cancelled 1');
    expect(wrapper.findAll('.header-actions button')).toHaveLength(0);
    wrapper.unmount();
  });
});
