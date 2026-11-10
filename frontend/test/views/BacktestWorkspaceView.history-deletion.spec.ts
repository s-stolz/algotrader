import {
  setupWorkspaceTests,
  run,
  backtest,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  deleteBacktest,
  getBacktest,
  listBacktestEvents,
  listBacktestMembers,
  listBacktests,
  listBacktestRuns,
} from '@/api/backtesterClient';

import { useExecutionLogStore } from '@/stores/executionLogStore';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';

describe('production Backtest Workspace: history-deletion', () => {
  setupWorkspaceTests();

  it(
    'keeps a Backtest visible after delete conflict, then refreshes and ' +
      'clears its selection',

    async () => {
      const accepted = backtest('delete-me', 1);
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktests)
        .mockResolvedValueOnce([accepted])
        .mockResolvedValueOnce([]);
      vi.mocked(getBacktest).mockResolvedValue(accepted);
      vi.mocked(listBacktestMembers).mockResolvedValue([
        run('member-1', {
          backtest_id: 'delete-me',
          run_ordinal: 0,
        }),
      ]);
      vi.mocked(listBacktestEvents).mockResolvedValue([]);
      vi.mocked(deleteBacktest).mockRejectedValueOnce(new Error('Conflict'));
      vi.stubGlobal(
        'confirm',
        vi.fn(() => true),
      );
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-backtest-delete-me"]')
        .trigger('click');
      await flushPromises();
      const overlay = useBacktestOverlayStore();
      overlay.selectedRunId = 'member-1';
      overlay.selectedRun = run('member-1', {
        backtest_id: 'delete-me',
        run_ordinal: 0,
      });

      const log = useExecutionLogStore();
      log.selectRun(overlay.selectedRun, false);

      await wrapper
        .find('[data-testid="workspace-delete-backtest-delete-me"]')
        .trigger('click');
      await flushPromises();
      expect(
        wrapper.find('[data-testid="workspace-backtest-delete-me"]').exists(),
      ).toBe(true);
      expect(wrapper.text()).toContain('Conflict');
      expect(log.selectedRun?.run_id).toBe('member-1');
      expect(listBacktests).toHaveBeenCalledTimes(1);

      await wrapper
        .find('[data-testid="workspace-delete-backtest-delete-me"]')
        .trigger('click');
      await flushPromises();
      expect(deleteBacktest).toHaveBeenCalledTimes(2);
      expect(
        wrapper.find('[data-testid="workspace-backtest-delete-me"]').exists(),
      ).toBe(false);
      expect(overlay.selectedRunId).toBeNull();
      expect(log.selectedRun).toBeNull();
      expect(log.isOpen).toBe(false);
      expect(wrapper.text()).not.toContain('Conflict');
      wrapper.unmount();
    },
  );
});
