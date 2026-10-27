import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
  toggleAnalysisColumns,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { NDataTable } from 'naive-ui';

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

describe('production Backtest Workspace: comparison-settings', () => {
  setupWorkspaceTests();
  it(
    'compares ten successful members while retaining selection, ' +
      'failures, and settings',
    async () => {
      const members = Array.from({ length: 10 }, (_, ordinal) =>
        run(`member-${ordinal}`, {
          batch_id: 'comparison',
          member_ordinal: ordinal,
          request: {
            ...run('base').request,
            symbols: ordinal === 1 ? ['GBPUSD'] : ['EURUSD'],
            strategy: {
              strategy_id: 'sma',
              strategy_version: 1,
              parameters: { fast: ordinal, note: `value ${ordinal}` },
            },
          },
          metrics: {
            ...run('base').metrics,
            total_return_pct: ordinal % 2 ? -1.25 : 2.5,
          },
        }),
      );
      const noTrade = run('no-trade', {
        batch_id: 'comparison',
        member_ordinal: 10,
      });
      const failed = run('failed-member', {
        batch_id: 'comparison',
        member_ordinal: 11,
        status: 'failed',
        metrics: null,
      });
      const cancelled = run('cancelled-member', {
        batch_id: 'comparison',
        member_ordinal: 12,
        status: 'cancelled',
        metrics: null,
      });
      const saved = [...members, noTrade, failed, cancelled];
      const accepted = batch('comparison', saved.length);
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
      vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
      vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
      vi.mocked(listBacktestBatchMembers).mockResolvedValue(saved);
      vi.mocked(getBacktestRun).mockImplementation(
        async (id) => saved.find((item) => item.run_id === id)!,
      );
      vi.mocked(fetchBacktestEquityCurve).mockImplementation(async (id) => {
        if (id === 'member-1') throw new Error('Replay service unavailable');
        if (id === 'member-2')
          return {
            availability: 'unavailable',
            reason: 'fingerprint_mismatch',
            source_point_count: 0,
            returned_point_count: 0,
            sampled: false,
            equity_curve: [],
          };
        return {
          availability: 'exact',
          reason: null,
          source_point_count: 2,
          returned_point_count: 2,
          sampled: false,
          equity_curve: [
            { timestamp_ms: 1_714_521_600_000, equity: 10000, drawdown_pct: 0 },
            {
              timestamp_ms: 1_714_608_000_000,
              equity: id === 'member-0' ? 10200 : 9800,
              drawdown_pct: -2,
            },
          ],
        };
      });
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-batch-comparison"]')
        .trigger('click');
      await flushPromises();
      const table = () =>
        wrapper.find('[data-testid="workspace-current-backtest"]');
      expect(table().findAll('tbody tr')).toHaveLength(13);
      expect(
        table()
          .findAll('th')
          .slice(0, 2)
          .map((header) => header.text()),
      ).toEqual(['', 'Run']);
      expect(table().findAll('th').at(-1)!.text()).toBe('Actions');
      expect(
        table()
          .findAll('th')
          .some((header) => header.text() === 'Cancel'),
      ).toBe(false);
      expect(table().find('[data-testid^="workspace-cancel-"]').exists()).toBe(
        false,
      );
      expect(
        table()
          .get(
            '[data-testid="workspace-member-member-0"] td:nth-child(2) .run-identity span',
          )
          .text(),
      ).toBe('Run #1');
      expect(
        table()
          .get('[data-testid="workspace-member-member-0"] td')
          .find('button')
          .exists(),
      ).toBe(false);
      const dataTable = wrapper.findAllComponents(NDataTable).at(-1)!;
      expect(dataTable.props('maxHeight')).toBe(360);
      expect(dataTable.props('scrollX')).toBeGreaterThan(1000);
      expect(
        (dataTable.props('columns') ?? [])
          .slice(0, 2)
          .map((column: { fixed?: string }) => column.fixed),
      ).toEqual(['left', 'left']);
      expect(
        table().find('[data-testid="workspace-member-failed-member"]').text(),
      ).toContain('—');
      expect(
        table()
          .find('[data-testid="comparison-select-failed-member"]')
          .attributes('disabled'),
      ).toBeDefined();
      expect(
        table()
          .find('[data-testid="comparison-select-cancelled-member"]')
          .attributes('disabled'),
      ).toBeDefined();

      for (let index = 0; index < 10; index++) {
        await table()
          .find(`[data-testid="comparison-select-member-${index}"]`)
          .setValue(true);
      }
      await flushPromises();
      expect(fetchBacktestEquityCurve).toHaveBeenCalledWith('member-0');
      expect(fetchBacktestEquityCurve).toHaveBeenCalledWith('member-9');
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(10);
      expect(
        wrapper.find('[data-testid="comparison-compatibility"]').text(),
      ).toContain('Market');
      expect(
        wrapper.find('[data-testid="curve-status-member-1"]').text(),
      ).toContain('Replay service unavailable');
      expect(
        wrapper.find('[data-testid="curve-status-member-2"]').text(),
      ).toContain('Candle data changed');
      expect(
        table().find('[data-testid="workspace-member-member-1"]').text(),
      ).toContain('-1.25%');
      expect(
        table().find('[data-testid="workspace-member-member-1"]').text(),
      ).toContain('—');
      expect(
        table().find('[data-testid="workspace-member-member-0"]').text(),
      ).toContain('10200');

      expect(table().findAll('tbody tr')).toHaveLength(saved.length);
      expect(
        table()
          .find('[data-testid="comparison-select-member-0"]')
          .attributes('checked'),
      ).toBeDefined();
      expect(
        table()
          .find('[data-testid="comparison-select-member-9"]')
          .attributes('checked'),
      ).toBeDefined();
      const returnHeader = table()
        .findAll('th')
        .find((header) => header.text().includes('Return (%)'));
      await returnHeader?.trigger('click');
      const rowOrder = () =>
        table()
          .findAll('tbody tr')
          .map((row) => row.attributes('data-testid'));
      const sortedOrder = rowOrder();
      expect(sortedOrder).not.toEqual(
        saved.map((run) => `workspace-member-${run.run_id}`),
      );
      await toggleAnalysisColumns(wrapper, [
        'parameter:fast',
        'parameter:note',
      ]);
      expect(table().text()).toContain('Parameter: fast');
      expect(table().text()).toContain('Parameter: note');
      expect(rowOrder()).toEqual(sortedOrder);
      expect(
        table()
          .find('[data-testid="comparison-select-member-9"]')
          .attributes('checked'),
      ).toBeDefined();
      await toggleAnalysisColumns(wrapper, [
        'long-win',
        'short-win',
        'long-pnl',
        'short-pnl',
      ]);
      expect(
        table().find('[data-testid="workspace-member-no-trade"]').text(),
      ).toContain('No trades');
      expect(
        table().find('[data-testid="workspace-member-no-trade"]').text(),
      ).toContain('0');
      expect(rowOrder()).toEqual(sortedOrder);
      await toggleAnalysisColumns(wrapper, [
        'long-win',
        'short-win',
        'long-pnl',
        'short-pnl',
      ]);
      await table()
        .find('[data-testid="workspace-log-member-0"]')
        .trigger('click');
      await flushPromises();
      expect(
        table()
          .find('[data-testid="comparison-select-member-0"]')
          .attributes('checked'),
      ).toBeDefined();
      wrapper.unmount();
    },
    30000,
  );
});
