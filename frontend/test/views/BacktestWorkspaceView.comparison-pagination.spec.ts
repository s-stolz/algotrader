import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { NDataTable, NPagination } from 'naive-ui';

import { describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestEquityCurve,
  getBacktestBatch,
  listBacktestBatchMembers,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: comparison-pagination', () => {
  setupWorkspaceTests();
  it(
    'paginates all fetched members with global sorting, page sizes, ' +
      'and an All option',
    async () => {
      vi.useFakeTimers();
      const members = Array.from({ length: 105 }, (_, ordinal) =>
        run(`paged-${ordinal}`, { batch_id: 'paged', member_ordinal: ordinal }),
      );
      const accepted = batch('paged', members.length);
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
      vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
      vi.mocked(listBacktestBatchMembers).mockResolvedValue(members);
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-batch-paged"]')
        .trigger('click');
      await flushPromises();
      const table = () =>
        wrapper.get('[data-testid="workspace-current-backtest"]');
      const pagination = () => wrapper.findAllComponents(NPagination).at(-1)!;
      const identities = () =>
        table()
          .findAll('.run-identity')
          .map((cell) => cell.find('span').text());
      expect(identities()).toEqual(
        Array.from({ length: 20 }, (_, index) => `Run #${index + 1}`),
      );
      expect(pagination().props('pageSize')).toBe(20);
      expect(pagination().props('pageSizes')).toEqual([
        { label: '20 rows', value: 20 },
        { label: '50 rows', value: 50 },
        { label: '100 rows', value: 100 },
        { label: 'All rows', value: Number.MAX_SAFE_INTEGER },
      ]);
      const memberReads = vi.mocked(listBacktestBatchMembers).mock.calls.length;
      pagination().vm.$emit('update:page', 3);
      await flushPromises();
      expect(identities()[0]).toBe('Run #41');
      wrapper
        .findAllComponents(NDataTable)
        .at(-1)!
        .vm.sort('ordinal', 'descend');
      await flushPromises();
      expect(pagination().props('page')).toBe(1);
      expect(identities()).toEqual(
        Array.from({ length: 20 }, (_, index) => `Run #${105 - index}`),
      );
      for (const size of [50, 100, Number.MAX_SAFE_INTEGER, 20]) {
        pagination().vm.$emit('update:pageSize', size);
        await flushPromises();
        expect(identities()).toHaveLength(Math.min(size, members.length));
        expect(pagination().props('page')).toBe(1);
        expect(pagination().exists()).toBe(true);
      }
      expect(listBacktestBatchMembers).toHaveBeenCalledTimes(memberReads);
      expect(fetchBacktestEquityCurve).not.toHaveBeenCalled();
      pagination().vm.$emit('update:page', 6);
      await flushPromises();
      expect(identities()).toHaveLength(5);
      wrapper
        .findComponent({ name: 'BacktestBatches' })
        .vm.$emit('members', 'paged', members.slice(0, 25));
      await flushPromises();
      expect(pagination().props('page')).toBe(2);
      expect(identities()).toEqual([
        'Run #5',
        'Run #4',
        'Run #3',
        'Run #2',
        'Run #1',
      ]);
      wrapper.unmount();
    },
  );
});
