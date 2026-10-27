import { createPinia, setActivePinia } from 'pinia';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getBacktestBatch,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
  controlBacktestBatch,
} from '@/api/backtesterClient';
import BacktestBatches from '@/components/Backtest/BacktestBatches.vue';

vi.mock('@/api/backtesterClient', () => ({
  controlBacktestBatch: vi.fn(),
  renameExperiment: vi.fn(),
  getBacktestBatch: vi.fn(),
  listBacktestBatchEvents: vi.fn(),
  listBacktestBatchMembers: vi.fn(),
}));

import { batch, member } from './backtestBatchFixtures';

describe('accepted batch inspection: progress', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(controlBacktestBatch).mockReset();
    vi.mocked(getBacktestBatch).mockReset().mockResolvedValue(batch);
    vi.mocked(listBacktestBatchMembers)
      .mockReset()
      .mockResolvedValue([member(0), member(1)]);
    vi.mocked(listBacktestBatchEvents)
      .mockReset()
      .mockResolvedValue([
        {
          batch_id: 'batch-1',
          revision: 0,
          event_type: 'accepted',
          status: 'queued',
          prior_status: null,
          occurred_at_ms: batch.accepted_at_ms,
          trigger_run_id: null,
          reason: null,
        },
      ]);
  });

  it(
    'preserves successful results and shows partial failure, ordinals, ' +
      'and transitions after refresh',
    async () => {
      vi.mocked(getBacktestBatch)
        .mockResolvedValueOnce({
          ...batch,
          status: 'running',
          lifecycle_revision: 2,
          started_at_ms: batch.accepted_at_ms + 1000,
          active_member_ordinal: 1,
          next_member_ordinal: null,
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
          ...batch,
          status: 'completed',
          lifecycle_revision: 3,
          started_at_ms: batch.accepted_at_ms + 1000,
          completed_at_ms: batch.accepted_at_ms + 3000,
          active_member_ordinal: null,
          next_member_ordinal: null,
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
      vi.mocked(listBacktestBatchMembers)
        .mockResolvedValueOnce([
          { ...member(0), status: 'failed', error_message: 'Data unavailable' },
          { ...member(1), status: 'running' },
        ])
        .mockResolvedValue([
          { ...member(0), status: 'failed', error_message: 'Data unavailable' },
          { ...member(1), status: 'succeeded' },
        ]);
      vi.mocked(listBacktestBatchEvents).mockResolvedValue([
        {
          batch_id: 'batch-1',
          revision: 0,
          event_type: 'accepted',
          status: 'queued',
          prior_status: null,
          occurred_at_ms: batch.accepted_at_ms,
          trigger_run_id: null,
          reason: null,
        },
        {
          batch_id: 'batch-1',
          revision: 1,
          event_type: 'started',
          status: 'running',
          prior_status: 'queued',
          occurred_at_ms: batch.accepted_at_ms + 1000,
          trigger_run_id: 'member-0',
          reason: null,
        },
        {
          batch_id: 'batch-1',
          revision: 3,
          event_type: 'completed',
          status: 'completed',
          prior_status: 'running',
          occurred_at_ms: batch.accepted_at_ms + 3000,
          trigger_run_id: 'member-1',
          reason: null,
        },
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
      expect(
        wrapper.get('[role="progressbar"]').attributes('aria-valuetext'),
      ).toContain('2 / 2 settled');
      expect(wrapper.get('.outcome-grid .succeeded dd').text()).toBe('1');
      expect(wrapper.get('.status-badge').text()).toBe(
        'Completed with failures',
      );
      expect(wrapper.text()).toContain('running → completed');
      expect(wrapper.text()).toContain('Finished · UTC');
      expect(wrapper.text()).toContain('run member-1');
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
    vi.setSystemTime(batch.accepted_at_ms + 10_000);
    vi.mocked(getBacktestBatch).mockResolvedValue({
      ...batch,
      status: 'running',
      started_at_ms: batch.accepted_at_ms,
      active_member_ordinal: 0,
      next_member_ordinal: 1,
      outcome_counts: { ...batch.outcome_counts, running: 1, queued: 1 },
    });
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(wrapper.get('.activity-copy').text()).toContain('Running #1 of 2');
    expect(wrapper.get('.active-context').text()).toContain('Fast window: 5');
    expect(wrapper.get('.activity-copy').text()).toContain('Up next: run #2');
    expect(wrapper.get('.elapsed strong').text()).toBe('10s');
    vi.advanceTimersByTime(1000);
    await flushPromises();
    expect(wrapper.get('.elapsed strong').text()).toBe('11s');
    vi.mocked(getBacktestBatch).mockResolvedValue({
      ...batch,
      status: 'completed',
      started_at_ms: batch.accepted_at_ms,
      completed_at_ms: batch.accepted_at_ms + 12_000,
      active_member_ordinal: null,
      next_member_ordinal: null,
      settled_count: 2,
      executed_count: 2,
      outcome_counts: { ...batch.outcome_counts, queued: 0, succeeded: 2 },
    });
    vi.advanceTimersByTime(4000);
    await flushPromises();
    expect(wrapper.get('.elapsed strong').text()).toBe('12s');
    expect(
      wrapper.get('[role="progressbar"]').attributes('aria-valuenow'),
    ).toBe('2');
    expect(wrapper.findAll('.header-actions button')).toHaveLength(0);
    vi.advanceTimersByTime(10_000);
    await flushPromises();
    expect(wrapper.get('.elapsed strong').text()).toBe('12s');
    wrapper.unmount();
    expect(vi.getTimerCount()).toBe(0);
    vi.useRealTimers();
  });

  it('marks failed polling as unknown, retains counts, and recovers on the next poll', async () => {
    vi.useFakeTimers();
    vi.mocked(getBacktestBatch)
      .mockResolvedValueOnce(batch)
      .mockRejectedValueOnce(new Error('Connection lost'))
      .mockResolvedValue(batch);
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.get('.status-badge').text()).toBe('Status unknown');
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'last saved snapshot',
    );
    expect(
      wrapper.get('[role="progressbar"]').attributes('aria-valuemax'),
    ).toBe('2');
    expect(wrapper.text()).toContain('Updates interrupted');
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.get('.status-badge').text()).toBe('Queued');
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    wrapper.unmount();
    vi.useRealTimers();
  });

  it('counts cancelled runs as settled without counting them as executed', async () => {
    vi.mocked(getBacktestBatch).mockResolvedValue({
      ...batch,
      status: 'cancelled',
      settled_count: 2,
      executed_count: 1,
      next_member_ordinal: null,
      outcome_counts: {
        ...batch.outcome_counts,
        queued: 0,
        succeeded: 1,
        cancelled: 1,
      },
    });
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(
      wrapper.get('[role="progressbar"]').attributes('aria-valuetext'),
    ).toBe('2 / 2 settled; 1 executed');
    expect(wrapper.get('.progress-percent').text()).toBe('100%');
    expect(wrapper.get('.status-badge').text()).toBe('Cancelled');
    expect(wrapper.get('.outcome-grid .cancelled dd').text()).toBe('1');
    expect(wrapper.findAll('.header-actions button')).toHaveLength(0);
    wrapper.unmount();
  });
});
