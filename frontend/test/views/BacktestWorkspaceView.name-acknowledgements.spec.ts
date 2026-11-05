import { emitBacktestChange } from '../backtestEventSocket';
import {
  setupWorkspaceTests,
  run,
  backtest,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  renameExperiment,
  getBacktest,
  getBacktestRun,
  listBacktestEvents,
  listBacktestMembers,
  listBacktests,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: name-acknowledgements', () => {
  setupWorkspaceTests();
  it(
    'renames a backtest in detail and updates history search while ' +
      'members remain uneditable',
    async () => {
      vi.useFakeTimers();
      const accepted = { ...backtest('rename-backtest', 1), name: null };
      const memberRun = run('rename-member', {
        backtest_id: accepted.backtest_id,
        run_ordinal: 0,
      });
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktests).mockResolvedValue([accepted]);
      vi.mocked(getBacktest).mockResolvedValue(accepted);
      vi.mocked(listBacktestEvents).mockResolvedValue([]);
      vi.mocked(listBacktestMembers).mockResolvedValue([memberRun]);
      vi.mocked(getBacktestRun).mockResolvedValue(memberRun);
      vi.mocked(renameExperiment).mockResolvedValue('Named selections');
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-backtest-rename-backtest"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .get('.backtest-header button[aria-label^="Edit experiment name"]')
        .trigger('click');
      const input = wrapper.get<HTMLInputElement>(
        '.backtest-header input[aria-label="Experiment name"]',
      );
      expect(input.element.value).toBe('');
      await input.setValue('Named selections');
      await input.trigger('blur');
      await flushPromises();
      expect(renameExperiment).toHaveBeenCalledWith(
        accepted.backtest_id,
        'Named selections',
      );
      await vi.advanceTimersByTimeAsync(5000);
      emitBacktestChange();
      await flushPromises();
      expect(
        wrapper
          .get('.backtest-header button[aria-label^="Edit experiment name"]')
          .text(),
      ).toBe('Named selections');
      await wrapper
        .get('[data-testid="workspace-search"] input')
        .setValue('Named selections');
      expect(
        wrapper
          .get('[data-testid="workspace-backtest-rename-backtest"]')
          .text(),
      ).toContain('Named selections');
      expect(
        wrapper.findAll('button[aria-label^="Edit experiment name"]'),
      ).toHaveLength(1);
      wrapper.unmount();
    },
  );
});
