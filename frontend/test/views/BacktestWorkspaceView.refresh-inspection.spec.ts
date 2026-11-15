import { emitBacktestChange } from '../backtestEventSocket';
import {
  setupWorkspaceTests,
  run,
  backtest,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestEquityCurve,
  getBacktest,
  getBacktestRun,
  listBacktestEvents,
  listBacktestMembers,
  listBacktests,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: refresh-inspection', () => {
  setupWorkspaceTests();
  it('keeps settled replay series loaded across unchanged backtest refreshes', async () => {
    const members = [0, 1].map((ordinal) =>
      run(`member-${ordinal}`, { backtest_id: 'stable', run_ordinal: ordinal }),
    );
    const accepted = backtest('stable', 2);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktests).mockResolvedValue([accepted]);
    vi.mocked(getBacktest).mockResolvedValue(accepted);
    vi.mocked(listBacktestEvents).mockResolvedValue([]);
    vi.mocked(listBacktestMembers).mockResolvedValue(members);
    vi.mocked(getBacktestRun).mockImplementation(async (id) =>
      members.find((run) => run.run_id === id)!,
    );
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({
      availability: 'exact',
      reason: null,
      source_point_count: 1,
      returned_point_count: 1,
      sampled: false,
      equity_curve: [
        { timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 },
      ],
    });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-backtest-stable"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .find('[data-testid="comparison-select-member-0"]')
      .setValue(true);
    await wrapper
      .find('[data-testid="comparison-select-member-1"]')
      .setValue(true);
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(2);
    expect(
      wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: 'member-0',
          points: [
            {
              timestamp_ms: 1_714_521_600_000,
              equity: 10050,
              drawdown_pct: -1,
            },
          ],
        }),
      ]),
    );
    emitBacktestChange();
    await flushPromises();
    expect(listBacktestMembers).toHaveBeenCalledTimes(2);
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(2);
    expect(
      wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: 'member-0',
          points: [
            {
              timestamp_ms: 1_714_521_600_000,
              equity: 10050,
              drawdown_pct: -1,
            },
          ],
        }),
      ]),
    );
    expect(
      wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: 'member-1',
          points: [
            {
              timestamp_ms: 1_714_521_600_000,
              equity: 10050,
              drawdown_pct: -1,
            },
          ],
        }),
      ]),
    );
    wrapper.unmount();
  });

  it('keeps completed curves visible while another backtest member settles', async () => {
    const success = run('settled', { backtest_id: 'active', run_ordinal: 0 });
    const pending = run('pending', {
      backtest_id: 'active',
      run_ordinal: 1,
      status: 'running',
      metrics: null,
    });
    const accepted = backtest('active', 2);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktests).mockResolvedValue([accepted]);
    vi.mocked(getBacktest).mockResolvedValue(accepted);
    vi.mocked(listBacktestEvents).mockResolvedValue([]);
    vi.mocked(listBacktestMembers).mockResolvedValue([success, pending]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({
      availability: 'exact',
      reason: null,
      source_point_count: 1,
      returned_point_count: 1,
      sampled: false,
      equity_curve: [
        { timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 },
      ],
    });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-backtest-active"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .find('[data-testid="comparison-select-settled"]')
      .setValue(true);
    await flushPromises();
    vi.mocked(listBacktestMembers).mockResolvedValue([
      success,
      { ...pending, status: 'failed' },
    ]);
    vi.mocked(fetchBacktestEquityCurve).mockImplementation(
      () => new Promise(() => {}),
    );
    emitBacktestChange();
    await flushPromises();
    expect(
      wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: 'settled',
          points: [
            {
              timestamp_ms: 1_714_521_600_000,
              equity: 10050,
              drawdown_pct: -1,
            },
          ],
        }),
      ]),
    );
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
});
