import {
  setupWorkspaceTests,
  refreshActivity,
  run,
  backtest,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  cancelBacktestRun,
  controlBacktest,
  getBacktest,
  listBacktestEvents,
  listBacktestMembers,
  listBacktests,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: history-cancellation', () => {
  setupWorkspaceTests();

  it(
    'cancels one queued Backtest member from the combined table and ' +
      'refreshes that member',

    async () => {
      const accepted = {
        ...backtest('cancellable', 2),
        status: 'queued' as const,
      };
      const queued = [0, 1].map((ordinal) =>
        run(`member-${ordinal}`, {
          backtest_id: 'cancellable',
          run_ordinal: ordinal,
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
      vi.mocked(listBacktests).mockResolvedValue([accepted]);
      vi.mocked(getBacktest).mockResolvedValue(accepted);
      vi.mocked(listBacktestEvents).mockResolvedValue([]);
      vi.mocked(listBacktestMembers)
        .mockResolvedValueOnce(queued)
        .mockResolvedValue([cancelled, queued[1]]);
      vi.mocked(cancelBacktestRun).mockResolvedValue(cancelled);
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-backtest-cancellable"]')
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
        wrapper.find('[data-testid="workspace-backtest-members"]').exists(),
      ).toBe(false);
      wrapper.unmount();
    },
  );

  it('refreshes history and queue after Backtest cancellation', async () => {
    const queued = {
      ...backtest('whole-backtest', 2),
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
    vi.mocked(listBacktests)
      .mockResolvedValueOnce([queued])
      .mockResolvedValue([cancelled]);
    vi.mocked(getBacktest)
      .mockResolvedValueOnce(queued)
      .mockResolvedValue(cancelled);
    vi.mocked(listBacktestMembers).mockResolvedValue([]);
    vi.mocked(listBacktestEvents).mockResolvedValue([]);
    vi.mocked(controlBacktest).mockResolvedValue({
      backtest_id: 'whole-backtest',
      command_id: 'cancel-command',
      status: 'cancelled',
      lifecycle_revision: 2,
    });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-backtest-whole-backtest"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-cancel-backtest"]')
      .trigger('click');
    await flushPromises();
    expect(controlBacktest).toHaveBeenCalledWith(
      'whole-backtest',
      'cancel',
      expect.any(String),
    );
    expect(listBacktests).toHaveBeenCalledTimes(2);
    expect(refreshActivity).toHaveBeenCalledOnce();
    expect(
      wrapper.find('[data-testid="workspace-backtest-whole-backtest"]').text(),
    ).toContain('cancelled');
    wrapper.unmount();
  });
});
