import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { fetchBacktestQueue } from '@/api/backtesterClient';
import { useBacktestQueueHealth } from '@/components/Backtest/useBacktestQueueHealth';
import {
  emitBacktestEvent,
  installBacktestSocket,
} from '../../backtestEventSocket';
import { healthySnapshot, NOW } from './backtestQueueFixtures';

vi.mock('@/api/backtesterClient', () => ({ fetchBacktestQueue: vi.fn() }));
const Host = defineComponent({
  setup: useBacktestQueueHealth,
  template: '<div />',
});

describe('queue health events', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    installBacktestSocket();
    vi.mocked(fetchBacktestQueue)
      .mockReset()
      .mockResolvedValue(healthySnapshot);
  });
  afterEach(() => vi.useRealTimers());

  it.each([0, -120_000, 120_000])(
    'expires an aged heartbeat with browser clock offset %i',
    async (clockOffset) => {
      vi.setSystemTime(NOW + clockOffset);
      vi.mocked(fetchBacktestQueue).mockResolvedValue({
        ...healthySnapshot,
        last_heartbeat_ms: NOW - 29_000,
      });
      const host = mount(Host);
      await flushPromises();
      expect(host.vm.healthType).toBe('success');
      vi.advanceTimersByTime(2000);
      expect(host.vm.isUnknown).toBe(true);
      expect(host.vm.healthType).toBe('warning');
      expect(fetchBacktestQueue).toHaveBeenCalledOnce();
      host.unmount();
    },
  );

  it('ages delayed health events against the snapshot clock', async () => {
    vi.mocked(fetchBacktestQueue).mockResolvedValue({
      ...healthySnapshot,
      last_heartbeat_ms: NOW - 29_000,
    });
    const host = mount(Host);
    await flushPromises();
    vi.advanceTimersByTime(2000);
    emitBacktestEvent({
      type: 'backtestHealth',
      run_id: 'long-run',
      heartbeat_at_ms: NOW - 10_000,
      fault_code: null,
      fault_message: null,
    });
    expect(host.vm.isUnknown).toBe(false);
    vi.advanceTimersByTime(19_000);
    expect(host.vm.isUnknown).toBe(true);
    emitBacktestEvent({
      type: 'backtestHealth',
      run_id: 'long-run',
      heartbeat_at_ms: NOW + 21_000,
      fault_code: null,
      fault_message: null,
    });
    expect(host.vm.isUnknown).toBe(false);
    expect(fetchBacktestQueue).toHaveBeenCalledOnce();
    host.unmount();
  });

  it('keeps health fresh from matching heartbeats without reading the queue again', async () => {
    const host = mount(Host);
    await flushPromises();
    for (let index = 0; index < 10; index++) {
      vi.advanceTimersByTime(5000);
      emitBacktestEvent({
        type: 'backtestHealth',
        run_id: 'long-run',
        heartbeat_at_ms: Date.now(),
        fault_code: null,
        fault_message: null,
      });
    }
    expect(fetchBacktestQueue).toHaveBeenCalledOnce();
    expect(host.vm.isUnknown).toBe(false);
    vi.advanceTimersByTime(31000);
    expect(host.vm.isUnknown).toBe(true);
    host.unmount();
  });

  it('ignores health from another worker or an old replay', async () => {
    const host = mount(Host);
    await flushPromises();
    vi.advanceTimersByTime(31000);
    emitBacktestEvent({
      type: 'backtestHealth',
      run_id: null,
      heartbeat_at_ms: Date.now(),
      fault_code: null,
      fault_message: null,
    });
    expect(host.vm.isUnknown).toBe(true);
    emitBacktestEvent({
      type: 'backtestHealth',
      run_id: 'long-run',
      heartbeat_at_ms: NOW,
      fault_code: null,
      fault_message: null,
    });
    expect(host.vm.isUnknown).toBe(true);
    host.unmount();
  });

  it('keeps saved data offline and refreshes on reconnection', async () => {
    const host = mount(Host);
    await flushPromises();
    emitBacktestEvent({ type: 'backtestConnection', connected: false });
    expect(host.vm.readError).toBe('Live updates disconnected');
    expect(host.vm.snapshot?.active_run?.run_id).toBe('long-run');
    emitBacktestEvent({ type: 'backtestConnection', connected: true });
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(host.vm.isUnknown).toBe(false);
    host.unmount();
  });
});
