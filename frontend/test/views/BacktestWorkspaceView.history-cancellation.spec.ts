import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  cancelBacktestRun,
  controlBacktestBatch,
  fetchBacktestQueue,
  getBacktestBatch,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: history-cancellation', () => {
  setupWorkspaceTests();
  it('cancels a queued standalone run once and refreshes its durable status', async () => {
    const queued = run('queued', {
      status: 'queued',
      started_at_ms: null,
      completed_at_ms: null,
      result_schema_version: null,
      metrics: null,
    });
    const cancelled = run('queued', {
      ...queued,
      status: 'cancelled',
      completed_at_ms: 1_780_922_100_000,
      cancel_requested_at_ms: 1_780_922_100_000,
      cancellation_source: 'user',
      cancellation_reason: 'user_requested',
    });
    vi.mocked(listBacktestRuns)
      .mockResolvedValueOnce([queued])
      .mockResolvedValueOnce([cancelled]);
    vi.mocked(cancelBacktestRun).mockResolvedValue(cancelled);
    const wrapper = mountWorkspace();
    await flushPromises();

    const cancelButton = wrapper.find(
      '[data-testid="workspace-cancel-queued"]',
    );
    await cancelButton.trigger('click');
    await flushPromises();

    expect(cancelBacktestRun).toHaveBeenCalledOnce();
    expect(cancelBacktestRun).toHaveBeenCalledWith('queued');
    expect(
      wrapper.find('[data-testid="workspace-run-queued"]').text(),
    ).toContain('cancelled');
    expect(
      wrapper.find('[data-testid="workspace-cancel-queued"]').exists(),
    ).toBe(false);
    wrapper.unmount();
  });

  it(
    'cancels one queued Batch member from the combined table and ' +
      'refreshes that member',

    async () => {
      const accepted = {
        ...batch('cancellable', 2),
        status: 'queued' as const,
      };
      const queued = [0, 1].map((ordinal) =>
        run(`member-${ordinal}`, {
          batch_id: 'cancellable',
          member_ordinal: ordinal,
          status: 'queued',
          started_at_ms: null,
          completed_at_ms: null,
          result_schema_version: null,
          metrics: null,
        }),
      );
      const cancelled = {
        ...queued[0],
        status: 'cancelled' as const,
        completed_at_ms: 1_780_922_100_000,
        cancel_requested_at_ms: 1_780_922_100_000,
        cancellation_source: 'user' as const,
        cancellation_reason: 'user_requested' as const,
      };
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
      vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
      vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
      vi.mocked(listBacktestBatchMembers)
        .mockResolvedValueOnce(queued)
        .mockResolvedValue([cancelled, queued[1]]);
      vi.mocked(cancelBacktestRun).mockResolvedValue(cancelled);
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-batch-cancellable"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-cancel-member-0"]')
        .trigger('click');
      await flushPromises();
      expect(cancelBacktestRun).toHaveBeenCalledOnce();
      expect(cancelBacktestRun).toHaveBeenCalledWith('member-0');
      expect(
        wrapper.find('[data-testid="workspace-cancel-member-0"]').exists(),
      ).toBe(false);
      expect(
        wrapper
          .find('[data-testid="workspace-cancel-member-1"]')
          .attributes('disabled'),
      ).toBeUndefined();
      expect(
        wrapper.find('[data-testid="workspace-batch-members"]').exists(),
      ).toBe(false);
      wrapper.unmount();
    },
  );

  it('refreshes combined history and queue health after cancelling an entire Batch', async () => {
    const queued = {
      ...batch('whole-batch', 2),
      status: 'queued' as const,
      completed_at_ms: null,
      settled_count: 0,
      executed_count: 0,
      outcome_counts: {
        queued: 2,
        running: 0,
        cancelling: 0,
        succeeded: 0,
        failed: 0,
        cancelled: 0,
      },
    };
    const cancelled = {
      ...queued,
      status: 'cancelled' as const,
      completed_at_ms: 1_780_922_100_000,
      settled_count: 2,
      cancel_requested_at_ms: 1_780_922_100_000,
      outcome_counts: {
        queued: 0,
        running: 0,
        cancelling: 0,
        succeeded: 0,
        failed: 0,
        cancelled: 2,
      },
    };
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches)
      .mockResolvedValueOnce([queued])
      .mockResolvedValue([cancelled]);
    vi.mocked(getBacktestBatch)
      .mockResolvedValueOnce(queued)
      .mockResolvedValue(cancelled);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([]);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(controlBacktestBatch).mockResolvedValue({
      batch_id: 'whole-batch',
      command_id: 'cancel-command',
      status: 'cancelled',
      lifecycle_revision: 2,
    });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-batch-whole-batch"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-cancel-batch"]')
      .trigger('click');
    await flushPromises();
    expect(controlBacktestBatch).toHaveBeenCalledWith(
      'whole-batch',
      'cancel',
      expect.any(String),
    );
    expect(listBacktestBatches).toHaveBeenCalledTimes(2);
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(
      wrapper.find('[data-testid="workspace-batch-whole-batch"]').text(),
    ).toContain('cancelled');
    wrapper.unmount();
  });
});
