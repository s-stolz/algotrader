import {
  setupWorkspaceTests,
  run,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestEquityCurve,
  getBacktestRun,
  listBacktestRuns,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';

import type { BacktestRun } from '@/types/backtesterContracts';

describe('production Backtest Workspace: polling-selection', () => {
  setupWorkspaceTests();
  it('ignores detail responses for a selection that has since changed', async () => {
    const first = run('first');
    const second = run('second', { status: 'failed', metrics: null });
    let resolveFirst!: (value: BacktestRun) => void;
    vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
    vi.mocked(getBacktestRun).mockImplementation((id) =>
      id === 'first'
        ? new Promise((resolve) => {
            resolveFirst = resolve;
          })
        : Promise.resolve(second),
    );

    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-first"]').trigger('click');
    await wrapper.find('[data-testid="workspace-run-second"]').trigger('click');
    await flushPromises();
    resolveFirst(first);
    await flushPromises();

    expect(useBacktestWorkspaceStore().selectedRunId).toBe('second');
    expect(
      wrapper
        .find(
          '[data-testid="workspace-current-backtest"] [role="img"][aria-label="Failed"]',
        )
        .exists(),
    ).toBe(true);
    wrapper.unmount();
  });

  it('ignores a late curve after switching the open Backtest', async () => {
    const first = run('first');
    const second = run('second');
    vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
    vi.mocked(getBacktestRun).mockImplementation(async (id) =>
      id === 'first' ? first : second,
    );
    let resolveFirst!: (
      value: Awaited<ReturnType<typeof fetchBacktestEquityCurve>>,
    ) => void;
    vi.mocked(fetchBacktestEquityCurve).mockImplementation((id) =>
      id === 'first'
        ? new Promise((resolve) => {
            resolveFirst = resolve;
          })
        : Promise.resolve({
            availability: 'exact',
            reason: null,
            source_point_count: 1,
            returned_point_count: 1,
            sampled: false,
            equity_curve: [
              {
                timestamp_ms: 1_714_521_600_000,
                equity: 11000,
                drawdown_pct: 0,
              },
            ],
          }),
    );
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-first"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-second"]').trigger('click');
    await flushPromises();
    resolveFirst({
      availability: 'exact',
      reason: null,
      source_point_count: 1,
      returned_point_count: 1,
      sampled: false,
      equity_curve: [
        { timestamp_ms: 1_714_521_600_000, equity: 9000, drawdown_pct: -1 },
      ],
    });
    await flushPromises();
    expect(wrapper.find('[data-testid="curve-status-second"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="curve-status-first"]').exists()).toBe(
      false,
    );
    expect(
      wrapper.find('[data-testid="workspace-current-backtest"]').text(),
    ).toContain('11000');
    wrapper.unmount();
  });

  it('shows sampled exact equity beside saved Return and Initial capital', async () => {
    const success = run('success');
    vi.mocked(listBacktestRuns).mockResolvedValue([success]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({
      availability: 'exact',
      reason: null,
      source_point_count: 5000,
      returned_point_count: 2,
      sampled: true,
      equity_curve: [
        { timestamp_ms: 1_714_521_600_000, equity: 10000, drawdown_pct: 0 },
        { timestamp_ms: 1_714_608_000_000, equity: 9875, drawdown_pct: -1.25 },
      ],
    });
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-run-success"]')
      .trigger('click');
    await flushPromises();

    expect(fetchBacktestEquityCurve).toHaveBeenCalledWith('success');
    expect(
      wrapper.find('[data-testid="workspace-current-backtest"]').text(),
    ).toContain('9875');
    expect(wrapper.find('[data-testid="curve-status-success"]').exists()).toBe(
      false,
    );
    expect(
      wrapper.findComponent({ name: 'EquityReplayCharts' }).props('sampled'),
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="workspace-current-backtest"]').text(),
    ).toContain('-1.25%');
    expect(
      wrapper.find('[data-testid="workspace-current-backtest"]').text(),
    ).toContain('10000');
    wrapper.unmount();
  });
});
