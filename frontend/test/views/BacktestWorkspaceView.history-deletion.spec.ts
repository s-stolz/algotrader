import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  deleteBacktestBatch,
  deleteBacktestRun,
  fetchBacktestQueue,
  getBacktestBatch,
  getBacktestRun,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';

import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';

describe('production Backtest Workspace: history-deletion', () => {
  setupWorkspaceTests();
  it('distinguishes failed reads from empty history and refreshes after deletion', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const success = run('success');
    vi.mocked(listBacktestRuns)
      .mockResolvedValueOnce([success])
      .mockRejectedValueOnce(new Error('Service unavailable'))
      .mockResolvedValueOnce([]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    vi.stubGlobal(
      'confirm',
      vi.fn(() => true),
    );

    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-refresh"]').exists()).toBe(
      false,
    );
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.get('[data-testid="workspace-refresh"]').text()).toBe(
      'Retry now',
    );
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain('current lifecycle status is unknown');
    expect(wrapper.find('[data-testid="workspace-run-success"]').exists()).toBe(
      true,
    );

    await wrapper
      .find('[data-testid="workspace-delete-success"]')
      .trigger('click');
    await flushPromises();
    expect(deleteBacktestRun).toHaveBeenCalledWith('success');
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(3);
    expect(wrapper.text()).toContain('No saved Backtest Runs or Batches.');
    expect(wrapper.text()).not.toContain('current lifecycle status is unknown');
    expect(wrapper.find('[data-testid="workspace-refresh"]').exists()).toBe(
      false,
    );
    wrapper.unmount();
  });

  it(
    'sends one DELETE for rapid duplicate clicks and disables that ' +
      'run while deleting',

    async () => {
      const success = run('success');
      let finishDelete!: () => void;
      vi.mocked(listBacktestRuns)
        .mockResolvedValueOnce([success])
        .mockResolvedValueOnce([]);
      vi.mocked(deleteBacktestRun)
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              finishDelete = resolve;
            }),
        )
        .mockRejectedValueOnce(new Error('404 Not Found'));
      const confirm = vi.fn(() => true);
      vi.stubGlobal('confirm', confirm);
      const wrapper = mountWorkspace();
      await flushPromises();

      const deleteButton = wrapper.find(
        '[data-testid="workspace-delete-success"]',
      );
      deleteButton.element.dispatchEvent(
        new MouseEvent('click', { bubbles: true }),
      );
      deleteButton.element.dispatchEvent(
        new MouseEvent('click', { bubbles: true }),
      );
      await wrapper.vm.$nextTick();

      expect(deleteBacktestRun).toHaveBeenCalledOnce();
      expect(confirm).toHaveBeenCalledOnce();
      expect(
        wrapper
          .find('[data-testid="workspace-delete-success"]')
          .attributes('disabled'),
      ).toBeDefined();

      finishDelete();
      await flushPromises();
      expect(
        wrapper.find('[data-testid="workspace-run-success"]').exists(),
      ).toBe(false);
      expect(wrapper.text()).not.toContain('404 Not Found');
      wrapper.unmount();
    },
  );

  it(
    'keeps a Batch visible after delete conflict, then refreshes and ' +
      'clears its selection',

    async () => {
      const accepted = batch('delete-me', 1);
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktestBatches)
        .mockResolvedValueOnce([accepted])
        .mockResolvedValueOnce([]);
      vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
      vi.mocked(listBacktestBatchMembers).mockResolvedValue([
        run('member-1', {
          batch_id: 'delete-me',
          member_ordinal: 0,
        }),
      ]);
      vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
      vi.mocked(deleteBacktestBatch).mockRejectedValueOnce(
        new Error('Conflict'),
      );
      vi.stubGlobal(
        'confirm',
        vi.fn(() => true),
      );
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-batch-delete-me"]')
        .trigger('click');
      await flushPromises();
      const overlay = useBacktestOverlayStore();
      overlay.selectedRunId = 'member-1';
      overlay.selectedRun = run('member-1', {
        batch_id: 'delete-me',
        member_ordinal: 0,
      });

      await wrapper
        .find('[data-testid="workspace-delete-batch-delete-me"]')
        .trigger('click');
      await flushPromises();
      expect(
        wrapper.find('[data-testid="workspace-batch-delete-me"]').exists(),
      ).toBe(true);
      expect(wrapper.text()).toContain('Conflict');
      expect(listBacktestBatches).toHaveBeenCalledTimes(1);

      await wrapper
        .find('[data-testid="workspace-delete-batch-delete-me"]')
        .trigger('click');
      await flushPromises();
      expect(deleteBacktestBatch).toHaveBeenCalledTimes(2);
      expect(
        wrapper.find('[data-testid="workspace-batch-delete-me"]').exists(),
      ).toBe(false);
      expect(wrapper.text()).toContain('removed from the chart overlay');
      expect(overlay.selectedRunId).toBeNull();
      expect(wrapper.text()).not.toContain('Conflict');
      wrapper.unmount();
    },
  );
});
