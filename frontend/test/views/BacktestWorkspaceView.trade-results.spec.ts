import {
  setupWorkspaceTests,
  run,
  trade,
  seedBacktest,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, it, expect, vi } from 'vitest';
import { fetchBacktestClosedTrades } from '@/api/backtesterClient';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
describe('Run statistics in the production comparison table', () => {
  setupWorkspaceTests();
  it('renders and sorts saved profit factor while unrelated trades remain pending', async () => {
    const members = [run('null'), run('zero'), run('finite'), run('infinite')];
    [null, 0, 2.5, 'infinity'].forEach((value, i) => {
      members[i].metrics = {
        profit_factor: value as number | 'infinity' | null,
      };
    });
    seedBacktest(members);
    vi.mocked(fetchBacktestClosedTrades).mockImplementation(
      () => new Promise(() => {}),
    );
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-backtest-null"]')
      .trigger('click');
    await flushPromises();
    const table = wrapper
      .findAllComponents(BaseDataTable)
      .find(
        (t) => t.attributes('data-testid') === 'workspace-current-backtest',
      )!;
    expect(table.text()).toContain('∞');
    expect(table.text()).toContain('2.50');
    table.vm.$emit('update:sorter', {
      columnKey: 'profit-factor',
      order: 'descend',
    });
    await flushPromises();
    expect(
      (table.props('data') as { run_id: string }[]).map((row) => row.run_id),
    ).toEqual(['infinite', 'finite', 'zero', 'null']);
  });
  it('loads metrics before comparison selection and sorts all runs by raw values', async () => {
    const members = [run('low'), run('high'), run('middle')];
    seedBacktest(members);
    vi.mocked(fetchBacktestClosedTrades).mockImplementation(async (id) => [
      {
        ...trade(0, 'long', 'signal'),
        realized_pnl: { low: 2.001, high: 20, middle: 2.004 }[id]!,
      },
    ]);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-backtest-low"]')
      .trigger('click');
    await flushPromises();
    for (const member of members)
      expect(fetchBacktestClosedTrades).toHaveBeenCalledWith(member.run_id);
    const table = wrapper
      .findAllComponents(BaseDataTable)
      .find(
        (t) => t.attributes('data-testid') === 'workspace-current-backtest',
      )!;
    expect(table.text()).toContain('Net realized profit');
    table.vm.$emit('update:sorter', {
      columnKey: 'net-profit',
      order: 'descend',
    });
    await flushPromises();
    expect(
      (table.props('data') as { run_id: string }[]).map((row) => row.run_id),
    ).toEqual(['high', 'middle', 'low']);
    table.vm.$emit('update:sorter', {
      columnKey: 'net-profit',
      order: 'ascend',
    });
    await flushPromises();
    expect(
      (table.props('data') as { run_id: string }[]).map((row) => row.run_id),
    ).toEqual(['low', 'middle', 'high']);
    await wrapper
      .get('[data-testid="comparison-select-middle"]')
      .setValue(true);
    await flushPromises();
    expect(
      wrapper.find('[aria-label="Monthly and yearly results"]').exists(),
    ).toBe(true);
    expect(wrapper.text()).not.toContain('synthetic');
    expect(wrapper.text()).not.toContain('Trade statistics');
  });
});
