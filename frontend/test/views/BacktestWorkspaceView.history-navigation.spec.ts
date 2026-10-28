import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
  toggleAnalysisColumns,
  pinia,
  routerMock,
} from './backtestWorkspaceFixtures';
import { flushPromises, mount } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  getBacktestRun,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';

import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';

describe('production Backtest Workspace: history-navigation', () => {
  setupWorkspaceTests();
  it('shows real saved history, selects one run, and retains signed metric semantics', async () => {
    const success = run('success', {
      name: 'Baseline',
    });
    const failed = run('failed', {
      status: 'failed',
      metrics: null,
      error_message: 'No candles',
    });
    vi.mocked(listBacktestRuns).mockResolvedValue([success, failed]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);

    const wrapper = mountWorkspace();
    await flushPromises();

    expect(wrapper.find('[data-testid="workspace-history"]').text()).toContain(
      'Baseline',
    );
    expect(wrapper.find('[data-testid="workspace-history"]').text()).toContain(
      'failed',
    );
    expect(wrapper.text()).toContain('Version unavailable');

    await wrapper
      .find('[data-testid="workspace-run-success"]')
      .trigger('click');
    await flushPromises();

    const current = wrapper.find('[data-testid="workspace-current-backtest"]');
    expect(current.text()).toContain('-1.25%');
    expect(current.text()).toContain('2.5%');
    await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
    await flushPromises();
    const groups = [...document.querySelectorAll('.column-group')];
    expect(groups.map((group) => group.getAttribute('aria-label'))).toEqual([
      'Run settings',
      'Performance',
      'Long / short',
    ]);
    expect(
      groups.reduce(
        (count, group) =>
          count +
          group.querySelectorAll('.column-options [role="checkbox"]').length,
        0,
      ),
    ).toBe(22);
    expect(wrapper.findAll('.comparison-controls button')).toHaveLength(1);
    await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
    await flushPromises();
    await toggleAnalysisColumns(wrapper, [
      'long-win',
      'short-win',
      'long-pnl',
      'short-pnl',
    ]);
    expect(
      wrapper.find('[data-testid="workspace-current-backtest"]').text(),
    ).toContain('No trades');
    await toggleAnalysisColumns(wrapper, [
      'long-win',
      'short-win',
      'long-pnl',
      'short-pnl',
    ]);
    expect(current.text()).toContain('10000');
    expect(
      wrapper
        .find('[data-testid="workspace-current-backtest"]')
        .findAll('td')
        .map((column) => column.text()),
    ).toContain('—');
    expect(wrapper.text()).toContain('Saved request and execution settings');
    wrapper.unmount();
  });

  it('opens the real creation workflow from the primary header action', async () => {
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    const wrapper = mount(BacktestWorkspaceView, {
      global: {
        plugins: [pinia],
        stubs: {
          BacktestCreationDrawer: true,
          BacktestBatches: true,
          EquityReplayCharts: true,
        },
      },
    });
    await flushPromises();
    expect(wrapper.getComponent(BacktestCreationDrawer).props('show')).toBe(
      false,
    );
    await wrapper.get('[data-testid="workspace-create"]').trigger('click');
    expect(wrapper.getComponent(BacktestCreationDrawer).props('show')).toBe(
      true,
    );
    wrapper.unmount();
  });

  it('opens a separate analysis page and restores history filters on return', async () => {
    const saved = run('navigation');
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    vi.mocked(getBacktestRun).mockResolvedValue(saved);
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(
      wrapper.get('[aria-label="Current Backtest"]').attributes('style'),
    ).toContain('display: none');
    await wrapper
      .get('[data-testid="workspace-search"] input')
      .setValue('navigation');
    await wrapper
      .get('[data-testid="workspace-run-navigation"]')
      .trigger('click');
    await flushPromises();
    expect(routerMock.push).toHaveBeenCalledWith('/backtests/run/navigation');
    expect(
      wrapper.get('[aria-label="Saved Backtest Runs"]').attributes('style'),
    ).toContain('display: none');
    expect(
      wrapper.get('[aria-label="Current Backtest"]').attributes('style') ?? '',
    ).not.toContain('display: none');
    await wrapper
      .get('[data-testid="workspace-history-return"]')
      .trigger('click');
    expect(
      wrapper.get('[aria-label="Saved Backtest Runs"]').attributes('style') ??
        '',
    ).not.toContain('display: none');
    expect(
      wrapper.get<HTMLInputElement>('[data-testid="workspace-search"] input')
        .element.value,
    ).toBe('navigation');
    wrapper.unmount();
  });

  it.each([
    [null, ''],
    ['Baseline', 'Baseline (copy)'],
  ] as const)(
    'opens Create from this for standalone name %s without changing the source or selection',
    async (name, proposed) => {
      const saved = run('source', { name });
      const original = structuredClone(saved);
      vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-run-source"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-create-from-source"]')
        .trigger('click');
      await flushPromises();
      expect(useBacktestWorkspaceStore().reuseSource).toMatchObject({
        kind: 'run',
        id: 'source',
        strategyVersion: null,
      });
      expect(
        useBacktestWorkspaceStore().creationDraft?.strategy.strategy_id,
      ).toBe('sma');
      expect(useBacktestWorkspaceStore().creationDraft?.name).toBe(proposed);
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('source');
      expect(saved).toEqual(original);
      wrapper.unmount();
    },
  );

  it.each([
    [null, ''],
    ['Sweep baseline', 'Sweep baseline (copy)'],
  ] as const)(
    'opens Create from this for batch name %s without changing saved history',
    async (name, proposed) => {
      const saved = { ...batch('source-batch', 1), name };
      saved.accepted_definition.shared_request = JSON.parse(
        JSON.stringify(run('settings').request),
      );
      const original = structuredClone(saved);
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktestBatches).mockResolvedValue([saved]);
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-create-from-source-batch"]')
        .trigger('click');
      await flushPromises();
      expect(useBacktestWorkspaceStore().reuseSource).toMatchObject({
        kind: 'batch',
        id: 'source-batch',
      });
      expect(useBacktestWorkspaceStore().creationDraft?.name).toBe(proposed);
      expect(useBacktestWorkspaceStore().creationSweepDraft?.isSweep).toBe(
        true,
      );
      expect(saved).toEqual(original);
      wrapper.unmount();
    },
  );
});
