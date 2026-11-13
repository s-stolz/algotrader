import { useBacktestEvents } from '@/utils/useBacktestEvents';
import type { BacktestHealthMessage } from '@/types/backtestEventContracts';
import {
  computed,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
  watch,
} from 'vue';

import { fetchBacktestQueue, getBacktest } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import type { Backtest } from '@/types/backtesterContracts';
import type { BacktestQueueSnapshot } from '@/types/backtesterContracts';

export function useBacktestActivity() {
  const workspaceStore = useBacktestWorkspaceStore();
  const backtests = shallowRef<Backtest[]>([]);
  const isRefreshing = ref(false);
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
  const isUnknown = computed(() => {
    if (readError.value !== null) return true;
    const current = snapshot.value;
    if (!current) return false;
    // A healthy snapshot cannot renew the heartbeat it reports. Keep its clock
    // anchor separate so later WebSocket messages retain their actual age.
    const heartbeatAge =
      current.availability === 'healthy' && current.last_heartbeat_ms !== null
        ? Math.max(0, current.snapshot_at_ms - current.last_heartbeat_ms)
        : 0;
    return (
      heartbeatAge + nowMs.value - receivedAtMs.value > current.stale_after_ms
    );
  });
  let generation = 0;
  let readPending = false;
  let isActive = false;
  let refreshAfterRead = false;
  let clockTimer: ReturnType<typeof setInterval> | null = null;

  async function loadActivityDetails(
    latest: BacktestQueueSnapshot,
    revision: number,
  ) {
    const ids = [
      ...new Set([
        ...(latest.active_run ? [latest.active_run.backtest_id] : []),
        ...latest.queued.map((entry) => entry.backtest_id),
      ]),
    ];
    const nameRevision = workspaceStore.nameRevision;
    const results = await Promise.allSettled(ids.map((id) => getBacktest(id)));
    if (!isActive || revision !== generation) return;
    backtests.value = results.flatMap((result) =>
      result.status === 'fulfilled'
        ? [workspaceStore.preserveBacktestName(result.value, nameRevision)]
        : [],
    );
  }
  watch(
    () => workspaceStore.nameRevision,
    () => {
      backtests.value = backtests.value.map((backtest) =>
        workspaceStore.preserveBacktestName(backtest, -1),
      );
    },
  );

  async function refresh(background = false): Promise<void> {
    if (!isActive) return;
    if (background && readPending) {
      refreshAfterRead = true;
      return;
    }
    readPending = true;
    isRefreshing.value = true;
    const request = ++generation;
    const requestedAtMs = Date.now();
    try {
      const latest = await fetchBacktestQueue();
      if (!isActive || request !== generation) return;
      snapshot.value = latest;
      void loadActivityDetails(latest, request);
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
        isRefreshing.value = false;
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
    isRefreshing.value = false;
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
    backtests,
    connected,
    isRefreshing,
    readError,
    isUnknown,
    refresh,
  };
}
