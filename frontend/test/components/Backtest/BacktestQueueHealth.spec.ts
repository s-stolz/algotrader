import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchBacktestQueue } from '@/api/backtesterClient';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';
import type { BacktestQueueSnapshot } from '@/types/backtesterContracts';

vi.mock('@/api/backtesterClient', () => ({ fetchBacktestQueue: vi.fn() }));

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

  it('polls only while open and computes elapsed times from current clock', async () => {
    const wrapper = mount(BacktestQueueHealth);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-worker-status"]').text()).toContain('Worker healthy');
    expect(wrapper.find('[data-testid="workspace-queue-active"]').text()).toContain('active for 2m 0s');
    expect(wrapper.find('[data-testid="workspace-queue-run-waiting"]').text())
      .toContain('estimated position 1 · waiting 1m 0s');
    expect(wrapper.text()).toContain('no start time or ETA');

    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(wrapper.find('[data-testid="workspace-queue-active"]').text()).toContain('2m 5s');
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
    const wrapper = mount(BacktestQueueHealth);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-active"]').text())
      .toContain('Batch active-batch member #1');
    expect(wrapper.find('[data-testid="workspace-queue-batch-waiting-batch"]').text())
      .toContain('estimated position 1 · waiting 1m 0s');
    expect(wrapper.find('[data-testid="workspace-queue-batch-waiting-batch"]').text())
      .toContain('next member #3 · 1 succeeded, 1 failed');
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
    const wrapper = mount(BacktestQueueHealth);
    await flushPromises();
    expect(wrapper.text()).toContain('Worker unavailable');
    expect(wrapper.text()).toContain('No worker heartbeat recorded');
    expect(wrapper.find('[data-testid="workspace-queue-run-waiting"]').exists()).toBe(true);

    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.text()).toContain('Worker stale');
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.text()).toContain('Worker faulted');
    expect(wrapper.text()).toContain('Settlement failed');
    wrapper.unmount();
  });

  it('keeps last known context but marks failed and aged snapshots unknown', async () => {
    vi.mocked(fetchBacktestQueue).mockResolvedValueOnce(healthySnapshot)
      .mockRejectedValueOnce(new Error('Service unreachable'));
    const wrapper = mount(BacktestQueueHealth);
    await flushPromises();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-unknown"]').text())
      .toContain('Service unreachable');
    expect(wrapper.find('[data-testid="workspace-queue-active"]').text())
      .toContain('Last known active run');
    expect(wrapper.text()).toContain('Last known snapshot');

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

  it('ignores an older response after a newer refresh and after closing', async () => {
    let resolveFirst!: (snapshot: BacktestQueueSnapshot) => void;
    vi.mocked(fetchBacktestQueue)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce({ ...healthySnapshot, active_run: null, queued: [] });
    const wrapper = mount(BacktestQueueHealth);
    await flushPromises();
    await wrapper.vm.refresh();
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-no-active"]').exists()).toBe(true);
    resolveFirst(healthySnapshot);
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-queue-active"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
