import { useExecutionLogStore } from '@/stores/executionLogStore';
import {
  setupWorkspaceTests,
  run,
  backtest,
  mountWorkspace,
  routerMock,
  seedBacktest,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { NDataTable } from 'naive-ui';

import { describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestClosedTrades,
  getBacktest,
  getBacktestRun,
  listBacktestEvents,
  listBacktestMembers,
  listBacktests,
  listBacktestRuns,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';

describe('production Backtest Workspace: chart-navigation', () => {
  setupWorkspaceTests();

  it(
    'opens a backtest row directly on the chart while preserving ' +
      'selection and comparison',

    async () => {
      const executionLog = useExecutionLogStore();
      executionLog.selectRun(run('previous-log'));
      const members = [
        run('z-first', { backtest_id: 'direct', run_ordinal: 0 }),
        run('a-tenth', { backtest_id: 'direct', run_ordinal: 9 }),
        run('m-second', { backtest_id: 'direct', run_ordinal: 1 }),
      ];
      const accepted = backtest('direct', members.length);
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktests).mockResolvedValue([accepted]);
      vi.mocked(getBacktest).mockResolvedValue(accepted);
      vi.mocked(listBacktestEvents).mockResolvedValue([]);
      vi.mocked(listBacktestMembers).mockResolvedValue(members);
      vi.mocked(getBacktestRun).mockImplementation(async (id) =>
        members.find((member) => member.run_id === id)!,
      );
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-backtest-direct"]')
        .trigger('click');
      await flushPromises();
      const table = wrapper.get('[data-testid="workspace-current-backtest"]');
      const identities = () =>
        table.findAll('.run-identity').map((cell) => cell.find('span').text());
      expect(identities()).toEqual(['Run #1', 'Run #2', 'Run #10']);
      const dataTable = wrapper.findAllComponents(NDataTable).at(-1)!;
      dataTable.vm.sort('ordinal', 'descend');
      await flushPromises();
      expect(identities()).toEqual(['Run #10', 'Run #2', 'Run #1']);
      dataTable.vm.sort('ordinal', 'ascend');
      await flushPromises();
      expect(identities()).toEqual(['Run #1', 'Run #2', 'Run #10']);
      await wrapper
        .get('[data-testid="workspace-member-z-first"]')
        .trigger('click');
      await flushPromises();
      const chart = wrapper.get('[data-testid="workspace-chart-a-tenth"]');
      expect(chart.attributes('aria-label')).toBe('Open Run #10 on chart');
      await chart.trigger('keydown', { key: 'Enter' });
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('z-first');
      await chart.trigger('click');
      await flushPromises();
      expect(useBacktestOverlayStore().selectedRunId).toBe('a-tenth');
      expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('a-tenth');
      expect(routerMock.push).toHaveBeenCalledWith('/');
      expect(executionLog.selectedRun?.run_id).toBe('a-tenth');
      expect(executionLog.isOpen).toBe(false);
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('z-first');
      expect(
        wrapper.get<HTMLInputElement>(
          '[data-testid="comparison-select-z-first"]',
        ).element.checked,
      ).toBe(true);
      expect(
        wrapper.get<HTMLInputElement>(
          '[data-testid="comparison-select-a-tenth"]',
        ).element.checked,
      ).toBe(false);
      wrapper.unmount();
    },
  );
  it('retains the selected log when chart navigation fails', async () => {
    const member = run('next');
    seedBacktest([member]);
    vi.mocked(getBacktestRun).mockResolvedValue(member);
    routerMock.push.mockRejectedValue(new Error('Navigation unavailable'));
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-backtest-next"]')
      .trigger('click');
    await flushPromises();
    const log = useExecutionLogStore();
    log.selectRun(run('previous-log'));
    await wrapper.get('[data-testid="workspace-chart-next"]').trigger('click');
    await flushPromises();
    expect(log.selectedRun?.run_id).toBe('previous-log');
    expect(log.isOpen).toBe(true);
    wrapper.unmount();
  });
});
