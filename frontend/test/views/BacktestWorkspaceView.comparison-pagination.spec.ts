import {
  setupWorkspaceTests,
  run,
  backtest,
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
  getBacktest,
  listBacktestMembers,
  listBacktests,
  listBacktestRuns,
} from '@/api/backtesterClient';

// Row actions have separate interaction suites; pagination needs the real table,
// but not hundreds of tooltip/button instances on its largest pages.
vi.mock('@/views/workspace/comparison/comparisonRunActions', () => ({
  createComparisonRunActions: () => () => null,
}));

async function openPagedBacktest() {
  vi.useFakeTimers();
  const members = Array.from({ length: 105 }, (_, ordinal) =>
    run(`paged-${ordinal}`, { backtest_id: 'paged', run_ordinal: ordinal }),
  );
  const accepted = backtest('paged', members.length);
  vi.mocked(listBacktestRuns).mockResolvedValue([]);
  vi.mocked(listBacktests).mockResolvedValue([accepted]);
  vi.mocked(getBacktest).mockResolvedValue(accepted);
  vi.mocked(listBacktestMembers).mockResolvedValue(members);
  const wrapper = mountWorkspace(true);
  await flushPromises();
  await wrapper
    .get('[data-testid="workspace-backtest-paged"]')
    .trigger('click');
  await flushPromises();
  return {
    wrapper,
    members,
    pagination: () => wrapper.findAllComponents(NPagination).at(-1)!,
    identities: () =>
      wrapper
        .get('[data-testid="workspace-current-backtest"]')
        .findAll('.run-identity')
        .map((cell) => cell.find('span').text()),
  };
}

describe('production Backtest Workspace: comparison-pagination', () => {
  setupWorkspaceTests();

  it('changes page size through the menu with production typography', async () => {
    const { pagination, identities } = await openPagedBacktest();
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
    const style = document.createElement('style');
    style.textContent =
      readFileSync('src/assets/main.css', 'utf8') +
      selectSource.split('<style>')[1].split('</style>')[0];
    document.head.append(style);
    onTestFinished(() => style.remove());
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
  });

  it.each([20, 50, 100, Number.MAX_SAFE_INTEGER])(
    'preserves global sorting for page size %s and resets the page',
    async (size) => {
      const { wrapper, pagination, identities, members } =
        await openPagedBacktest();
      const memberReads = vi.mocked(listBacktestMembers).mock.calls.length;
      pagination().vm.$emit('update:page', 3);
      await flushPromises();
      expect(identities()[0]).toBe('Run #41');
      wrapper
        .findAllComponents(NDataTable)
        .at(-1)!
        .vm.sort('ordinal', 'descend');
      await flushPromises();
      pagination().vm.$emit('update:page', 3);
      await flushPromises();
      expect(identities()[0]).toBe('Run #65');
      pagination().vm.$emit('update:pageSize', size);
      await flushPromises();
      expect(identities()).toEqual(
        Array.from(
          { length: Math.min(size, members.length) },
          (_, index) => `Run #${members.length - index}`,
        ),
      );
      expect(pagination().props('page')).toBe(1);
      expect(pagination().exists()).toBe(true);
      expect(listBacktestMembers).toHaveBeenCalledTimes(memberReads);
      expect(fetchBacktestEquityCurve).not.toHaveBeenCalled();
    },
  );

  it('sorts globally and clamps the page when members shrink', async () => {
    const { wrapper, pagination, identities, members } =
      await openPagedBacktest();
    const memberReads = vi.mocked(listBacktestMembers).mock.calls.length;
    pagination().vm.$emit('update:page', 3);
    await flushPromises();
    wrapper.findAllComponents(NDataTable).at(-1)!.vm.sort('ordinal', 'descend');
    await flushPromises();
    expect(pagination().props('page')).toBe(1);
    expect(identities()).toEqual(
      Array.from({ length: 20 }, (_, index) => `Run #${105 - index}`),
    );
    pagination().vm.$emit('update:page', 6);
    await flushPromises();
    expect(identities()).toHaveLength(5);
    wrapper
      .findComponent({ name: 'BacktestOverview' })
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
    expect(listBacktestMembers).toHaveBeenCalledTimes(memberReads);
    expect(fetchBacktestEquityCurve).not.toHaveBeenCalled();
  });
});
