import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
  toggleAnalysisColumns,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { NDataTable, NSelect } from 'naive-ui';

import { describe, expect, it, vi } from 'vitest';

import {
  getBacktestRun,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: history-filters', () => {
  setupWorkspaceTests();
  it('shows tiny saved Return, drawdown, and account-unit PnL values', async () => {
    const success = run('tiny', {
      metrics: {
        total_return_pct: -0.004,
        max_drawdown_pct: -0.004,
        long_trade_count: 1,
        short_trade_count: 1,
        long_realized_pnl: -0.003,
        short_realized_pnl: 0.002,
      },
    });
    vi.mocked(listBacktestRuns).mockResolvedValue([success]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-tiny"]').trigger('click');
    await flushPromises();
    await toggleAnalysisColumns(wrapper, [
      'long-win',
      'short-win',
      'long-pnl',
      'short-pnl',
    ]);
    const pnlCells = wrapper
      .find('[data-testid="workspace-current-backtest"]')
      .findAll('td')
      .map((cell) => cell.text());
    expect(pnlCells).toContain('-0.003');
    expect(pnlCells).toContain('+0.002');
    await toggleAnalysisColumns(wrapper, [
      'long-win',
      'short-win',
      'long-pnl',
      'short-pnl',
    ]);

    const cells = wrapper
      .find('[data-testid="workspace-current-backtest"]')
      .findAll('td')
      .map((cell) => cell.text());
    expect(cells).toContain('-0.004%');
    expect(cells).toContain('0.004%');
    wrapper.unmount();
  });

  it(
    'displays saved names and unnamed fallbacks with UUIDs and ' +
      'searches and sorts the visible names',

    async () => {
      const named = run('alpha-run-full-uuid', { name: 'Alpha research' });
      const unnamed = run('void-run-full-uuid', {
        request: {
          ...run('x').request,
          run_metadata: {
            name: 'Ignored legacy name',
            label: 'Ignored legacy label',
          },
        },
      });
      const namedSweep = {
        ...batch('beta-batch-full-uuid', 1),
        name: 'Beta research',
      };
      const unnamedSweep = batch('empty-batch-full-uuid', 1);
      vi.mocked(listBacktestRuns).mockResolvedValue([named, unnamed]);
      vi.mocked(listBacktestBatches).mockResolvedValue([
        namedSweep,
        unnamedSweep,
      ]);
      vi.mocked(getBacktestRun).mockImplementation(async (id) =>
        id === named.run_id ? named : unnamed,
      );
      const wrapper = mountWorkspace();
      await flushPromises();
      const history = () => wrapper.get('[data-testid="workspace-history"]');
      for (const [kind, id, label] of [
        ['run', named.run_id, 'Alpha research'],
        ['run', unnamed.run_id, 'Unnamed standalone run'],
        ['batch', namedSweep.batch_id, 'Beta research'],
        ['batch', unnamedSweep.batch_id, 'Unnamed parameter sweep'],
      ] as const) {
        await wrapper
          .get('[data-testid="workspace-search"] input')
          .setValue('');
        const identity = history().get(
          `[data-testid="workspace-${kind}-${id}"] .run-identity`,
        );
        expect(identity.get('span').text()).toBe(label);
        expect(identity.get('small').text()).toBe(id.slice(0, 8));
        expect(identity.get('span').attributes('title')).toBe(id);
        await wrapper
          .get('[data-testid="workspace-search"] input')
          .setValue(`  ${label.toUpperCase()}  `);
        expect(history().findAll('tbody tr')).toHaveLength(1);
        expect(
          history().find(`[data-testid="workspace-${kind}-${id}"]`).exists(),
        ).toBe(true);
      }
      await wrapper
        .get('[data-testid="workspace-search"] input')
        .setValue('Ignored legacy name');
      expect(
        history()
          .find('[data-testid="workspace-run-void-run-full-uuid"]')
          .exists(),
      ).toBe(false);
      for (const query of [
        named.run_id,
        namedSweep.batch_id,
        namedSweep.submission_id,
      ]) {
        await wrapper
          .get('[data-testid="workspace-search"] input')
          .setValue(query);
        expect(history().findAll('tbody tr')).toHaveLength(1);
      }
      await wrapper.get('[data-testid="workspace-search"] input').setValue('');
      wrapper.findAllComponents(NDataTable)[0].vm.sort('name', 'ascend');
      await flushPromises();
      expect(
        history()
          .findAll('.run-identity span')
          .map((identity) => identity.text()),
      ).toEqual([
        'Alpha research',
        'Beta research',
        'Unnamed parameter sweep',
        'Unnamed standalone run',
      ]);
      await history()
        .get(`[data-testid="workspace-run-${named.run_id}"]`)
        .trigger('click');
      await flushPromises();
      expect(wrapper.get('.strategy-name').text()).toBe('Alpha research');
      wrapper.unmount();
    },
  );

  it('filters by search, status, Market, Strategy, and Timeframe', async () => {
    const euro = run('euro', {
      name: 'Euro setup',
    });
    const pound = run('pound', {
      status: 'failed',
      request: {
        ...run('x').request,
        symbols: ['GBPUSD'],
        timeframe: 'H1',
        strategy: { strategy_id: 'breakout', parameters: {} },
      },
      metrics: null,
    });
    vi.mocked(listBacktestRuns).mockResolvedValue([euro, pound]);
    vi.mocked(getBacktestRun).mockResolvedValue(euro);
    const wrapper = mountWorkspace();
    await flushPromises();

    const history = () => wrapper.find('[data-testid="workspace-history"]');
    await wrapper
      .find('[data-testid="workspace-search"] input')
      .setValue('Euro setup');
    expect(history().find('[data-testid="workspace-run-euro"]').exists()).toBe(
      true,
    );
    expect(history().find('[data-testid="workspace-run-pound"]').exists()).toBe(
      false,
    );
    await wrapper.find('[data-testid="workspace-search"] input').setValue('');

    for (const [index, value] of [
      [0, 'failed'],
      [2, 'FX:GBPUSD'],
      [3, 'breakout'],
      [4, 'H1'],
    ] as const) {
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', value);
      await wrapper.vm.$nextTick();
      expect(
        history().find('[data-testid="workspace-run-pound"]').exists(),
      ).toBe(true);
      expect(
        history().find('[data-testid="workspace-run-euro"]').exists(),
      ).toBe(false);
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', 'all');
      await wrapper.vm.$nextTick();
    }
    wrapper.unmount();
  });

  it('sorts history dates in both directions with deterministic rows', async () => {
    const older = run('older');
    const newer = run('newer', {
      request: {
        ...older.request,
        start_ms: older.request.start_ms + 86_400_000,
      },
    });
    vi.mocked(listBacktestRuns).mockResolvedValue([newer, older]);
    const wrapper = mountWorkspace();
    await flushPromises();

    const startHeader = wrapper
      .findAll('th')
      .find((header) => header.text().includes('Start date'));
    expect(startHeader).toBeDefined();
    const rowIds = () =>
      wrapper
        .find('[data-testid="workspace-history"]')
        .findAll('[data-testid^="workspace-run-"]')
        .map((row) => row.attributes('data-testid'));

    await startHeader?.trigger('click');
    expect(rowIds()).toEqual(['workspace-run-newer', 'workspace-run-older']);
    await startHeader?.trigger('click');
    expect(rowIds()).toEqual(['workspace-run-older', 'workspace-run-newer']);
    wrapper.unmount();
  });
});
