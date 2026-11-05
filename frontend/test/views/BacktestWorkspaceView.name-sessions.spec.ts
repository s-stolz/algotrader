import {
  setupWorkspaceTests,
  backtest,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  renameExperiment,
  getBacktest,
  listBacktestEvents,
  listBacktestMembers,
  listBacktests,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: name-sessions', () => {
  setupWorkspaceTests();

  it.each(['Enter', 'blur'] as const)(
    'persists a newer committed name after %s and navigation',
    async (gesture) => {
      vi.useFakeTimers();
      const source = { ...backtest('departed-backtest', 1), name: 'Original' };
      const other = { ...backtest('other-backtest', 1), name: 'Other' };
      vi.mocked(listBacktests).mockResolvedValue([source, other]);
      vi.mocked(getBacktest).mockImplementation(async (id) =>
        id === source.backtest_id ? source : other,
      );
      vi.mocked(listBacktestMembers).mockResolvedValue([]);
      vi.mocked(listBacktestEvents).mockResolvedValue([]);
      let firstSave!: (name: string | null) => void;
      vi.mocked(renameExperiment)
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              firstSave = resolve;
            }),
        )
        .mockResolvedValueOnce('Newer committed');
      const wrapper = mountWorkspace(true);
      await flushPromises();
      const sourceId = source.backtest_id;
      const sourceRow = `[data-testid="workspace-backtest-${sourceId}"]`;
      await wrapper.get(sourceRow).trigger('click');
      await flushPromises();
      const sourceHeading = '.backtest-header';
      await wrapper
        .get(`${sourceHeading} button[aria-label^="Edit experiment name"]`)
        .trigger('click');
      const input = wrapper.get(
        `${sourceHeading} input[aria-label="Experiment name"]`,
      );
      await input.setValue('First');
      await input.trigger('keydown', { key: 'Enter' });
      await input.setValue('Newer committed');
      if (gesture === 'Enter') await input.trigger('keydown', { key: 'Enter' });
      await input.trigger('blur');
      expect(renameExperiment).toHaveBeenCalledTimes(1);
      const destinationId = other.backtest_id;
      await wrapper
        .get(`[data-testid="workspace-backtest-${destinationId}"]`)
        .trigger('click');
      await flushPromises();
      const destinationHeading = '.backtest-header';
      const displayedName = 'Other';
      const button = () =>
        wrapper.get(
          `${destinationHeading} button[aria-label^="Edit experiment name"]`,
        );
      expect(button().text()).toBe(displayedName);
      expect(wrapper.find(`${destinationHeading} input`).exists()).toBe(false);
      firstSave('First');
      await flushPromises();
      expect(renameExperiment).toHaveBeenCalledTimes(2);
      expect(renameExperiment).toHaveBeenLastCalledWith(
        sourceId,
        'Newer committed',
      );
      expect(wrapper.get(sourceRow).text()).toContain('Newer committed');
      expect(button().text()).toBe(displayedName);
      expect(wrapper.find(`${destinationHeading} input`).exists()).toBe(false);
      expect(
        wrapper
          .find(`${destinationHeading} .experiment-name [role="status"]`)
          .exists(),
      ).toBe(false);
      wrapper.unmount();
    },
  );
});
