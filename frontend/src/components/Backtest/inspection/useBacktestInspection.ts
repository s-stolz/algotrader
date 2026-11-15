import { terminalMembersIssue } from '@/types/backtest/heatmapSnapshot';
import { useBacktestEvents } from '@/utils/useBacktestEvents';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { HttpResponseError } from '@/api/http';
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
import {
  controlBacktest,
  getBacktest,
  listBacktestEvents,
  listBacktestMembers,
} from '@/api/backtesterClient';
import type {
  Backtest,
  BacktestEvent,
  BacktestRun,
} from '@/types/backtesterContracts';

export function useBacktestInspection(
  props: Readonly<{ backtestId: string | null }>,
  callbacks: {
    members: (backtestId: string, runs: BacktestRun[]) => void;
    cancelled: () => void;
    unavailable: (backtestId: string) => void;
  },
) {
  const workspaceStore = useBacktestWorkspaceStore();
  const selectedBacktest = shallowRef<Backtest | null>(null);
  const members = ref<BacktestRun[] | null>(null);
  const terminalSnapshot = shallowRef<{
    backtest: Backtest;
    runs: BacktestRun[];
  } | null>(null);
  const events = ref<BacktestEvent[] | null>(null);
  const membersError = ref<string | null>(null);
  const membersPending = ref(false);
  const detailError = ref<string | null>(null);
  const controlError = ref<string | null>(null);
  const controlPending = ref(false);
  type BacktestCommand = 'pause' | 'resume' | 'cancel';
  const commandIds: Partial<Record<BacktestCommand, string>> = {};
  let detailRevision = 0;
  let isActive = false;
  let readPending = false;
  let refreshAfterRead = false;

  const nowMs = ref(Date.now());
  let clockTimer: ReturnType<typeof setInterval> | null = null;
  const canPause = computed(() =>
    ['queued', 'running'].includes(selectedBacktest.value?.status ?? ''),
  );
  const canControl = computed(() =>
    ['queued', 'running', 'pausing', 'paused'].includes(
      selectedBacktest.value?.status ?? '',
    ),
  );
  const isTerminal = computed(() =>
    ['completed', 'cancelled'].includes(selectedBacktest.value?.status ?? ''),
  );
  const selections = computed(
    () => selectedBacktest.value?.accepted_definition.normalized_selections,
  );
  const progressPercent = computed(() => {
    const backtest = selectedBacktest.value;
    return backtest?.total_count
      ? Math.floor((backtest.settled_count / backtest.total_count) * 100)
      : 0;
  });
  const outcomes = computed(() =>
    (
      [
        { status: 'succeeded', label: 'Succeeded' },
        { status: 'failed', label: 'Failed' },
        { status: 'cancelled', label: 'Cancelled' },
        { status: 'running', label: 'Running' },
        { status: 'cancelling', label: 'Stopping' },
        { status: 'queued', label: 'Queued' },
      ] as const
    ).map((outcome) => ({
      ...outcome,
      count: selectedBacktest.value?.outcome_counts[outcome.status] ?? 0,
    })),
  );
  const statusLabel = computed(() => {
    const backtest = selectedBacktest.value;
    if (!backtest) return '';
    if (backtest.status === 'completed' && backtest.outcome_counts.failed > 0)
      return 'Completed with failures';
    return eventLabel(backtest.status);
  });
  const elapsed = computed(() => {
    const backtest = selectedBacktest.value;
    if (backtest?.started_at_ms == null) return '—';
    const seconds = Math.max(
      0,
      Math.floor(
        ((backtest.completed_at_ms ?? nowMs.value) - backtest.started_at_ms) /
          1000,
      ),
    );
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  });
  const timestampFormatter = new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: 'UTC',
  });
  function formatTimestamp(timestamp: number | null): string {
    return timestamp === null ? '—' : timestampFormatter.format(timestamp);
  }
  function eventLabel(value: string): string {
    const words = value.replaceAll('_', ' ');
    return words.charAt(0).toUpperCase() + words.slice(1);
  }
  function parameterLabel(name: string): string {
    return (
      selectedBacktest.value?.strategy_metadata.parameters.find(
        (parameter) => parameter.name === name,
      )?.display_name ?? eventLabel(name)
    );
  }
  function directionLabel(value: string): string {
    return (
      {
        long_only: 'Long only',
        short_only: 'Short only',
        long_and_short: 'Long and short',
      }[value] ?? value
    );
  }

  watch(
    () => workspaceStore.nameRevision,
    () => {
      if (selectedBacktest.value)
        selectedBacktest.value = workspaceStore.preserveBacktestName(
          selectedBacktest.value,
          -1,
        );
    },
  );

  async function loadDetail(
    backtestId: string,
    background = false,
  ): Promise<void> {
    if (!isActive) return;
    if (background && readPending) {
      refreshAfterRead = true;
      return;
    }
    readPending = true;
    membersPending.value = true;
    if (!background) {
      membersError.value = null;
      if (!selectedBacktest.value) detailError.value = null;
    }
    const revision = ++detailRevision;
    const nameReadRevision = workspaceStore.nameRevision;
    let isUnavailable = false;
    function reportReadFailure(
      error: unknown,
      target: 'detail' | 'members',
    ): never {
      if (
        revision === detailRevision &&
        !isUnavailable &&
        error instanceof HttpResponseError &&
        error.status === 404
      ) {
        isUnavailable = true;
        callbacks.unavailable(backtestId);
      }
      if (revision === detailRevision && !isUnavailable) {
        if (target === 'members') membersError.value = 'Couldn’t load runs';
        else detailError.value = 'Couldn’t load this backtest.';
      }
      throw error;
    }
    try {
      // A member read starts after the overview resolves. A newly terminal overview
      // can therefore never be paired with an earlier active member snapshot.
      const overviewRead = getBacktest(backtestId)
        .then((backtest) => {
          if (revision === detailRevision && !isUnavailable) {
            selectedBacktest.value = workspaceStore.preserveBacktestName(
              backtest,
              nameReadRevision,
            );
          }
          return backtest;
        })
        .catch((error) => reportReadFailure(error, 'detail'));
      const memberRead = overviewRead
        .catch(() => null)
        .then(() => {
          if (revision !== detailRevision || isUnavailable) return null;
          return listBacktestMembers(backtestId, false).catch((error) =>
            reportReadFailure(error, 'members'),
          );
        });
      const [backtestResult, membersResult, eventsResult] =
        await Promise.allSettled([
          overviewRead,
          memberRead,
          listBacktestEvents(backtestId).catch((error) =>
            reportReadFailure(error, 'detail'),
          ),
        ]);
      if (revision !== detailRevision || isUnavailable) return;
      if (backtestResult.status === 'fulfilled') {
        selectedBacktest.value = workspaceStore.preserveBacktestName(
          backtestResult.value,
          nameReadRevision,
        );
        detailError.value = null;
      } else {
        detailError.value = 'Couldn’t load this backtest.';
      }
      if (membersResult.status === 'fulfilled' && membersResult.value) {
        const terminalBacktest =
          backtestResult.status === 'fulfilled' &&
          ['completed', 'cancelled'].includes(backtestResult.value.status)
            ? backtestResult.value
            : null;
        const issue = terminalBacktest
          ? terminalMembersIssue(terminalBacktest, membersResult.value)
          : null;
        membersError.value =
          issue ?? (membersResult.value.length ? null : 'Couldn’t load runs');
        // Failed reconciliation must not discard established table/comparison membership.
        if (!issue || members.value === null) {
          members.value = membersResult.value;
          callbacks.members(backtestId, membersResult.value);
        }
        if (terminalBacktest && !issue)
          terminalSnapshot.value = {
            backtest: terminalBacktest,
            runs: membersResult.value,
          };
      } else {
        membersError.value = 'Couldn’t load runs';
      }
      if (eventsResult.status === 'fulfilled') {
        events.value = eventsResult.value;
        for (const command of ['pause', 'resume', 'cancel'] as const) {
          const pending = commandIds[command];
          if (
            pending &&
            eventsResult.value.some((event) => event.command_id === pending)
          ) {
            delete commandIds[command];
            controlError.value = null;
          }
        }
      } else {
        detailError.value = 'Couldn’t refresh this backtest.';
      }
    } catch (error) {
      if (revision === detailRevision && !isUnavailable) {
        detailError.value =
          error instanceof Error ? error.message : 'Read failed';
      }
    } finally {
      if (revision === detailRevision) {
        readPending = false;
        membersPending.value = false;
        if (refreshAfterRead && isActive && props.backtestId) {
          refreshAfterRead = false;
          void loadDetail(props.backtestId, true);
        }
      }
    }
  }

  let failedCommand: BacktestCommand | null = null;
  async function control(command: BacktestCommand): Promise<void> {
    const backtestId = props.backtestId;
    if (!backtestId || controlPending.value) return;
    controlPending.value = true;
    controlError.value = null;
    failedCommand = null;
    const pending = commandIds[command] ?? crypto.randomUUID();
    commandIds[command] = pending;
    try {
      await controlBacktest(backtestId, command, pending);
      if (props.backtestId === backtestId) {
        delete commandIds.pause;
        delete commandIds.resume;
        delete commandIds.cancel;
        await loadDetail(backtestId);
        if (command === 'cancel') callbacks.cancelled();
      }
    } catch (error) {
      if (props.backtestId === backtestId) {
        failedCommand = command;
        controlError.value =
          error instanceof Error ? error.message : 'Backtest command failed';
        await loadDetail(backtestId);
      }
    } finally {
      controlPending.value = false;
    }
  }

  function start(): void {
    if (isActive) return;
    isActive = true;
    nowMs.value = Date.now();
    clockTimer = setInterval(() => {
      nowMs.value = Date.now();
    }, 1000);
    if (props.backtestId) void loadDetail(props.backtestId);
  }
  function stop(): void {
    isActive = false;
    ++detailRevision;
    readPending = false;
    refreshAfterRead = false;
    if (clockTimer) clearInterval(clockTimer);
    clockTimer = null;
  }
  const { progress } = useBacktestEvents(() => {
    if (props.backtestId) void loadDetail(props.backtestId, true);
  });
  onMounted(start);
  onActivated(start);
  onDeactivated(stop);
  watch(
    () => props.backtestId,
    (backtestId) => {
      ++detailRevision;
      readPending = false;
      detailError.value = null;
      selectedBacktest.value = null;
      members.value = null;
      terminalSnapshot.value = null;
      refreshAfterRead = false;
      membersError.value = null;
      membersPending.value = false;
      failedCommand = null;
      events.value = null;
      controlError.value = null;
      delete commandIds.pause;
      delete commandIds.resume;
      delete commandIds.cancel;
      if (backtestId) void loadDetail(backtestId);
    },
  );
  onUnmounted(stop);

  return {
    selectedBacktest,
    terminalSnapshot,
    progress,
    membersError,
    membersPending,
    refresh: () =>
      props.backtestId ? loadDetail(props.backtestId) : Promise.resolve(),
    retryControl: () =>
      failedCommand ? control(failedCommand) : Promise.resolve(),
    members,
    events,
    detailError,
    controlError,
    controlPending,
    canPause,
    canControl,
    isTerminal,
    selections,
    progressPercent,
    outcomes,
    statusLabel,
    elapsed,
    formatTimestamp,
    eventLabel,
    parameterLabel,
    directionLabel,
    control,
  };
}
export type BacktestInspection = ReturnType<typeof useBacktestInspection>;
