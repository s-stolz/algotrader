import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import {
  CheckmarkCircleOutline,
  HourglassOutline,
  PauseOutline,
  PlayOutline,
  StopCircleOutline,
} from '@vicons/ionicons5';
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
  controlBacktestBatch,
  getBacktestBatch,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
} from '@/api/backtesterClient';
import type {
  BacktestBatch,
  BacktestBatchEvent,
  BacktestRun,
} from '@/types/backtesterContracts';

export function useBatchInspection(
  props: Readonly<{ batchId: string | null }>,
  callbacks: {
    members: (batchId: string, runs: BacktestRun[]) => void;
    cancelled: () => void;
  },
) {
  const workspaceStore = useBacktestWorkspaceStore();
  const selectedBatch = shallowRef<BacktestBatch | null>(null);
  const members = ref<BacktestRun[] | null>(null);
  const events = ref<BacktestBatchEvent[] | null>(null);
  const detailError = ref<string | null>(null);
  const controlError = ref<string | null>(null);
  const controlPending = ref(false);
  type BatchCommand = 'pause' | 'resume' | 'cancel';
  const commandIds: Partial<Record<BatchCommand, string>> = {};
  let detailRevision = 0;
  let isActive = false;
  let readPending = false;
  let timer: ReturnType<typeof setInterval> | null = null;

  const nowMs = ref(Date.now());
  let clockTimer: ReturnType<typeof setInterval> | null = null;
  const canPause = computed(() =>
    ['queued', 'running'].includes(selectedBatch.value?.status ?? ''),
  );
  const canControl = computed(() =>
    ['queued', 'running', 'pausing', 'paused'].includes(
      selectedBatch.value?.status ?? '',
    ),
  );
  const isTerminal = computed(() =>
    ['completed', 'cancelled'].includes(selectedBatch.value?.status ?? ''),
  );
  const selections = computed(
    () => selectedBatch.value?.accepted_definition.normalized_selections,
  );
  const progressPercent = computed(() => {
    const batch = selectedBatch.value;
    return batch?.total_count
      ? Math.floor((batch.settled_count / batch.total_count) * 100)
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
      count: selectedBatch.value?.outcome_counts[outcome.status] ?? 0,
    })),
  );
  const activeMember = computed(() =>
    selectedBatch.value?.active_member_ordinal == null
      ? null
      : members.value?.find(
          (member) =>
            member.member_ordinal ===
            selectedBatch.value?.active_member_ordinal,
        ),
  );
  const statusLabel = computed(() => {
    const batch = selectedBatch.value;
    if (!batch) return '';
    if (batch.status === 'completed' && batch.outcome_counts.failed > 0)
      return 'Completed with failures';
    return eventLabel(batch.status);
  });
  const activityMessage = computed(() => {
    const batch = selectedBatch.value;
    if (!batch) return '';
    if (detailError.value)
      return 'Live activity is unavailable. Retrying automatically.';
    switch (batch.status) {
      case 'queued':
        return 'Waiting for an execution slot.';
      case 'running':
        return batch.active_member_ordinal === null
          ? 'Waiting for the next run to start.'
          : `Running #${batch.active_member_ordinal + 1} of ${batch.total_count}`;
      case 'pausing':
        return 'Pausing after the active run finishes.';
      case 'paused':
        return 'Batch paused. Resume to continue queued runs.';
      case 'cancelling':
        return 'Stopping active execution. Cancellation will finish after cleanup.';
      case 'cancelled':
        return 'Batch cancelled. Previously completed results are still available.';
      case 'completed':
        return '';
    }
  });
  const activityIcon = computed(() => {
    switch (selectedBatch.value?.status) {
      case 'completed':
        return CheckmarkCircleOutline;
      case 'paused':
      case 'pausing':
        return PauseOutline;
      case 'cancelled':
      case 'cancelling':
        return StopCircleOutline;
      case 'running':
        return PlayOutline;
      default:
        return HourglassOutline;
    }
  });
  const elapsed = computed(() => {
    const batch = selectedBatch.value;
    if (batch?.started_at_ms == null) return '—';
    const seconds = Math.max(
      0,
      Math.floor(
        ((batch.completed_at_ms ?? nowMs.value) - batch.started_at_ms) / 1000,
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
      selectedBatch.value?.strategy_metadata.parameters.find(
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
      if (selectedBatch.value)
        selectedBatch.value = workspaceStore.preserveBatchName(
          selectedBatch.value,
          -1,
        );
    },
  );

  async function loadDetail(
    batchId: string,
    background = false,
  ): Promise<void> {
    if (!isActive || (background && readPending)) return;
    readPending = true;
    const revision = ++detailRevision;
    const nameReadRevision = workspaceStore.nameRevision;
    try {
      const [batch, loadedMembers, loadedEvents] = await Promise.all([
        getBacktestBatch(batchId),
        listBacktestBatchMembers(batchId),
        listBacktestBatchEvents(batchId),
      ]);
      if (revision !== detailRevision) return;
      for (const command of ['pause', 'resume', 'cancel'] as const) {
        const pending = commandIds[command];
        if (
          pending &&
          loadedEvents.some((event) => event.command_id === pending)
        ) {
          delete commandIds[command];
          controlError.value = null;
        }
      }
      detailError.value = null;
      selectedBatch.value = workspaceStore.preserveBatchName(
        batch,
        nameReadRevision,
      );
      members.value = loadedMembers;
      events.value = loadedEvents;
      callbacks.members(batchId, loadedMembers);
    } catch (error) {
      if (revision === detailRevision) {
        detailError.value =
          error instanceof Error ? error.message : 'Read failed';
      }
    } finally {
      if (revision === detailRevision) readPending = false;
    }
  }

  async function control(command: BatchCommand): Promise<void> {
    const batchId = props.batchId;
    if (!batchId || controlPending.value) return;
    controlPending.value = true;
    controlError.value = null;
    const pending = commandIds[command] ?? crypto.randomUUID();
    commandIds[command] = pending;
    try {
      await controlBacktestBatch(batchId, command, pending);
      if (props.batchId === batchId) {
        delete commandIds.pause;
        delete commandIds.resume;
        delete commandIds.cancel;
        await loadDetail(batchId);
        if (command === 'cancel') callbacks.cancelled();
      }
    } catch (error) {
      if (props.batchId === batchId) {
        controlError.value =
          error instanceof Error ? error.message : 'Batch command failed';
        await loadDetail(batchId);
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
    if (props.batchId) void loadDetail(props.batchId);
    timer = setInterval(() => {
      if (props.batchId) void loadDetail(props.batchId, true);
    }, 5000);
  }
  function stop(): void {
    isActive = false;
    ++detailRevision;
    readPending = false;
    if (timer) clearInterval(timer);
    timer = null;
    if (clockTimer) clearInterval(clockTimer);
    clockTimer = null;
  }
  onMounted(start);
  onActivated(start);
  onDeactivated(stop);
  watch(
    () => props.batchId,
    (batchId) => {
      ++detailRevision;
      readPending = false;
      detailError.value = null;
      selectedBatch.value = null;
      members.value = null;
      events.value = null;
      controlError.value = null;
      delete commandIds.pause;
      delete commandIds.resume;
      delete commandIds.cancel;
      if (batchId) void loadDetail(batchId);
    },
  );
  onUnmounted(stop);

  return {
    selectedBatch,
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
    activeMember,
    statusLabel,
    activityMessage,
    activityIcon,
    elapsed,
    formatTimestamp,
    eventLabel,
    parameterLabel,
    directionLabel,
    control,
  };
}
export type BatchInspection = ReturnType<typeof useBatchInspection>;
