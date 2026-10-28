import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { NCheckbox, NPagination } from 'naive-ui';

import { describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestEquityCurve,
  getBacktestBatch,
  getBacktestRun,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: comparison-selection', () => {
  setupWorkspaceTests();
  it('selects all eligible runs and shows partial selection in the header checkbox', async () => {
    const members = [
      run('first', { batch_id: 'selection', member_ordinal: 0 }),
      run('second', { batch_id: 'selection', member_ordinal: 1 }),
      run('failed', {
        batch_id: 'selection',
        member_ordinal: 2,
        status: 'failed',
        metrics: null,
      }),
    ];
    const accepted = batch('selection', members.length);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue(members);
    vi.mocked(getBacktestRun).mockImplementation(
      async (id) => members.find((member) => member.run_id === id)!,
    );
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-batch-selection"]')
      .trigger('click');
    await flushPromises();
    const header = () =>
      wrapper
        .findAllComponents(NCheckbox)
        .find(
          (checkbox) =>
            checkbox.attributes('data-testid') === 'comparison-select-all',
        )!;

    header().vm.$emit('update:checked', false);
    await flushPromises();
    expect(header().props('checked')).toBe(false);
    expect(header().props('indeterminate')).toBe(false);
    await wrapper.get('[data-testid="comparison-select-first"]').setValue(true);
    expect(header().props('indeterminate')).toBe(true);

    header().vm.$emit('update:checked', true);
    await flushPromises();
    expect(header().props('checked')).toBe(true);
    expect(header().props('indeterminate')).toBe(false);
    expect(
      wrapper.get<HTMLInputElement>('[data-testid="comparison-select-second"]')
        .element.checked,
    ).toBe(true);
    expect(
      wrapper.get<HTMLInputElement>('[data-testid="comparison-select-failed"]')
        .element.checked,
    ).toBe(false);
    expect(fetchBacktestEquityCurve).not.toHaveBeenCalledWith('failed');

    header().vm.$emit('update:checked', false);
    await flushPromises();
    expect(
      wrapper.get<HTMLInputElement>('[data-testid="comparison-select-first"]')
        .element.checked,
    ).toBe(false);
    expect(
      wrapper.get<HTMLInputElement>('[data-testid="comparison-select-second"]')
        .element.checked,
    ).toBe(false);
    wrapper.unmount();
  });

  it(
    'selects and deselects only successful page members while ' +
      'retaining off-page comparisons',

    async () => {
      const members = Array.from({ length: 25 }, (_, ordinal) =>
        run(`page-selection-${ordinal}`, {
          batch_id: 'page-selection',
          member_ordinal: ordinal,
          status: ordinal === 24 ? 'failed' : 'succeeded',
        }),
      );
      const accepted = batch('page-selection', members.length);
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
      vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
      vi.mocked(listBacktestBatchMembers).mockResolvedValue(members);
      vi.mocked(getBacktestRun).mockImplementation(
        async (id) => members.find((member) => member.run_id === id)!,
      );
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-batch-page-selection"]')
        .trigger('click');
      await flushPromises();
      const header = () =>
        wrapper
          .findAllComponents(NCheckbox)
          .find(
            (checkbox) =>
              checkbox.attributes('data-testid') === 'comparison-select-all',
          )!;
      const pagination = () => wrapper.findAllComponents(NPagination).at(-1)!;
      header().vm.$emit('update:checked', true);
      await flushPromises();
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(20);
      expect(fetchBacktestEquityCurve).not.toHaveBeenCalledWith(
        'page-selection-20',
      );
      pagination().vm.$emit('update:page', 2);
      await flushPromises();
      expect(header().props('checked')).toBe(false);
      expect(header().props('indeterminate')).toBe(false);
      await wrapper
        .get('[data-testid="comparison-select-page-selection-20"]')
        .setValue(true);
      await flushPromises();
      expect(header().props('indeterminate')).toBe(true);
      header().vm.$emit('update:checked', true);
      await flushPromises();
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(24);
      expect(fetchBacktestEquityCurve).not.toHaveBeenCalledWith(
        'page-selection-24',
      );
      expect(header().props('checked')).toBe(true);
      header().vm.$emit('update:checked', false);
      await flushPromises();
      expect(header().props('checked')).toBe(false);
      pagination().vm.$emit('update:page', 1);
      await flushPromises();
      expect(header().props('checked')).toBe(true);
      expect(
        wrapper.get<HTMLInputElement>(
          '[data-testid="comparison-select-page-selection-0"]',
        ).element.checked,
      ).toBe(true);
      header().vm.$emit('update:checked', false);
      await flushPromises();
      expect(
        wrapper.findComponent({ name: 'EquityReplayCharts' }).exists(),
      ).toBe(false);
      wrapper.unmount();
    },
  );
});
