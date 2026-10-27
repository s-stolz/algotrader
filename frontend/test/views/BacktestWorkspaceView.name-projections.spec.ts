import {
  setupWorkspaceTests,
  run,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  renameExperiment,
  fetchBacktestEquityCurve,
  getBacktestRun,
  listBacktestRuns,
} from '@/api/backtesterClient';

import type { EquityReplayResponse } from '@/types/backtesterContracts';

describe('production Backtest Workspace: name-projections', () => {
  setupWorkspaceTests();
  it(
    'preserves a confirmed rename in comparison and chart legends ' +
      'after delayed Equity Replay',
    async () => {
      vi.useFakeTimers();
      const original = run('delayed-replay-name', { name: 'Before replay' });
      vi.mocked(listBacktestRuns).mockResolvedValue([original]);
      vi.mocked(getBacktestRun).mockResolvedValue(original);
      vi.mocked(renameExperiment).mockResolvedValue('After rename');
      let finishReplay!: (curve: EquityReplayResponse) => void;
      vi.mocked(fetchBacktestEquityCurve).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishReplay = resolve;
          }),
      );
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-run-delayed-replay-name"]')
        .trigger('click');
      await flushPromises();
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(1);
      await wrapper
        .get('.run-heading button[aria-label^="Edit experiment name"]')
        .trigger('click');
      const input = wrapper.get(
        '.run-heading input[aria-label="Experiment name"]',
      );
      await input.setValue('After rename');
      await input.trigger('keydown', { key: 'Enter' });
      await flushPromises();
      const persisted = { ...original, name: 'After rename' };
      vi.mocked(listBacktestRuns).mockResolvedValue([persisted]);
      vi.mocked(getBacktestRun).mockResolvedValue(persisted);
      await vi.advanceTimersByTimeAsync(5000);
      await flushPromises();
      const comparison = () =>
        wrapper.get(
          '[data-testid="workspace-current-backtest"] .run-identity span',
        );
      expect(comparison().text()).toBe('After rename');
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(1);
      finishReplay({
        availability: 'exact',
        reason: null,
        source_point_count: 1,
        returned_point_count: 1,
        sampled: false,
        equity_curve: [
          { timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: 0 },
        ],
      });
      await flushPromises();
      expect(comparison().text()).toBe('After rename');
      expect(
        wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'),
      ).toEqual([expect.objectContaining({ name: 'After rename' })]);
      expect(
        wrapper
          .get('.run-heading button[aria-label^="Edit experiment name"]')
          .text(),
      ).toBe('After rename');
      expect(
        wrapper.get('[data-testid="workspace-run-delayed-replay-name"]').text(),
      ).toContain('After rename');
      wrapper.unmount();
    },
  );
});
