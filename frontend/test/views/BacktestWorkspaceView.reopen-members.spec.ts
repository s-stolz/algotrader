import {
  setupRoutingTests,
  openWorkspace,
  backtest,
} from './backtestWorkspaceRoutingFixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import {
  getBacktest,
  listBacktestMembers,
  listBacktests,
} from '@/api/backtesterClient';
import type { BacktestRun } from '@/types/backtesterContracts';
import router from '@/router';
import { member } from '../components/Backtest/backtestOverviewFixtures';

describe('Backtest member list on repeated navigation', () => {
  setupRoutingTests();
  it('keeps the completed backtest header and its runs together when reopened from history', async () => {
    vi.mocked(getBacktest).mockResolvedValue({
      ...backtest,
      status: 'completed',
      settled_count: 2,
      executed_count: 2,
      completed_at_ms: backtest.accepted_at_ms + 1000,
      outcome_counts: { ...backtest.outcome_counts, queued: 0, succeeded: 2 },
    });
    const wrapper = await openWorkspace();
    expect(wrapper.get('.status-badge').text()).toBe('Completed');
    expect(
      wrapper.find('[data-testid="workspace-member-member-0"]').exists(),
    ).toBe(true);
    await wrapper
      .get('[data-testid="workspace-history-return"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-backtest-backtest-1"]')
      .trigger('click');
    await flushPromises();
    expect(listBacktestMembers).toHaveBeenCalledTimes(1);
    expect(listBacktests).toHaveBeenCalledTimes(1);
    expect(wrapper.get('.status-badge').text()).toBe('Completed');
    expect(wrapper.get('[aria-label="Current Backtest"]').isVisible()).toBe(
      true,
    );
    expect(
      wrapper.find('[data-testid="workspace-member-member-0"]').exists(),
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="workspace-member-member-1"]').exists(),
    ).toBe(true);
  });
  it('shows the rows when the initial member response arrives after reopening', async () => {
    let resolveMembers!: (runs: BacktestRun[]) => void;
    vi.mocked(listBacktestMembers).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveMembers = resolve;
        }),
    );
    const wrapper = await openWorkspace();
    await wrapper
      .get('[data-testid="workspace-history-return"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-backtest-backtest-1"]')
      .trigger('click');
    await flushPromises();
    resolveMembers([member(0), member(1)]);
    await flushPromises();
    expect(listBacktestMembers).toHaveBeenCalledTimes(1);
    expect(
      wrapper.find('[data-testid="workspace-member-member-0"]').exists(),
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="workspace-member-member-1"]').exists(),
    ).toBe(true);
  });
  it('clears the previous rows while a different backtest is loading', async () => {
    const wrapper = await openWorkspace();
    expect(
      wrapper.find('[data-testid="workspace-member-member-0"]').exists(),
    ).toBe(true);
    let resolveMembers!: (runs: BacktestRun[]) => void;
    vi.mocked(getBacktest).mockResolvedValue({
      ...backtest,
      backtest_id: 'other',
    });
    vi.mocked(listBacktestMembers).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveMembers = resolve;
        }),
    );
    await router.push('/backtests/other');
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workspace-member-member-0"]').exists(),
    ).toBe(false);
    resolveMembers([
      { ...member(0), backtest_id: 'other', run_id: 'other-member' },
    ]);
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workspace-member-other-member"]').exists(),
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="workspace-member-member-0"]').exists(),
    ).toBe(false);
  });
});
