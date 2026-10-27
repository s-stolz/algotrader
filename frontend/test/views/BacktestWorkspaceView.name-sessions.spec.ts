import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  renameExperiment,
  getBacktestBatch,
  getBacktestRun,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: name-sessions', () => {
  setupWorkspaceTests();
  it.each(['Enter', 'blur'])(
    'saves a newer explicit %s gesture while an earlier rename is pending',
    async (gesture) => {
      vi.useFakeTimers();
      const original = run('pending-gesture', { name: 'Original' });
      vi.mocked(listBacktestRuns).mockResolvedValue([original]);
      vi.mocked(getBacktestRun).mockResolvedValue(original);
      let firstSave!: (name: string | null) => void;
      vi.mocked(renameExperiment)
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              firstSave = resolve;
            }),
        )
        .mockResolvedValueOnce('Newer');
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-run-pending-gesture"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .get('.run-heading button[aria-label^="Edit experiment name"]')
        .trigger('click');
      const input = () =>
        wrapper.get<HTMLInputElement>(
          '.run-heading input[aria-label="Experiment name"]',
        );
      await input().setValue('First');
      await input().trigger('keydown', { key: 'Enter' });
      await input().setValue('Newer');
      if (gesture === 'Enter')
        await input().trigger('keydown', { key: 'Enter' });
      await input().trigger('blur');
      await input().setValue('Uncommitted draft');
      expect(renameExperiment).toHaveBeenCalledTimes(1);
      firstSave('First');
      await flushPromises();
      expect(renameExperiment).toHaveBeenCalledTimes(2);
      expect(renameExperiment).toHaveBeenLastCalledWith(
        'run',
        original.run_id,
        'Newer',
      );
      expect(
        wrapper.get('[data-testid="workspace-run-pending-gesture"]').text(),
      ).toContain('Newer');
      expect(input().element.value).toBe('Uncommitted draft');
      wrapper.unmount();
    },
  );

  it.each([
    ['run', 'Enter', 'run'],
    ['run', 'blur', 'run'],
    ['run', 'Enter', 'batch'],
    ['batch', 'blur', 'run'],
  ] as const)(
    'persists a newer committed %s name after %s and navigation to %s detail',
    async (kind, gesture, destination) => {
      vi.useFakeTimers();
      const original = run('departed-run', { name: 'Original run' });
      const other = run('other-run', { name: 'Other run' });
      const sweep = { ...batch('departed-batch', 1), name: 'Original sweep' };
      vi.mocked(listBacktestRuns).mockResolvedValue([original, other]);
      vi.mocked(getBacktestRun).mockImplementation(async (id) =>
        id === original.run_id ? original : other,
      );
      vi.mocked(listBacktestBatches).mockResolvedValue([sweep]);
      vi.mocked(getBacktestBatch).mockResolvedValue(sweep);
      vi.mocked(listBacktestBatchMembers).mockResolvedValue([]);
      vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
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
      const sourceId = kind === 'run' ? original.run_id : sweep.batch_id;
      const sourceRow = `[data-testid="workspace-${kind}-${sourceId}"]`;
      await wrapper.get(sourceRow).trigger('click');
      await flushPromises();
      const sourceHeading = kind === 'run' ? '.run-heading' : '.sweep-header';
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
      const destinationId =
        destination === 'run' ? other.run_id : sweep.batch_id;
      await wrapper
        .get(`[data-testid="workspace-${destination}-${destinationId}"]`)
        .trigger('click');
      await flushPromises();
      const destinationHeading =
        destination === 'run' ? '.run-heading' : '.sweep-header';
      const displayedName =
        destination === 'run' ? 'Other run' : 'Original sweep';
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
        kind,
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

  it('cancels a newer queued commit with Escape while an earlier rename is pending', async () => {
    vi.useFakeTimers();
    const original = run('cancel-gesture', { name: 'Original' });
    vi.mocked(listBacktestRuns).mockResolvedValue([original]);
    vi.mocked(getBacktestRun).mockResolvedValue(original);
    let firstSave!: (name: string | null) => void;
    vi.mocked(renameExperiment).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          firstSave = resolve;
        }),
    );
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-run-cancel-gesture"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .get('.run-heading button[aria-label^="Edit experiment name"]')
      .trigger('click');
    const input = wrapper.get(
      '.run-heading input[aria-label="Experiment name"]',
    );
    await input.setValue('First');
    await input.trigger('keydown', { key: 'Enter' });
    await input.setValue('Cancelled');
    await input.trigger('keydown', { key: 'Enter' });
    await input.trigger('keydown', { key: 'Escape' });
    await input.trigger('blur');
    firstSave('First');
    await flushPromises();
    expect(renameExperiment).toHaveBeenCalledTimes(1);
    expect(
      wrapper
        .get('.run-heading button[aria-label^="Edit experiment name"]')
        .text(),
    ).toBe('First');
    wrapper.unmount();
  });
});
