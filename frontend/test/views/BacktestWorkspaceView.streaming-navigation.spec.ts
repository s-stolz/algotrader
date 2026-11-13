import {
  setupRoutingTests,
  openWorkspace,
} from './backtestWorkspaceRoutingFixtures';
import { member } from '../components/Backtest/backtestOverviewFixtures';
import {
  fetchBacktestEquityCurve,
  getBacktestRun,
  listBacktestMembers,
} from '@/api/backtesterClient';
import router from '@/router';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { emitBacktestChange } from '../backtestEventSocket';

describe('replay navigation cancellation', () => {
  setupRoutingTests();
  it.each(['button', 'route'])(
    'pauses streams on history via %s and resumes on return',
    async (mode) => {
      const runs = [0, 1, 2].map((i) => ({
        ...member(i),
        status: 'succeeded' as const,
      }));
      vi.mocked(listBacktestMembers).mockResolvedValue(runs);
      vi.mocked(getBacktestRun).mockImplementation(async (id) =>
        runs.find((run) => run.run_id === id)!,
      );
      vi.mocked(fetchBacktestEquityCurve)
        .mockReset()
        .mockImplementation(
          (_id, _max, options) =>
            new Promise((_resolve, reject) => {
              options!.signal.addEventListener('abort', () =>
                reject(new DOMException('Aborted', 'AbortError')),
              );
            }),
        );
      const wrapper = await openWorkspace();
      for (const run of runs) {
        await wrapper
          .get(`[data-testid="comparison-select-${run.run_id}"]`)
          .setValue(true);
      }
      await flushPromises();
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(2);
      const signals = vi
        .mocked(fetchBacktestEquityCurve)
        .mock.calls.map((call) => call[2]!.signal);
      if (mode === 'button')
        await wrapper
          .get('[data-testid="workspace-history-return"]')
          .trigger('click');
      else await router.push('/backtests');
      await flushPromises();
      expect(signals.every((signal) => signal.aborted)).toBe(true);
      emitBacktestChange();
      await flushPromises();
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(2);
      if (mode === 'button')
        await wrapper
          .get('[data-testid="workspace-backtest-backtest-1"]')
          .trigger('click');
      else await router.push('/backtests/backtest-1');
      await flushPromises();
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(4);
    },
  );
});
