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
  const POLL_INTERVAL_MS = 5000;
  const CLOCK_INTERVAL_MS = 1000;
  const snapshot = ref<BacktestQueueSnapshot | null>(null);
  const readError = ref<string | null>(null);
  const nowMs = ref(Date.now());
  const isUnknown = computed(
    () =>
      readError.value !== null ||
      (snapshot.value !== null &&
        nowMs.value - snapshot.value.snapshot_at_ms >
          snapshot.value.stale_after_ms),
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
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let clockTimer: ReturnType<typeof setInterval> | null = null;

  function elapsed(sinceMs: number): string {
    const seconds = Math.max(0, Math.floor((nowMs.value - sinceMs) / 1000));
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
    return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  }

  async function refresh(background = false): Promise<void> {
    if (!isActive || (background && readPending)) return;
    readPending = true;
    const request = ++generation;
    try {
      const latest = await fetchBacktestQueue();
      if (!isActive || request !== generation) return;
      snapshot.value = latest;
      readError.value = null;
      nowMs.value = Date.now();
    } catch (error) {
      if (!isActive || request !== generation) return;
      readError.value =
        error instanceof Error ? error.message : 'Queue read failed';
    } finally {
      if (request === generation) readPending = false;
    }
  }

  function start(): void {
    if (isActive) return;
    isActive = true;
    nowMs.value = Date.now();
    void refresh();
    pollTimer = setInterval(() => {
      void refresh(true);
    }, POLL_INTERVAL_MS);
    clockTimer = setInterval(() => {
      nowMs.value = Date.now();
    }, CLOCK_INTERVAL_MS);
  }

  function stop(): void {
    isActive = false;
    ++generation;
    readPending = false;
    if (pollTimer) clearInterval(pollTimer);
    if (clockTimer) clearInterval(clockTimer);
    pollTimer = null;
    clockTimer = null;
  }

  onMounted(start);
  onActivated(start);
  onDeactivated(stop);
  onUnmounted(stop);
  return { snapshot, readError, isUnknown, healthType, elapsed, refresh };
}
