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

import type { BacktestRun } from '@/types/backtesterContracts';

describe('production Backtest Workspace: name-acknowledgements', () => {
  setupWorkspaceTests();
  it(
    'renames a batch in detail and updates history search while ' +
      'members remain uneditable',
    async () => {
      vi.useFakeTimers();
      const accepted = { ...batch('rename-batch', 1), name: null };
      const memberRun = run('rename-member', {
        batch_id: accepted.batch_id,
        member_ordinal: 0,
      });
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
      vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
      vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
      vi.mocked(listBacktestBatchMembers).mockResolvedValue([memberRun]);
      vi.mocked(getBacktestRun).mockResolvedValue(memberRun);
      vi.mocked(renameExperiment).mockResolvedValue('Named sweep');
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-batch-rename-batch"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .get('.sweep-header button[aria-label^="Edit experiment name"]')
        .trigger('click');
      const input = wrapper.get<HTMLInputElement>(
        '.sweep-header input[aria-label="Experiment name"]',
      );
      expect(input.element.value).toBe('');
      await input.setValue('Named sweep');
      await input.trigger('blur');
      await flushPromises();
      expect(renameExperiment).toHaveBeenCalledWith(
        'batch',
        accepted.batch_id,
        'Named sweep',
      );
      await vi.advanceTimersByTimeAsync(5000);
      await flushPromises();
      expect(
        wrapper
          .get('.sweep-header button[aria-label^="Edit experiment name"]')
          .text(),
      ).toBe('Named sweep');
      await wrapper
        .get('[data-testid="workspace-search"] input')
        .setValue('Named sweep');
      expect(
        wrapper.get('[data-testid="workspace-batch-rename-batch"]').text(),
      ).toContain('Named sweep');
      expect(
        wrapper.findAll('button[aria-label^="Edit experiment name"]'),
      ).toHaveLength(1);
      wrapper.unmount();
    },
  );

  it('protects an acknowledged rename from a history read started before saving', async () => {
    vi.useFakeTimers();
    const original = run('late-read', { name: 'Before' });
    vi.mocked(listBacktestRuns).mockResolvedValue([original]);
    vi.mocked(getBacktestRun).mockResolvedValue(original);
    vi.mocked(renameExperiment).mockResolvedValue('After');
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-run-late-read"]')
      .trigger('click');
    await flushPromises();
    let finishRead!: (runs: BacktestRun[]) => void;
    vi.mocked(listBacktestRuns).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishRead = resolve;
        }),
    );
    await vi.advanceTimersByTimeAsync(5000);
    await wrapper
      .get('.run-heading button[aria-label^="Edit experiment name"]')
      .trigger('click');
    const input = wrapper.get(
      '.run-heading input[aria-label="Experiment name"]',
    );
    await input.setValue('After');
    await input.trigger('keydown', { key: 'Enter' });
    await flushPromises();
    finishRead([original]);
    await flushPromises();
    expect(
      wrapper
        .get('.run-heading button[aria-label^="Edit experiment name"]')
        .text(),
    ).toBe('After');
    expect(
      wrapper.get('[data-testid="workspace-run-late-read"]').text(),
    ).toContain('After');
    wrapper.unmount();
  });

  it('serializes a new edit after cancelling a pending save for the same experiment', async () => {
    vi.useFakeTimers();
    const original = run('queued-name', { name: 'Original' });
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
      .mockResolvedValueOnce('Second edit');
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-run-queued-name"]')
      .trigger('click');
    await flushPromises();
    const button = () =>
      wrapper.get('.run-heading button[aria-label^="Edit experiment name"]');
    const input = () =>
      wrapper.get<HTMLInputElement>(
        '.run-heading input[aria-label="Experiment name"]',
      );
    await button().trigger('click');
    await input().setValue('First edit');
    await input().trigger('keydown', { key: 'Enter' });
    await input().trigger('keydown', { key: 'Escape' });
    await button().trigger('click');
    await input().setValue('Second edit');
    await input().trigger('keydown', { key: 'Enter' });
    expect(renameExperiment).toHaveBeenCalledTimes(1);
    firstSave('First edit');
    await flushPromises();
    expect(renameExperiment).toHaveBeenCalledTimes(2);
    expect(renameExperiment).toHaveBeenLastCalledWith(
      'run',
      'queued-name',
      'Second edit',
    );
    expect(button().text()).toBe('Second edit');
    expect(
      wrapper.get('[data-testid="workspace-run-queued-name"]').text(),
    ).toContain('Second edit');
    wrapper.unmount();
  });

  it(
    'retains a successful predecessor name when its cancelled session ' +
      'has a failed successor',

    async () => {
      vi.useFakeTimers();
      const original = run('failed-successor', { name: 'Original' });
      vi.mocked(listBacktestRuns).mockResolvedValue([original]);
      vi.mocked(getBacktestRun).mockResolvedValue(original);
      let firstSave!: (name: string | null) => void;
      vi.mocked(renameExperiment)
        .mockResolvedValueOnce('Last acknowledged')
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              firstSave = resolve;
            }),
        )
        .mockRejectedValueOnce(new Error('Successor failed'));
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-run-failed-successor"]')
        .trigger('click');
      await flushPromises();
      const button = () =>
        wrapper.get('.run-heading button[aria-label^="Edit experiment name"]');
      const input = () =>
        wrapper.get<HTMLInputElement>(
          '.run-heading input[aria-label="Experiment name"]',
        );
      await button().trigger('click');
      await input().setValue('Last acknowledged');
      await input().trigger('keydown', { key: 'Enter' });
      await flushPromises();
      await button().trigger('click');
      await input().setValue('Persisted predecessor');
      await input().trigger('keydown', { key: 'Enter' });
      await input().trigger('keydown', { key: 'Escape' });
      await button().trigger('click');
      await input().setValue('Failed successor draft');
      await input().trigger('keydown', { key: 'Enter' });
      expect(renameExperiment).toHaveBeenCalledTimes(2);
      firstSave('Persisted predecessor');
      await flushPromises();
      expect(renameExperiment).toHaveBeenCalledTimes(3);
      expect(input().element.value).toBe('Failed successor draft');
      expect(wrapper.get('.run-heading [role="alert"]').text()).toBe(
        'Successor failed',
      );
      const persisted = { ...original, name: 'Persisted predecessor' };
      vi.mocked(listBacktestRuns).mockResolvedValue([persisted]);
      vi.mocked(getBacktestRun).mockResolvedValue(persisted);
      await vi.advanceTimersByTimeAsync(10000);
      await flushPromises();
      expect(input().element.value).toBe('Failed successor draft');
      expect(wrapper.get('.run-heading [role="alert"]').text()).toBe(
        'Successor failed',
      );
      expect(
        wrapper.get('[data-testid="workspace-run-failed-successor"]').text(),
      ).toContain('Persisted predecessor');
      await input().trigger('keydown', { key: 'Escape' });
      expect(button().text()).toBe('Persisted predecessor');
      await wrapper
        .get('[data-testid="workspace-search"] input')
        .setValue('Persisted predecessor');
      expect(
        wrapper.find('[data-testid="workspace-run-failed-successor"]').exists(),
      ).toBe(true);
      wrapper.unmount();
    },
  );
});
