import { defineComponent, ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchBacktestQueue } from '@/api/backtesterClient';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';
import type { BacktestQueueSnapshot } from '@/types/backtesterContracts';

vi.mock('@/api/backtesterClient', () => ({ fetchBacktestQueue: vi.fn() }));

const PopoverStub = defineComponent({
  props: ['show'],
  emits: ['update:show'],
  template: '<div><div @click="$emit(\'update:show\', !show)"><slot name="trigger" /></div><div v-if="show"><slot /></div></div>',
});
async function openQueue() {
  const wrapper = mount(BacktestQueueHealth, { global: { stubs: { BasePopover: PopoverStub } } });
  await flushPromises();
  await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
  return wrapper;
}

const NOW = 1_780_922_100_000;
const healthySnapshot: BacktestQueueSnapshot = {
  snapshot_at_ms: NOW,
  active_run: { run_id: 'long-run', started_at_ms: NOW - 120_000,
    batch_id: null, member_ordinal: null },
  last_heartbeat_ms: NOW - 1000,
  availability: 'healthy', stale_after_ms: 30_000, operational_faults: [],
  queued: [{ entry_type: 'standalone', run_id: 'waiting', batch_id: null,
    submitted_at_ms: NOW - 60_000, estimated_position: 1,
    next_member_ordinal: null, outcome_counts: null }],
};

describe('Backtest queue health', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.mocked(fetchBacktestQueue).mockReset().mockResolvedValue(healthySnapshot);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls while mounted and computes elapsed times from current clock', async () => {
    const wrapper = await openQueue();
    await flushPromises();
    expect(wrapper.get('[data-testid="queue-toggle"]').text()).toContain('1 running');
    expect(wrapper.find('[data-testid="workspace-queue-active-section"]').text()).toContain('Active for 2m 0s');
    expect(wrapper.find('[data-testid="workspace-queue-run-waiting"]').text())
      .toContain('1');
    expect(wrapper.text()).toContain('waiting 1m 0s');
    expect(wrapper.text()).not.toContain('Estimated order');
    expect(wrapper.text()).not.toContain('Last heartbeat');

    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(wrapper.find('[data-testid="workspace-queue-active-section"]').text()).toContain('2m 5s');
    wrapper.unmount();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
  });

  it('shows batch turns, active ordinal, advisory position, and outcome counts on refresh', async () => {
    vi.mocked(fetchBacktestQueue).mockResolvedValueOnce({ ...healthySnapshot,
      active_run: { run_id: 'member-0', batch_id: 'active-batch', member_ordinal: 0,
        started_at_ms: NOW - 120_000 },
      queued: [{ entry_type: 'batch', run_id: null, batch_id: 'waiting-batch',
        submitted_at_ms: NOW - 60_000, estimated_position: 1, next_member_ordinal: 2,
        outcome_counts: { queued: 1, running: 0, cancelling: 0, succeeded: 1,
          failed: 1, cancelled: 0 } }],
    });
    const wrapper = await openQueue();
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-active-section"]').text())
      .toContain('Run #1');
    expect(wrapper.find('[data-testid="workspace-queue-active-section"]').text()).toContain('active-batch');
    expect(wrapper.find('[data-testid="workspace-queue-batch-waiting-batch"]').text())
      .toContain('1');
    expect(wrapper.find('[data-testid="workspace-queue-batch-waiting-batch"]').text())
      .toContain('next Run #3');
    expect(wrapper.text()).toContain('1 succeeded');
    expect(wrapper.text()).toContain('1 failed');
    await wrapper.get('[data-testid="workspace-queue-batch-waiting-batch"] button').trigger('click');
    expect(wrapper.emitted('inspect')).toEqual([['batch', 'waiting-batch']]);
    await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-run-waiting"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it('shows absent, stale, and faulted worker signals without changing queue history', async () => {
    vi.mocked(fetchBacktestQueue)
      .mockResolvedValueOnce({ ...healthySnapshot, active_run: null,
        last_heartbeat_ms: null, availability: 'unavailable' })
      .mockResolvedValueOnce({ ...healthySnapshot, availability: 'stale' })
      .mockResolvedValueOnce({ ...healthySnapshot, availability: 'faulted',
        operational_faults: [{ code: 'terminal_persistence_failed', message: 'Settlement failed' }] });
    const wrapper = await openQueue();
    await flushPromises();
    expect(wrapper.text()).toContain('Worker: unavailable');
    expect(wrapper.get('[data-testid="queue-toggle"]').text()).toContain('Needs attention');
    expect(wrapper.find('[data-testid="workspace-queue-run-waiting"]').exists()).toBe(true);

    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.text()).toContain('Worker: stale');
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.text()).toContain('Worker: faulted');
    expect(wrapper.text()).toContain('Settlement failed');
    wrapper.unmount();
  });

  it('keeps last known context but marks failed and aged snapshots unknown', async () => {
    vi.mocked(fetchBacktestQueue).mockResolvedValueOnce(healthySnapshot)
      .mockRejectedValueOnce(new Error('Service unreachable'));
    const wrapper = await openQueue();
    await flushPromises();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-unknown"]').text())
      .toContain('Service unreachable');
    expect(wrapper.find('[data-testid="workspace-queue-active-section"]').text())
      .toContain('Last known active run');
    expect(wrapper.get('[data-testid="queue-toggle"]').text()).toContain('Last known: 1 waiting');

    vi.mocked(fetchBacktestQueue).mockResolvedValueOnce(healthySnapshot);
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-unknown"]').exists()).toBe(false);
    vi.mocked(fetchBacktestQueue).mockImplementationOnce(() => new Promise(() => {}));
    vi.advanceTimersByTime(35_000);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-unknown"]').text())
      .toContain('latest snapshot is old');
    wrapper.unmount();
  });

  it('allows a slow poll to finish before scheduling another', async () => {
    let resolve!: (snapshot: BacktestQueueSnapshot) => void;
    vi.mocked(fetchBacktestQueue).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    const wrapper = await openQueue();
    vi.advanceTimersByTime(10_000);
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(1);
    resolve(healthySnapshot);
    await flushPromises();
    expect(wrapper.get('[data-testid="queue-toggle"]').text()).toContain('1 running');
    wrapper.unmount();
  });

  it('ignores an older response after a newer refresh and after closing', async () => {
    let resolveFirst!: (snapshot: BacktestQueueSnapshot) => void;
    vi.mocked(fetchBacktestQueue)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce({ ...healthySnapshot, active_run: null, queued: [] });
    const wrapper = await openQueue();
    await flushPromises();
    await wrapper.vm.refresh();
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-no-active"]').exists()).toBe(true);
    resolveFirst(healthySnapshot);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-no-active"]').exists()).toBe(true);
    wrapper.unmount();
  });
  it('starts collapsed, distinguishes loading from idle, and closes after navigation', async () => {
    let resolve!: (snapshot: BacktestQueueSnapshot) => void;
    vi.mocked(fetchBacktestQueue).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    const wrapper = mount(BacktestQueueHealth, { global: { stubs: { BasePopover: PopoverStub } } });
    expect(wrapper.get('[data-testid="queue-toggle"]').attributes('aria-expanded')).toBe('false');
    expect(wrapper.text()).toContain('Connecting');
    expect(wrapper.text()).toContain('Queue unknown');
    resolve(healthySnapshot);
    await flushPromises();
    await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
    await wrapper.get('[data-testid="queue-view-active"]').trigger('click');
    expect(wrapper.emitted('inspect')).toEqual([['run', 'long-run']]);
    expect(wrapper.get('[data-testid="queue-toggle"]').attributes('aria-expanded')).toBe('false');
    await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
    await wrapper.get('[data-testid="workspace-queue-run-waiting"] button').trigger('click');
    expect(wrapper.emitted('inspect')?.[1]).toEqual(['run', 'waiting']);
    await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
    await wrapper.get('[data-testid="queue-toggle"]').trigger('keydown', { key: 'Escape' });
    expect(wrapper.get('[data-testid="queue-toggle"]').attributes('aria-expanded')).toBe('false');
    wrapper.unmount();
  });

  it('does not display an empty queue after the initial request fails', async () => {
    vi.mocked(fetchBacktestQueue).mockRejectedValueOnce(new Error('Offline'));
    const wrapper = await openQueue();
    expect(wrapper.text()).toContain('Status unknown');
    expect(wrapper.text()).toContain('Queue unknown');
    expect(wrapper.find('[data-testid="workspace-queue-empty"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it('closes the popover and suspends polling when the workspace is kept alive offscreen', async () => {
    const shown = ref(true);
    const Host = defineComponent({
      components: { BacktestQueueHealth },
      setup: () => ({ shown }),
      template: '<KeepAlive><BacktestQueueHealth v-if="shown" /></KeepAlive>',
    });
    const wrapper = mount(Host, { global: { stubs: { BasePopover: PopoverStub } } });
    await flushPromises();
    await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
    shown.value = false;
    await flushPromises();
    vi.advanceTimersByTime(10_000);
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(1);
    expect(wrapper.find('[data-testid="queue-toggle"]').exists()).toBe(false);
    shown.value = true;
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(wrapper.get('[data-testid="queue-toggle"]').attributes('aria-expanded')).toBe('false');
    wrapper.unmount();
  });

});
