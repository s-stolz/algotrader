import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { NDataTable, NPagination } from 'naive-ui';
import { designTokens } from '@/design/tokens';
import { readFileSync } from 'node:fs';
import selectSource from '@/components/Common/BaseSelect.vue?raw';

import { describe, expect, it, onTestFinished, vi } from 'vitest';

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
      // Load production CSS: the legacy select class must not override this menu.
      const style = document.createElement('style');
      style.textContent =
        readFileSync('src/assets/main.css', 'utf8') +
        selectSource.split('<style>')[1].split('</style>')[0];
      document.head.append(style);
      onTestFinished(() => {
        style.remove();
        Reflect.deleteProperty(HTMLElement.prototype, 'scrollTo');
      });
      Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
        configurable: true,
        value: vi.fn(),
      });
      const picker = pagination().get('[tabindex="0"]');
      await picker.trigger('keydown', {
        key: 'ArrowDown',
        code: 'ArrowDown',
      });
      const menu = document.querySelector<HTMLElement>('.n-select-menu')!;
      expect(menu).not.toBeNull();
      expect(getComputedStyle(menu).fontFamily).toBe(designTokens.font.ui);
      expect(menu.style.getPropertyValue('--design-font-ui')).toBe(
        designTokens.font.ui,
      );
      const option = [
        ...menu.querySelectorAll<HTMLElement>('.n-base-select-option'),
      ].find((item) => item.textContent?.trim() === '50 rows')!;
      expect(getComputedStyle(option).fontFamily).toContain('Tektur');
      // jsdom retains var() in computed font sizes; inspect its mounted value.
      expect(menu.style.getPropertyValue('--n-option-font-size')).toBe(
        designTokens.text.body,
      );
      option.click();
      await flushPromises();
      expect(identities()).toHaveLength(50);
      expect(pagination().props('pageSize')).toBe(50);
      style.remove();
      Reflect.deleteProperty(HTMLElement.prototype, 'scrollTo');
      pagination().vm.$emit('update:pageSize', 20);
      await flushPromises();
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
