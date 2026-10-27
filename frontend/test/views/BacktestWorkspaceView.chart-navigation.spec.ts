import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
  routerMock,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { NDataTable } from 'naive-ui';

import { describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestClosedTrades,
  getBacktestBatch,
  getBacktestRun,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';

import type { BacktestRun } from '@/types/backtesterContracts';

describe('production Backtest Workspace: chart-navigation', () => {
  setupWorkspaceTests();
  it('hands eligible saved runs to the chart overlay and returns to the chart', async () => {
    const success = run('success');
    vi.mocked(listBacktestRuns).mockResolvedValue([success]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    routerMock.push.mockResolvedValue(undefined);

    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-run-success"]')
      .trigger('click');
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-open-chart"]').exists()).toBe(
      false,
    );
    await wrapper
      .find('[data-testid="workspace-chart-success"]')
      .trigger('click');
    await flushPromises();

    expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('success');
    expect(routerMock.push).toHaveBeenCalledWith('/');
    wrapper.unmount();
  });

  it(
    'opens a batch row directly on the chart while preserving ' +
      'selection and comparison',

    async () => {
      const members = [
        run('z-first', { batch_id: 'direct', member_ordinal: 0 }),
        run('a-tenth', { batch_id: 'direct', member_ordinal: 9 }),
        run('m-second', { batch_id: 'direct', member_ordinal: 1 }),
      ];
      const accepted = batch('direct', members.length);
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
        .get('[data-testid="workspace-batch-direct"]')
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

  it.each([
    ['unfinished', { status: 'running', metrics: null }],
    ['no-symbol', { request: { ...run('base').request, symbols: [] } }],
    [
      'multi-symbol',
      { request: { ...run('base').request, symbols: ['EURUSD', 'GBPUSD'] } },
    ],
    [
      'missing-market',
      { request: { ...run('base').request, symbols: ['GBPUSD'] } },
    ],
  ] as [string, Partial<BacktestRun>][])(
    'disables the chart action for %s runs',
    async (id, overrides) => {
      const saved = run(id, overrides);
      vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
      vi.mocked(getBacktestRun).mockResolvedValue(saved);
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper.get(`[data-testid="workspace-run-${id}"]`).trigger('click');
      await flushPromises();
      expect(
        wrapper
          .get(`[data-testid="workspace-chart-${id}"]`)
          .attributes('disabled'),
      ).toBeDefined();
      if (saved.status === 'succeeded') {
        expect(
          wrapper
            .get(`[data-testid="workspace-log-${id}"]`)
            .attributes('disabled'),
        ).toBeUndefined();
      } else {
        expect(
          wrapper
            .get(`[data-testid="workspace-log-${id}"]`)
            .attributes('disabled'),
        ).toBeDefined();
      }
      expect(routerMock.push).not.toHaveBeenCalledWith('/');
      wrapper.unmount();
    },
  );

  it(
    'prevents repeated chart opens during loading and allows retry ' +
      'after a failed read',

    async () => {
      const saved = run('retry');
      vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
      vi.mocked(getBacktestRun).mockResolvedValue(saved);
      let rejectRead!: (reason: Error) => void;
      vi.mocked(fetchBacktestClosedTrades).mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectRead = reject;
          }),
      );
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper.get('[data-testid="workspace-run-retry"]').trigger('click');
      await flushPromises();
      const chart = wrapper.get('[data-testid="workspace-chart-retry"]');
      await chart.trigger('click');
      expect(chart.attributes('disabled')).toBeDefined();
      await chart.trigger('click');
      expect(fetchBacktestClosedTrades).toHaveBeenCalledTimes(1);
      rejectRead(new Error('Trades unavailable'));
      await flushPromises();
      expect(wrapper.text()).toContain('Trades unavailable');
      expect(routerMock.push).not.toHaveBeenCalledWith('/');
      expect(chart.attributes('disabled')).toBeUndefined();
      await chart.trigger('click');
      await flushPromises();
      expect(routerMock.push).toHaveBeenCalledWith('/');
      wrapper.unmount();
    },
  );

  it(
    'keeps an unsupported result inspectable with an explanation ' +
      'instead of chart navigation',

    async () => {
      const legacy = run('legacy', { result_schema_version: 2 });
      vi.mocked(listBacktestRuns).mockResolvedValue([legacy]);
      vi.mocked(getBacktestRun).mockResolvedValue(legacy);
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-run-legacy"]')
        .trigger('click');
      await flushPromises();

      expect(
        wrapper.find('[data-testid="workspace-current-backtest"]').text(),
      ).toContain('-1.25%');
      expect(
        wrapper
          .find('[data-testid="workspace-chart-legacy"]')
          .attributes('disabled'),
      ).toBeDefined();
      await wrapper
        .find('[data-testid="workspace-chart-legacy"]')
        .element.parentElement?.dispatchEvent(new MouseEvent('mouseenter'));
      await vi.waitFor(() =>
        expect(document.body.textContent).toContain(
          'Backtest Run result schema is unsupported.',
        ),
      );
      expect(routerMock.push).not.toHaveBeenCalledWith('/');
      wrapper.unmount();
    },
  );
});
