import { useBacktestEvents } from '@/utils/useBacktestEvents';
import type { BacktestHealthMessage } from '@/types/backtestEventContracts';
import {
  computed,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  ref,
} from 'vue';

import { fetchBacktestQueue } from '@/api/backtesterClient';
import type { BacktestQueueSnapshot } from '@/types/backtesterContracts';

export function useBacktestQueueHealth() {
  const CLOCK_INTERVAL_MS = 1000;
  const snapshot = ref<BacktestQueueSnapshot | null>(null);
  const requestError = ref<string | null>(null);
  const receivedAtMs = ref(Date.now());
  const { connected } = useBacktestEvents(() => {
    void refresh(true);
  }, receiveHealth);
  const readError = computed(
    () =>
      requestError.value ??
      (connected.value ? null : 'Live updates disconnected'),
  );
  const nowMs = ref(Date.now());
  const isUnknown = computed(
    () =>
      readError.value !== null ||
      (snapshot.value !== null &&
        nowMs.value - receivedAtMs.value > snapshot.value.stale_after_ms),
  );
  const healthType = computed(() => {
    if (isUnknown.value) return 'warning';
    if (snapshot.value?.availability === 'healthy') return 'success';
    if (snapshot.value?.availability === 'faulted') return 'error';
    return snapshot.value ? 'warning' : 'default';
  });
  let generation = 0;
  let readPending = false;
  let isActive = false;
  let refreshAfterRead = false;
  let clockTimer: ReturnType<typeof setInterval> | null = null;

  function elapsed(sinceMs: number): string {
    const seconds = Math.max(0, Math.floor((nowMs.value - sinceMs) / 1000));
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
    return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  }

  async function refresh(background = false): Promise<void> {
    if (!isActive) return;
    if (background && readPending) {
      refreshAfterRead = true;
      return;
    }
    readPending = true;
    const request = ++generation;
    const requestedAtMs = Date.now();
    try {
      const latest = await fetchBacktestQueue();
      if (!isActive || request !== generation) return;
      snapshot.value = latest;
      requestError.value = null;
      receivedAtMs.value = requestedAtMs;
      nowMs.value = Date.now();
    } catch (error) {
      if (!isActive || request !== generation) return;
      requestError.value =
        error instanceof Error ? error.message : 'Queue read failed';
    } finally {
      if (request === generation) {
        readPending = false;
        if (refreshAfterRead && isActive) {
          refreshAfterRead = false;
          void refresh(true);
        }
      }
    }
  }

  function receiveHealth(message: BacktestHealthMessage): void {
    const current = snapshot.value;
    if (
      !current ||
      (current.active_run?.run_id ?? null) !== message.run_id ||
      message.heartbeat_at_ms <= (current.last_heartbeat_ms ?? 0)
    )
      return;
    // Older queued health messages must not establish fresh evidence on delivery.
    const serverNow = current.snapshot_at_ms + Date.now() - receivedAtMs.value;
    const age = Math.max(0, serverNow - message.heartbeat_at_ms);
    if (age > current.stale_after_ms) return;
    const faults = current.operational_faults.filter(
      (fault) => !['heartbeat_absent', 'heartbeat_stale'].includes(fault.code),
    );
    if (message.fault_code)
      faults.push({
        code: message.fault_code,
        message: message.fault_message ?? 'Worker is faulted',
      });
    snapshot.value = {
      ...current,
      snapshot_at_ms: message.heartbeat_at_ms,
      last_heartbeat_ms: message.heartbeat_at_ms,
      operational_faults: faults,
      availability: faults.length ? 'faulted' : 'healthy',
    };
    receivedAtMs.value = Date.now() - age;
    nowMs.value = Date.now();
  }

  function start(): void {
    if (isActive) return;
    isActive = true;
    nowMs.value = Date.now();
    void refresh();

    clockTimer = setInterval(() => {
      nowMs.value = Date.now();
    }, CLOCK_INTERVAL_MS);
  }

  function stop(): void {
    isActive = false;
    ++generation;
    readPending = false;
    if (clockTimer) clearInterval(clockTimer);
    refreshAfterRead = false;
    clockTimer = null;
  }

  onMounted(start);
  onActivated(start);
  onDeactivated(stop);
  onUnmounted(stop);
  return {
    snapshot,
    readError,
    nowMs,
    isUnknown,
    healthType,
    elapsed,
    refresh,
  };
}
