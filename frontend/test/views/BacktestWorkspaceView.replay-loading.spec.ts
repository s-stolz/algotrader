import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import {
  setupWorkspaceTests,
  run,
  backtest,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import {
  listBacktests,
  getBacktest,
  listBacktestMembers,
  getBacktestRun,
  fetchBacktestEquityCurve,
} from '@/api/backtesterClient';
import type { EquityReplayResponse } from '@/types/backtesterContracts';

describe('Backtest Workspace replay loading', () => {
  setupWorkspaceTests();
  it('shows both placeholders immediately and retains loaded charts while another run loads or fails', async () => {
    const members = [0, 1].map((ordinal) =>
      run(`loading-${ordinal}`, {
        backtest_id: 'loading',
        run_ordinal: ordinal,
      }),
    );
    const saved = backtest('loading', 2);
    vi.mocked(listBacktests).mockResolvedValue([saved]);
    vi.mocked(getBacktest).mockResolvedValue(saved);
    vi.mocked(listBacktestMembers).mockResolvedValue(members);
    vi.mocked(getBacktestRun).mockImplementation(async (id) =>
      members.find((member) => member.run_id === id)!,
    );
    let resolveFirst!: (curve: EquityReplayResponse) => void;
    let rejectSecond!: (error: Error) => void;
    vi.mocked(fetchBacktestEquityCurve)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((_resolve, reject) => {
            rejectSecond = reject;
          }),
      );
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-backtest-loading"]')
      .trigger('click');
    await flushPromises();
    expect(wrapper.find('.replay-loading').exists()).toBe(false);
    await wrapper
      .get('[data-testid="comparison-select-loading-0"]')
      .setValue(true);
    await flushPromises();
    expect(wrapper.findAll('.chart-skeleton')).toHaveLength(2);
    expect(wrapper.get('.replay-loading').attributes('aria-busy')).toBe('true');
    expect(wrapper.get('.replay-loading').text()).toContain(
      'Loading equity and drawdown',
    );
    resolveFirst({
      availability: 'exact',
      reason: null,
      source_point_count: 1,
      returned_point_count: 1,
      sampled: false,
      equity_curve: [
        { timestamp_ms: 1714521600000, equity: 10000, drawdown_pct: 0 },
      ],
    });
    await flushPromises();
    const chart = wrapper.getComponent({ name: 'EquityReplayCharts' });
    expect(wrapper.find('.replay-loading').exists()).toBe(false);
    await wrapper
      .get('[data-testid="comparison-select-loading-1"]')
      .setValue(true);
    await flushPromises();
    expect(wrapper.get('.replay-loading').text()).toContain('1 run');
    expect(wrapper.findAll('.chart-skeleton')).toHaveLength(0);
    expect(wrapper.getComponent({ name: 'EquityReplayCharts' }).vm).toBe(
      chart.vm,
    );
    rejectSecond(new Error('Replay unavailable'));
    await flushPromises();
    expect(wrapper.find('.replay-loading').exists()).toBe(false);
    expect(
      wrapper.get('[data-testid="curve-status-loading-1"]').text(),
    ).toContain('Replay unavailable');
    expect(wrapper.getComponent({ name: 'EquityReplayCharts' }).vm).toBe(
      chart.vm,
    );
    await wrapper
      .get('[data-testid="comparison-select-loading-0"]')
      .setValue(false);
    await wrapper
      .get('[data-testid="comparison-select-loading-1"]')
      .setValue(false);
    expect(wrapper.find('.curve-inspection').exists()).toBe(false);
  });
});
