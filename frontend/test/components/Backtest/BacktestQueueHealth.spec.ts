import { emitBacktestChange } from '../../backtestEventSocket';
import { installBacktestSocket } from '../../backtestEventSocket';
import { readFileSync } from 'node:fs';
import { defineComponent, ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  onTestFinished,
  vi,
} from 'vitest';

import { fetchBacktestQueue } from '@/api/backtesterClient';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';
import type { BacktestQueueSnapshot } from '@/types/backtesterContracts';

vi.mock('@/api/backtesterClient', () => ({ fetchBacktestQueue: vi.fn() }));

import {
  PopoverStub,
  openQueue,
  backtest,
  NOW,
  healthySnapshot,
} from './backtestQueueFixtures';
describe('Backtest queue health', () => {
  beforeEach(() => {
    installBacktestSocket();
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.mocked(fetchBacktestQueue)
      .mockReset()
      .mockResolvedValue(healthySnapshot);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it(
    'keeps the floating activity trigger keyboard-focusable and ' +
      'toggles its popover',
    async () => {
      const style = document.createElement('style');
      document.body.style.setProperty('--design-color-interactive', '#63e2b7');
      style.textContent = readFileSync(
        'src/components/Backtest/backtestQueueHealth.css',
        'utf8',
      );
      document.head.append(style);
      const wrapper = mount(BacktestQueueHealth, {
        attachTo: document.body,
        global: { stubs: { BasePopover: PopoverStub } },
      });
      onTestFinished(() => {
        wrapper.unmount();
        style.remove();
        document.body.style.removeProperty('--design-color-interactive');
      });
      await flushPromises();
      const trigger = wrapper.get('[data-testid="queue-toggle"]');
      (trigger.element as HTMLElement).focus();
      expect(document.activeElement).toBe(trigger.element);
      expect(getComputedStyle(trigger.element).outline).toBe(
        '2px solid rgb(99, 226, 183)',
      );
      await trigger.trigger('click');
      expect(trigger.attributes('aria-expanded')).toBe('true');
      await trigger.trigger('click');
      expect(trigger.attributes('aria-expanded')).toBe('false');
    },
  );

  it('refreshes on events without polling and computes elapsed times locally', async () => {
    const wrapper = await openQueue();
    await flushPromises();
    expect(wrapper.get('[data-testid="queue-toggle"]').text()).toContain(
      '1 running',
    );
    expect(
      wrapper.find('[data-testid="workspace-queue-active-section"]').text(),
    ).toContain('Active for 2m 0s');
    expect(wrapper.text()).toContain('waiting 1m 0s');
    expect(wrapper.text()).not.toContain('Estimated order');
    expect(wrapper.text()).not.toContain('Last heartbeat');

    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(1);
    emitBacktestChange();
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(
      wrapper.find('[data-testid="workspace-queue-active-section"]').text(),
    ).toContain('2m 5s');
    wrapper.unmount();
    vi.advanceTimersByTime(5000);
    emitBacktestChange();
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
  });

  it(
    'shows backtest turns, active ordinal, advisory position, and ' +
      'outcome counts on refresh',
    async () => {
      vi.mocked(fetchBacktestQueue).mockResolvedValueOnce({
        ...healthySnapshot,
        active_run: {
          run_id: 'member-0',
          backtest_id: 'active-backtest',
          run_ordinal: 0,
          started_at_ms: NOW - 120_000,
        },
        queued: [
          {
            backtest_id: 'waiting-backtest',
            submitted_at_ms: NOW - 60_000,
            estimated_position: 1,
            next_run_ordinal: 2,
            outcome_counts: {
              queued: 1,
              running: 0,
              cancelling: 0,
              succeeded: 1,
              failed: 1,
              cancelled: 0,
            },
          },
        ],
      });
      const wrapper = await openQueue();
      await flushPromises();
      expect(
        wrapper.find('[data-testid="workspace-queue-active-section"]').text(),
      ).toContain('Currently running #1');
      expect(
        wrapper.find('[data-testid="workspace-queue-active-section"]').text(),
      ).toContain('active-backtest');
      expect(
        wrapper
          .find('[data-testid="workspace-queue-backtest-waiting-backtest"]')
          .text(),
      ).toContain('1');
      expect(
        wrapper
          .find('[data-testid="workspace-queue-backtest-waiting-backtest"]')
          .text(),
      ).toContain('3 runs · 2 finished');
      expect(wrapper.text()).toContain('1 failed');
      await wrapper
        .get('[data-testid="workspace-queue-backtest-waiting-backtest"] button')
        .trigger('click');
      expect(wrapper.emitted('inspect')).toEqual([['waiting-backtest']]);
      await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
      vi.advanceTimersByTime(5000);
      emitBacktestChange();
      await flushPromises();
      expect(
        wrapper
          .find('[data-testid="workspace-queue-backtest-waiting"]')
          .exists(),
      ).toBe(true);
      wrapper.unmount();
    },
  );

  it(
    'opens the selections instead of its transient member and displays ' +
      'aggregate progress',
    async () => {
      vi.mocked(fetchBacktestQueue).mockResolvedValue({
        ...healthySnapshot,
        active_run: {
          run_id: 'member-0',
          backtest_id: 'backtest-1',
          run_ordinal: 1,
          started_at_ms: NOW,
        },
      });
      const wrapper = await openQueue({
        backtests: [
          {
            ...backtest,
            name: 'MA exploration',
            status: 'running',
            settled_count: 1,
            outcome_counts: {
              ...backtest.outcome_counts,
              queued: 0,
              running: 1,
              succeeded: 1,
            },
          },
        ],
      });
      expect(wrapper.text()).toContain('MA exploration');
      expect(wrapper.text()).toContain('1 / 2 finished');
      expect(wrapper.get('progress').attributes('value')).toBe('1');
      await wrapper.get('[data-testid="queue-view-active"]').trigger('click');
      expect(wrapper.emitted('inspect')).toEqual([['backtest-1']]);
      expect(
        wrapper.get('[data-testid="queue-toggle"]').attributes('aria-expanded'),
      ).toBe('false');
      wrapper.unmount();
    },
  );

  it(
    'keeps finished experiments discoverable between polls, excludes ' +
      'members, and expires recent entries',
    async () => {
      vi.mocked(fetchBacktestQueue).mockResolvedValue({
        ...healthySnapshot,
        active_run: null,
        queued: [],
      });
      const wrapper = await openQueue({
        backtests: [
          {
            ...backtest,
            status: 'completed',
            name: 'Finished selections',
            completed_at_ms: NOW - 2000,
            settled_count: 2,
            outcome_counts: {
              ...backtest.outcome_counts,
              queued: 0,
              succeeded: 1,
              failed: 1,
            },
          },
        ],
      });
      const recent = wrapper.get(
        '[aria-label="Recently finished experiments"]',
      );
      expect(recent.text()).toContain('Finished selections');
      expect(recent.text()).toContain('1 failed');
      await recent.findAll('button')[0].trigger('click');
      expect(wrapper.emitted('inspect')).toEqual([['backtest-1']]);
      await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
      vi.advanceTimersByTime(60_000);
      emitBacktestChange();
      await flushPromises();
      expect(
        wrapper.find('[aria-label="Recently finished experiments"]').exists(),
      ).toBe(false);
      wrapper.unmount();
    },
  );

  it(
    'shows absent, stale, and faulted worker signals without changing ' +
      'queue history',
    async () => {
      vi.mocked(fetchBacktestQueue)
        .mockResolvedValueOnce({
          ...healthySnapshot,
          active_run: null,
          last_heartbeat_ms: null,
          availability: 'unavailable',
        })
        .mockResolvedValueOnce({ ...healthySnapshot, availability: 'stale' })
        .mockResolvedValueOnce({
          ...healthySnapshot,
          availability: 'faulted',
          operational_faults: [
            {
              code: 'terminal_persistence_failed',
              message: 'Settlement failed',
            },
          ],
        });
      const wrapper = await openQueue();
      await flushPromises();
      expect(wrapper.text()).toContain('Worker: unavailable');
      expect(wrapper.get('[data-testid="queue-toggle"]').text()).toContain(
        'Needs attention',
      );
      expect(
        wrapper
          .find('[data-testid="workspace-queue-backtest-waiting"]')
          .exists(),
      ).toBe(true);

      vi.advanceTimersByTime(5000);
      emitBacktestChange();
      await flushPromises();
      expect(wrapper.text()).toContain('Worker: stale');
      vi.advanceTimersByTime(5000);
      emitBacktestChange();
      await flushPromises();
      expect(wrapper.text()).toContain('Worker: faulted');
      expect(wrapper.text()).toContain('Settlement failed');
      wrapper.unmount();
    },
  );

  it('keeps last known context but marks failed and aged snapshots unknown', async () => {
    vi.mocked(fetchBacktestQueue)
      .mockResolvedValueOnce(healthySnapshot)
      .mockRejectedValueOnce(new Error('Service unreachable'));
    const wrapper = await openQueue();
    await flushPromises();
    vi.advanceTimersByTime(5000);
    emitBacktestChange();
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workspace-queue-unknown"]').text(),
    ).toContain('Service unreachable');
    expect(
      wrapper.find('[data-testid="workspace-queue-active-section"]').text(),
    ).toContain('Last known running');
    expect(wrapper.get('[data-testid="queue-toggle"]').text()).toContain(
      'Last known: 1 waiting',
    );

    vi.mocked(fetchBacktestQueue).mockResolvedValueOnce(healthySnapshot);
    vi.advanceTimersByTime(5000);
    emitBacktestChange();
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workspace-queue-unknown"]').exists(),
    ).toBe(false);
    vi.mocked(fetchBacktestQueue).mockImplementationOnce(
      () => new Promise(() => {}),
    );
    vi.advanceTimersByTime(35_000);
    emitBacktestChange();
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workspace-queue-unknown"]').text(),
    ).toContain('latest snapshot is old');
    wrapper.unmount();
  });

  it('allows a slow poll to finish before scheduling another', async () => {
    let resolve!: (snapshot: BacktestQueueSnapshot) => void;
    vi.mocked(fetchBacktestQueue).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const wrapper = await openQueue();
    vi.advanceTimersByTime(10_000);
    emitBacktestChange();
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(1);
    resolve(healthySnapshot);
    await flushPromises();
    expect(wrapper.get('[data-testid="queue-toggle"]').text()).toContain(
      '1 running',
    );
    wrapper.unmount();
  });

  it('ignores an older response after a newer refresh and after closing', async () => {
    let resolveFirst!: (snapshot: BacktestQueueSnapshot) => void;
    vi.mocked(fetchBacktestQueue)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockResolvedValueOnce({
        ...healthySnapshot,
        active_run: null,
        queued: [],
      });
    const wrapper = await openQueue();
    await flushPromises();
    await wrapper.vm.refresh();
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workspace-queue-no-active"]').exists(),
    ).toBe(true);
    resolveFirst(healthySnapshot);
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workspace-queue-no-active"]').exists(),
    ).toBe(true);
    wrapper.unmount();
  });
  it(
    'starts collapsed, distinguishes loading from idle, and closes ' +
      'after navigation',
    async () => {
      let resolve!: (snapshot: BacktestQueueSnapshot) => void;
      vi.mocked(fetchBacktestQueue).mockImplementationOnce(
        () =>
          new Promise((done) => {
            resolve = done;
          }),
      );
      const wrapper = mount(BacktestQueueHealth, {
        global: { stubs: { BasePopover: PopoverStub } },
      });
      expect(
        wrapper.get('[data-testid="queue-toggle"]').attributes('aria-expanded'),
      ).toBe('false');
      expect(wrapper.text()).toContain('Connecting');
      expect(wrapper.text()).toContain('Queue unknown');
      resolve(healthySnapshot);
      await flushPromises();
      await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
      await wrapper.get('[data-testid="queue-view-active"]').trigger('click');
      expect(wrapper.emitted('inspect')).toEqual([['backtest-1']]);
      expect(
        wrapper.get('[data-testid="queue-toggle"]').attributes('aria-expanded'),
      ).toBe('false');
      await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
      await wrapper
        .get('[data-testid="workspace-queue-backtest-waiting"] button')
        .trigger('click');
      expect(wrapper.emitted('inspect')?.[1]).toEqual(['waiting']);
      await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
      await wrapper
        .get('[data-testid="queue-toggle"]')
        .trigger('keydown', { key: 'Escape' });
      expect(
        wrapper.get('[data-testid="queue-toggle"]').attributes('aria-expanded'),
      ).toBe('false');
      wrapper.unmount();
    },
  );

  it('does not display an empty queue after the initial request fails', async () => {
    vi.mocked(fetchBacktestQueue).mockRejectedValueOnce(new Error('Offline'));
    const wrapper = await openQueue();
    expect(wrapper.text()).toContain('Status unknown');
    expect(wrapper.text()).toContain('Queue unknown');
    expect(wrapper.find('[data-testid="workspace-queue-empty"]').exists()).toBe(
      false,
    );
    wrapper.unmount();
  });

  it(
    'closes the popover and suspends polling when the workspace is ' +
      'kept alive offscreen',
    async () => {
      const shown = ref(true);
      const Host = defineComponent({
        components: { BacktestQueueHealth },
        setup: () => ({ shown }),
        template: '<KeepAlive><BacktestQueueHealth v-if="shown" /></KeepAlive>',
      });
      const wrapper = mount(Host, {
        global: { stubs: { BasePopover: PopoverStub } },
      });
      await flushPromises();
      await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
      shown.value = false;
      await flushPromises();
      vi.advanceTimersByTime(10_000);
      emitBacktestChange();
      await flushPromises();
      expect(fetchBacktestQueue).toHaveBeenCalledTimes(1);
      expect(wrapper.find('[data-testid="queue-toggle"]').exists()).toBe(false);
      shown.value = true;
      await flushPromises();
      expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
      expect(
        wrapper.get('[data-testid="queue-toggle"]').attributes('aria-expanded'),
      ).toBe('false');
      wrapper.unmount();
    },
  );
});
