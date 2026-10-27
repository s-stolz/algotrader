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

describe('accepted batch inspection: commands', () => {
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

  it('offers legal pause and resume controls and refreshes after command acceptance', async () => {
    vi.mocked(controlBacktestBatch).mockResolvedValueOnce({
      batch_id: 'batch-1',
      status: 'paused',
      lifecycle_revision: 1,
    });
    vi.mocked(getBacktestBatch)
      .mockResolvedValueOnce(batch)
      .mockResolvedValue({ ...batch, status: 'paused', lifecycle_revision: 1 });
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    expect(controlBacktestBatch).toHaveBeenCalledWith(
      'batch-1',
      'pause',
      expect.any(String),
    );
    expect(wrapper.text()).toContain('Batch paused.');
    expect(wrapper.get('.header-actions button').text()).toBe('Resume Batch');
    expect(wrapper.get('p[role="status"]').text()).not.toContain('%');
    wrapper.unmount();
  });

  it('cancels an executing batch and keeps its active member visibly unsettled', async () => {
    const running = {
      ...batch,
      status: 'running' as const,
      active_member_ordinal: 0,
      outcome_counts: { ...batch.outcome_counts, queued: 1, running: 1 },
    };
    const cancelling = {
      ...running,
      status: 'cancelling' as const,
      cancel_requested_at_ms: batch.accepted_at_ms + 1,
      cancellation_source: 'user',
      cancellation_reason: 'user_requested',
      lifecycle_revision: 2,
      next_member_ordinal: null,
      outcome_counts: {
        ...batch.outcome_counts,
        queued: 0,
        running: 0,
        cancelling: 1,
        cancelled: 1,
      },
      settled_count: 1,
    };
    vi.mocked(getBacktestBatch)
      .mockResolvedValueOnce(running)
      .mockResolvedValue(cancelling);
    vi.mocked(listBacktestBatchMembers)
      .mockResolvedValueOnce([{ ...member(0), status: 'running' }, member(1)])
      .mockResolvedValue([
        {
          ...member(0),
          status: 'cancelling',
          cancel_requested_at_ms: batch.accepted_at_ms + 1,
          cancellation_source: 'batch',
          cancellation_reason: 'batch_cancel_requested',
        },
        {
          ...member(1),
          status: 'cancelled',
          cancel_requested_at_ms: batch.accepted_at_ms + 1,
          completed_at_ms: batch.accepted_at_ms + 1,
          cancellation_source: 'batch',
          cancellation_reason: 'batch_cancel_requested',
        },
      ]);
    vi.mocked(controlBacktestBatch).mockImplementation(
      async (_id, _command, commandId) => ({
        batch_id: 'batch-1',
        command_id: commandId,
        status: 'cancelling',
        lifecycle_revision: 2,
      }),
    );
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-cancel-batch"]')
      .trigger('click');
    await flushPromises();
    expect(controlBacktestBatch).toHaveBeenCalledWith(
      'batch-1',
      'cancel',
      expect.any(String),
    );
    expect(
      wrapper.get('[role="progressbar"]').attributes('aria-valuetext'),
    ).toContain('1 / 2 settled');
    expect(wrapper.text()).toContain('0 executed');
    expect(wrapper.text()).toContain('Cancellation will finish after cleanup');
    expect(wrapper.text()).toContain('Cancellation accepted:');
    expect(
      wrapper.find('[data-testid="workspace-cancel-batch"]').exists(),
    ).toBe(false);
    expect(wrapper.emitted('cancelled')).toHaveLength(1);
    wrapper.unmount();
  });

  it('shows draining state and retries a failed command with the same identity', async () => {
    const draining = {
      ...batch,
      status: 'pausing' as const,
      lifecycle_revision: 2,
      active_member_ordinal: 0,
    };
    vi.mocked(getBacktestBatch).mockResolvedValue(draining);
    vi.mocked(controlBacktestBatch)
      .mockRejectedValueOnce(new Error('Connection lost'))
      .mockResolvedValueOnce({
        batch_id: 'batch-1',
        status: 'running',
        lifecycle_revision: 3,
      });
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(wrapper.text()).toContain('Pausing after the active run finishes.');
    expect(wrapper.get('.header-actions button').text()).toBe('Resume Batch');
    expect(wrapper.get('p[role="status"]').text()).not.toContain('%');
    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Connection lost');
    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    const calls = vi.mocked(controlBacktestBatch).mock.calls;
    expect(calls[0][2]).toBe(calls[1][2]);
    wrapper.unmount();
  });

  it(
    'retains a pending Pause identity when member cancellation ' +
      'advances the batch revision',
    async () => {
      vi.mocked(getBacktestBatch)
        .mockResolvedValueOnce(batch)
        .mockResolvedValue({
          ...batch,
          status: 'queued',
          lifecycle_revision: 1,
        });
      vi.mocked(listBacktestBatchEvents)
        .mockResolvedValueOnce([
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
        ])
        .mockResolvedValue([
          {
            batch_id: 'batch-1',
            revision: 1,
            event_type: 'member_cancelled',
            status: 'queued',
            prior_status: 'queued',
            occurred_at_ms: batch.accepted_at_ms + 1,
            trigger_run_id: 'member-0',
            reason: 'user_requested',
            command_id: null,
          },
        ]);
      vi.mocked(controlBacktestBatch).mockRejectedValue(
        new Error('Connection lost'),
      );
      const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
      await flushPromises();
      await wrapper.get('.header-actions button').trigger('click');
      await flushPromises();
      await wrapper.get('.header-actions button').trigger('click');
      await flushPromises();
      const calls = vi.mocked(controlBacktestBatch).mock.calls;
      expect(calls).toHaveLength(2);
      expect(calls[0][2]).toBe(calls[1][2]);
      wrapper.unmount();
    },
  );

  it('uses a new Pause identity after a lost response, observed pause, and Resume', async () => {
    vi.mocked(getBacktestBatch)
      .mockResolvedValueOnce(batch)
      .mockResolvedValueOnce({
        ...batch,
        status: 'paused',
        lifecycle_revision: 1,
      })
      .mockResolvedValueOnce({
        ...batch,
        status: 'running',
        lifecycle_revision: 2,
      })
      .mockResolvedValue({ ...batch, status: 'paused', lifecycle_revision: 3 });
    vi.mocked(controlBacktestBatch)
      .mockRejectedValueOnce(new Error('Pause response lost'))
      .mockResolvedValueOnce({
        batch_id: 'batch-1',
        status: 'running',
        lifecycle_revision: 2,
      })
      .mockResolvedValueOnce({
        batch_id: 'batch-1',
        status: 'paused',
        lifecycle_revision: 3,
      });

    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    expect(wrapper.get('.header-actions button').text()).toBe('Resume Batch');
    expect(wrapper.text()).toContain('revision 1');

    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    expect(wrapper.get('.header-actions button').text()).toBe('Pause Batch');
    expect(wrapper.text()).toContain('revision 2');

    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    const calls = vi.mocked(controlBacktestBatch).mock.calls;
    expect(calls.map(([, , identity]) => identity)).toHaveLength(3);
    expect(calls.map(([, command]) => command)).toEqual([
      'pause',
      'resume',
      'pause',
    ]);
    expect(calls[2][2]).not.toBe(calls[0][2]);
    expect(wrapper.text()).toContain('revision 3');
    expect(wrapper.text()).toContain('Batch paused.');
    wrapper.unmount();
  });
});
