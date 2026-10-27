import {
  setupWorkspaceTests,
  run,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  renameExperiment,
  getBacktestRun,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: name-editing', () => {
  setupWorkspaceTests();
  it(
    'renames inline with keyboard activation, Enter/blur ' +
      'deduplication, Escape, clearing and validation',
    async () => {
      vi.useFakeTimers();
      const savedRun = run('rename', { name: 'Saved name' });
      vi.mocked(listBacktestRuns).mockResolvedValue([savedRun]);
      vi.mocked(getBacktestRun).mockResolvedValue(savedRun);
      vi.mocked(renameExperiment).mockImplementation(
        async (_kind, _id, name) => name,
      );
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-run-rename"]')
        .trigger('click');
      await flushPromises();
      const button = () =>
        wrapper.get('.run-heading button[aria-label^="Edit experiment name"]');
      const input = () =>
        wrapper.get<HTMLInputElement>(
          '.run-heading input[aria-label="Experiment name"]',
        );
      await button().trigger('keydown', { key: 'Enter' });
      expect(input().element.value).toBe('Saved name');
      await input().setValue('  New name  ');
      expect(renameExperiment).not.toHaveBeenCalled();
      const committedInput = input();
      await committedInput.trigger('keydown', { key: 'Enter' });
      await committedInput.trigger('blur');
      await flushPromises();
      expect(renameExperiment).toHaveBeenCalledTimes(1);
      expect(renameExperiment).toHaveBeenCalledWith(
        'run',
        'rename',
        'New name',
      );
      expect(button().text()).toBe('New name');
      expect(
        wrapper.get('[data-testid="workspace-run-rename"]').text(),
      ).toContain('New name');
      expect(wrapper.get('.run-heading [role="status"]').text()).toBe('Saved');
      await button().trigger('keydown', { key: ' ' });
      await input().setValue('cancelled draft');
      const cancelledInput = input();
      await cancelledInput.trigger('keydown', { key: 'Escape' });
      await cancelledInput.trigger('blur');
      expect(renameExperiment).toHaveBeenCalledTimes(1);
      expect(button().text()).toBe('New name');
      await button().trigger('click');
      await input().setValue('x'.repeat(121));
      await input().trigger('keydown', { key: 'Enter' });
      expect(wrapper.get('.run-heading [role="alert"]').text()).toContain(
        '120',
      );
      expect(input().element.value).toBe('x'.repeat(121));
      expect(renameExperiment).toHaveBeenCalledTimes(1);
      await input().setValue('');
      await input().trigger('blur');
      await flushPromises();
      expect(renameExperiment).toHaveBeenLastCalledWith('run', 'rename', null);
      expect(button().text()).toBe('Unnamed standalone run');
      await button().trigger('click');
      expect(input().element.value).toBe('');
      wrapper.unmount();
    },
  );

  it(
    'retains failed drafts for retry and preserves them and ' +
      'acknowledged names across polling',

    async () => {
      vi.useFakeTimers();
      const savedRun = run('retry', { name: 'Old name' });
      vi.mocked(listBacktestRuns).mockResolvedValue([savedRun]);
      vi.mocked(getBacktestRun).mockResolvedValue(savedRun);
      vi.mocked(renameExperiment)
        .mockRejectedValueOnce(new Error('Connection lost'))
        .mockResolvedValueOnce('Recovered name');
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper.get('[data-testid="workspace-run-retry"]').trigger('click');
      await flushPromises();
      await wrapper
        .get('.run-heading button[aria-label^="Edit experiment name"]')
        .trigger('click');
      const input = () =>
        wrapper.get<HTMLInputElement>(
          '.run-heading input[aria-label="Experiment name"]',
        );
      await input().setValue('Recovered name');
      await vi.advanceTimersByTimeAsync(5000);
      await flushPromises();
      expect(input().element.value).toBe('Recovered name');
      await input().trigger('keydown', { key: 'Enter' });
      await flushPromises();
      expect(input().element.value).toBe('Recovered name');
      expect(wrapper.get('.run-heading [role="alert"]').text()).toBe(
        'Connection lost',
      );
      await input().trigger('keydown', { key: 'Enter' });
      await flushPromises();
      expect(renameExperiment).toHaveBeenCalledTimes(2);
      await vi.advanceTimersByTimeAsync(5000);
      await flushPromises();
      expect(
        wrapper
          .get('.run-heading button[aria-label^="Edit experiment name"]')
          .text(),
      ).toBe('Recovered name');
      await wrapper
        .get('[data-testid="workspace-search"] input')
        .setValue('Recovered name');
      expect(wrapper.find('[data-testid="workspace-run-retry"]').exists()).toBe(
        true,
      );
      wrapper.unmount();
    },
  );

  it(
    'keeps changes made during a save and isolates responses after ' +
      'navigating to another experiment',

    async () => {
      vi.useFakeTimers();
      const first = run('first-rename', { name: 'First' });
      const second = run('second-rename', { name: 'Second' });
      vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
      vi.mocked(getBacktestRun).mockImplementation(async (id) =>
        id === first.run_id ? first : second,
      );
      let resolve!: (name: string | null) => void;
      vi.mocked(renameExperiment).mockImplementationOnce(
        () =>
          new Promise((done) => {
            resolve = done;
          }),
      );
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-run-first-rename"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .get('.run-heading button[aria-label^="Edit experiment name"]')
        .trigger('click');
      const input = () =>
        wrapper.get<HTMLInputElement>(
          '.run-heading input[aria-label="Experiment name"]',
        );
      await input().setValue('Submitted');
      await input().trigger('keydown', { key: 'Enter' });
      expect(wrapper.get('.run-heading [role="status"]').text()).toBe(
        'Saving…',
      );
      await input().setValue('Newer draft');
      resolve('Submitted');
      await flushPromises();
      expect(input().element.value).toBe('Newer draft');
      vi.mocked(renameExperiment).mockImplementationOnce(
        () =>
          new Promise((done) => {
            resolve = done;
          }),
      );
      await input().trigger('keydown', { key: 'Enter' });
      await wrapper
        .get('[data-testid="workspace-run-second-rename"]')
        .trigger('click');
      await flushPromises();
      resolve('Newer draft');
      await flushPromises();
      expect(
        wrapper
          .get('.run-heading button[aria-label^="Edit experiment name"]')
          .text(),
      ).toBe('Second');
      expect(wrapper.find('.run-heading input').exists()).toBe(false);
      expect(wrapper.find('.run-heading [role="status"]').exists()).toBe(false);
      expect(
        wrapper.get('[data-testid="workspace-run-first-rename"]').text(),
      ).toContain('Newer draft');
      wrapper.unmount();
    },
  );
});
