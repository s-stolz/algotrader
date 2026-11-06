import { installBacktestSocket } from '../../backtestEventSocket';
import { createPinia, setActivePinia } from 'pinia';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest';
import savedDetails from '@/components/Backtest/inspection/BacktestSavedDetails.vue?raw';
import {
  getBacktest,
  listBacktestEvents,
  listBacktestMembers,
  controlBacktest,
} from '@/api/backtesterClient';
import { isBacktest, type Backtest } from '@/types/backtesterContracts';
import BacktestOverview from '@/components/Backtest/BacktestOverview.vue';

vi.mock('@/api/backtesterClient', () => ({
  controlBacktest: vi.fn(),
  renameExperiment: vi.fn(),
  getBacktest: vi.fn(),
  listBacktestEvents: vi.fn(),
  listBacktestMembers: vi.fn(),
}));

import { backtest, member } from './backtestOverviewFixtures';

describe('accepted backtest inspection: inspection', () => {
  beforeEach(() => {
    installBacktestSocket();
    setActivePinia(createPinia());
    vi.mocked(controlBacktest).mockReset();
    vi.mocked(getBacktest).mockReset().mockResolvedValue(backtest);
    vi.mocked(listBacktestMembers)
      .mockReset()
      .mockResolvedValue([member(0), member(1)]);
    vi.mocked(listBacktestEvents)
      .mockReset()
      .mockResolvedValue([
        {
          backtest_id: 'backtest-1',
          revision: 0,
          event_type: 'accepted',
          status: 'queued',
          prior_status: null,
          occurred_at_ms: backtest.accepted_at_ms,
          trigger_run_id: null,
          reason: null,
        },
      ]);
  });

  it('validates actual-member context and aggregate failure projection', () => {
    expect(isBacktest(backtest)).toBe(true);
    expect(isBacktest({ ...backtest, has_failed_members: true })).toBe(false);
    expect(isBacktest({ ...backtest, market_contexts: [] })).toBe(false);
  });

  it('emits actual members to the workspace comparison table', async () => {
    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    await flushPromises();
    expect(wrapper.get('h3').text()).toBe('Unnamed backtest');
    expect(wrapper.emitted('members')?.[0]).toEqual([
      'backtest-1',
      [member(0), member(1)],
    ]);
    expect(
      wrapper.find('[data-testid="workspace-backtest-members"]').exists(),
    ).toBe(false);
    wrapper.unmount();
  });

  it('keeps saved disclosure focus interactive and activation native', async () => {
    const style = document.createElement('style');
    document.body.style.setProperty('--design-color-interactive', '#63e2b7');
    style.textContent = savedDetails
      .split('<style scoped>')[1]
      .split('</style>')[0];
    document.head.append(style);
    const wrapper = mount(BacktestOverview, {
      attachTo: document.body,
      props: { backtestId: 'backtest-1' },
    });
    onTestFinished(() => {
      wrapper.unmount();
      style.remove();
      document.body.style.removeProperty('--design-color-interactive');
    });
    await flushPromises();
    const summary = wrapper.get('.selections-details summary')
      .element as HTMLElement;
    summary.focus();
    expect(document.activeElement).toBe(summary);
    expect(summary.matches(':focus-visible')).toBe(true);
    expect(getComputedStyle(summary).outline).toBe(
      '2px solid rgb(99, 226, 183)',
    );
    expect(getComputedStyle(summary).outlineOffset).toBe('5px');
    const details = summary.parentElement as HTMLDetailsElement;
    summary.click();
    expect(details.open).toBe(true);
    summary.click();
    expect(details.open).toBe(false);
  });

  it('shows the saved experiment name again after reloading detail', async () => {
    vi.mocked(getBacktest).mockResolvedValue({
      ...backtest,
      name: 'Selections research',
    });
    for (let reload = 0; reload < 2; reload += 1) {
      const wrapper = mount(BacktestOverview, {
        props: { backtestId: 'backtest-1' },
      });
      await flushPromises();
      expect(wrapper.get('h3').text()).toBe('Selections research');
      wrapper.unmount();
    }
  });

  it('does not discard a backtest read that takes several seconds', async () => {
    vi.useFakeTimers();
    let resolve!: (backtest: Backtest) => void;
    vi.mocked(getBacktest).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    vi.advanceTimersByTime(10_000);
    await flushPromises();
    expect(getBacktest).toHaveBeenCalledTimes(1);
    resolve(backtest);
    await flushPromises();
    expect(wrapper.emitted('members')).toHaveLength(1);
    wrapper.unmount();
    vi.useRealTimers();
  });

  it(
    'shows one backtest summary, saved definition, and actual ordered ' +
      'Ready members after reload',
    async () => {
      const reloaded = mount(BacktestOverview, {
        props: { backtestId: 'backtest-1' },
      });
      await flushPromises();
      expect(reloaded.text()).toContain('2 of 3 combinations');
      expect(
        reloaded.get('[role="progressbar"]').attributes('aria-valuetext'),
      ).toContain('0 / 2 settled');
      expect(reloaded.text()).not.toContain('0 executed');
      expect(reloaded.emitted('members')?.[0]).toEqual([
        'backtest-1',
        [member(0), member(1)],
      ]);
      expect(
        reloaded.find('[data-testid="workspace-backtest-members"]').exists(),
      ).toBe(false);
      expect(reloaded.text()).toContain(
        'Full saved definition and strategy metadata',
      );
      expect(
        reloaded.get('[role="progressbar"]').attributes('aria-valuenow'),
      ).toBe('0');
      reloaded.unmount();
    },
  );
});
