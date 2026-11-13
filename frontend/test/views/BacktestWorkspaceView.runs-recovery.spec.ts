import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import {
  setupWorkspaceTests,
  mountWorkspace,
  backtest,
  run,
} from './backtestWorkspaceFixtures';
import {
  getBacktest,
  listBacktests,
  listBacktestMembers,
} from '@/api/backtesterClient';

describe('Backtest runs recovery', () => {
  setupWorkspaceTests();

  it.each(['empty', 'failed'])(
    'retries a %s member read from the Runs section',
    async (result) => {
      const saved = backtest('recover', 1);
      const member = run('recover-0', {
        backtest_id: 'recover',
        run_ordinal: 0,
      });
      vi.mocked(getBacktest).mockResolvedValue(saved);
      vi.mocked(listBacktests).mockResolvedValue([saved]);
      if (result === 'empty')
        vi.mocked(listBacktestMembers).mockResolvedValueOnce([]);
      else
        vi.mocked(listBacktestMembers).mockRejectedValueOnce(
          new Error('Offline'),
        );
      vi.mocked(listBacktestMembers).mockResolvedValue([member]);
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-backtest-recover"]')
        .trigger('click');
      await flushPromises();
      const runs = wrapper.get('.current-backtest .table-panel');
      expect(runs.get('[role="alert"]').text()).toBe('Couldn’t load runs');
      await runs.get('[aria-label="Retry: Runs unavailable"]').trigger('click');
      await flushPromises();
      expect(listBacktestMembers).toHaveBeenCalledTimes(2);
      expect(
        runs.get('[data-testid="workspace-member-recover-0"]').text(),
      ).toContain('Run #1');
      wrapper.unmount();
    },
  );
});
