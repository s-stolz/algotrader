<template>
  <section
    v-if="visible"
    class="floating-pill"
    aria-label="Backtest queue"
    data-testid="workspace-queue"
  >
    <BasePopover
      v-model:show="expanded"
      trigger="click"
      placement="top-end"
      :show-arrow="false"
      :width="380"
      :style="{ maxWidth: 'calc(100vw - 32px)' }"
    >
      <template #trigger>
        <button
          ref="trigger"
          class="status-pill"
          :class="{ 'pill-warning': isUnknown || needsAttention }"
          :aria-expanded="expanded"
          :aria-controls="panelId"
          :aria-label="`Backtest activity: ${pillStatus}, ${waitingLabel}`"
          data-testid="queue-toggle"
          @keydown.esc.stop="close"
        >
          <span
            class="status-dot"
            :class="{
              muted: isUnknown || !snapshot?.active_run,
              amber: needsAttention && !isUnknown,
            }"
          />
          <strong>{{ pillStatus }}</strong
          ><span class="pill-divider" />
          <span class="secondary">{{ waitingLabel }}</span>
          <n-icon
            class="pill-chevron"
            :class="{ 'is-expanded': expanded }"
            :size="16"
            aria-hidden="true"
            ><ChevronUpOutline
          /></n-icon>
        </button>
      </template>
      <section
        :id="panelId"
        class="activity-panel"
        aria-label="Backtest activity details"
        @keydown.esc.stop="close"
      >
        <div class="list-heading"
          ><h3>Experiments</h3
          ><n-button
            text
            aria-label="Close activity details"
            @click="close"
            ><n-icon :size="16"><CloseOutline /></n-icon></n-button
        ></div>
        <n-skeleton
          v-if="!snapshot && !readError"
          text
          :repeat="2"
          aria-label="Loading backtest activity"
        />
        <n-alert
          v-if="isUnknown"
          type="warning"
          class="activity-alert"
          data-testid="workspace-queue-unknown"
        >
          {{
            readError
              ? `Activity unavailable: ${readError}`
              : 'Activity status unknown: latest snapshot is old.'
          }}
          <template v-if="snapshot"> Showing last known activity.</template>
          <n-button
            size="small"
            @click="refresh()"
            >Retry</n-button
          >
        </n-alert>
        <template v-if="snapshot">
          <n-alert
            v-if="needsAttention"
            type="warning"
            class="activity-alert"
            data-testid="workspace-worker-status"
            >{{ isUnknown ? 'Last known worker status' : 'Worker' }}:
            {{ snapshot.availability }}. Waiting work may not start.</n-alert
          >
          <n-alert
            v-for="fault in snapshot.operational_faults"
            :key="fault.code"
            type="error"
            class="activity-alert"
            :title="fault.message"
            ><code>{{ fault.code }}</code></n-alert
          >
          <div
            class="active-run"
            data-testid="workspace-queue-active-section"
          >
            <span class="eyebrow">{{
              isUnknown ? 'Last known running' : 'Running'
            }}</span>
            <button
              v-if="snapshot.active_run"
              class="experiment-entry"
              data-testid="queue-view-active"
              @click="
                inspect(
                  snapshot.active_run.batch_id ? 'batch' : 'run',
                  snapshot.active_run.batch_id ?? snapshot.active_run.run_id,
                )
              "
            >
              <strong data-testid="workspace-queue-active"
                >{{ activeName }} →</strong
              >
              <span
                class="secondary"
                v-if="activeBatch"
                >{{ activeBatch.settled_count }} /
                {{ activeBatch.total_count }} finished<template
                  v-if="activeBatch.outcome_counts.failed"
                >
                  · {{ activeBatch.outcome_counts.failed }} failed</template
                ></span
              >
              <span
                v-else-if="!snapshot.active_run.batch_id"
                class="secondary"
                >{{ isUnknown ? 'Started' : 'Active for' }}
                {{ elapsed(snapshot.active_run.started_at_ms)
                }}{{ isUnknown ? ' ago' : '' }}</span
              >
              <progress
                v-if="activeBatch"
                :value="activeBatch.settled_count"
                :max="activeBatch.total_count"
                aria-label="Finished runs"
              />
              <small v-if="snapshot.active_run.batch_id"
                >{{
                  isUnknown ? 'Last known running' : 'Currently running'
                }}
                #{{ (snapshot.active_run.member_ordinal ?? 0) + 1 }}</small
              >
            </button>
            <p
              v-else
              class="secondary"
              data-testid="workspace-queue-no-active"
              >{{
                isUnknown
                  ? 'Last known active run: none'
                  : 'No backtests running'
              }}</p
            >
          </div>
          <span class="eyebrow"
            >{{ isUnknown ? 'Last known queue' : 'Waiting' }} ·
            {{ snapshot.queued.length }}</span
          >
          <ol
            v-if="snapshot.queued.length"
            aria-label="Waiting backtests"
          >
            <li
              v-for="entry in snapshot.queued"
              :key="`${entryIdentity(entry).kind}:${entryIdentity(entry).id}`"
              :data-testid="entryTestId(entry)"
            >
              <button
                class="experiment-entry"
                @click="
                  inspect(entryIdentity(entry).kind, entryIdentity(entry).id)
                "
              >
                <strong
                  >{{
                    experimentName(
                      entryIdentity(entry).kind,
                      entryIdentity(entry).id,
                    )
                  }}
                  →</strong
                >
                <small v-if="entry.outcome_counts"
                  >{{
                    Object.values(entry.outcome_counts).reduce(
                      (sum, count) => sum + count,
                      0,
                    )
                  }}
                  runs ·
                  {{ finishedCount(entry.outcome_counts) }} finished<template
                    v-if="entry.outcome_counts.failed"
                  >
                    · {{ entry.outcome_counts.failed }} failed</template
                  ></small
                >
                <small v-else
                  >Single backtest · waiting
                  {{ elapsed(entry.submitted_at_ms) }}</small
                >
              </button>
            </li>
          </ol>
          <p
            v-else
            class="secondary"
            data-testid="workspace-queue-empty"
            >{{
              isUnknown
                ? 'Last known queue had no waiting work.'
                : 'No waiting work.'
            }}</p
          >
          <template v-if="recentExperiments.length">
            <span class="eyebrow">Recently finished</span>
            <ol aria-label="Recently finished experiments">
              <li
                v-for="entry in recentExperiments"
                :key="`${entry.kind}:${entry.id}`"
              >
                <button
                  class="experiment-entry"
                  @click="inspect(entry.kind, entry.id)"
                >
                  <strong>{{ experimentName(entry.kind, entry.id) }} →</strong>
                  <small>{{ entry.summary }}</small>
                </button>
              </li>
            </ol>
          </template>
        </template>
      </section>
    </BasePopover>
  </section>
</template>

<script setup lang="ts">
import { NAlert, NButton, NIcon, NSkeleton } from 'naive-ui';
import { ChevronUpOutline, CloseOutline } from '@vicons/ionicons5';
import {
  computed,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  ref,
  useId,
} from 'vue';
import BasePopover from '@/components/Common/BasePopover.vue';
import { useBacktestQueueHealth } from './useBacktestQueueHealth';
import type {
  BacktestBatch,
  BacktestRun,
  BacktestQueueEntry,
} from '@/types/backtesterContracts';
import { batchName, runName } from '@/views/backtestWorkspaceRuns';

const props = defineProps<{
  runs?: BacktestRun[] | null;
  batches?: BacktestBatch[] | null;
}>();
const emit = defineEmits<{ inspect: [kind: 'run' | 'batch', id: string] }>();
const expanded = ref(false);
const visible = ref(true);
const trigger = ref<HTMLButtonElement | null>(null);
const panelId = useId();
const { snapshot, readError, nowMs, isUnknown, elapsed, refresh } =
  useBacktestQueueHealth();
const needsAttention = computed(
  () =>
    snapshot.value !== null &&
    (snapshot.value.availability !== 'healthy' ||
      snapshot.value.operational_faults.length > 0),
);
const pillStatus = computed(() =>
  isUnknown.value
    ? 'Status unknown'
    : !snapshot.value
      ? 'Connecting'
      : needsAttention.value
        ? 'Needs attention'
        : snapshot.value.active_run
          ? '1 running'
          : 'Idle',
);
const waitingLabel = computed(() =>
  !snapshot.value
    ? 'Queue unknown'
    : `${isUnknown.value ? 'Last known: ' : ''}${snapshot.value.queued.length} waiting`,
);
const activeName = computed(() => {
  const active = snapshot.value?.active_run;
  return active
    ? experimentName(
        active.batch_id ? 'batch' : 'run',
        active.batch_id ?? active.run_id,
      )
    : '';
});
const activeBatch = computed(() =>
  props.batches?.find(
    (batch) => batch.batch_id === snapshot.value?.active_run?.batch_id,
  ),
);
function finishedCount(counts: BacktestBatch['outcome_counts']): number {
  return counts.succeeded + counts.failed + counts.cancelled;
}
const recentExperiments = computed(() => {
  const entries = [
    ...(props.runs ?? [])
      .filter(
        (run) =>
          !run.batch_id &&
          ['succeeded', 'failed', 'cancelled'].includes(run.status),
      )
      .map((run) => ({
        kind: 'run' as const,
        id: run.run_id,
        completedAt: run.completed_at_ms,
        summary:
          run.status === 'succeeded'
            ? 'Completed'
            : run.status === 'failed'
              ? 'Failed'
              : 'Cancelled',
      })),
    ...(props.batches ?? [])
      .filter((batch) => ['completed', 'cancelled'].includes(batch.status))
      .map((batch) => ({
        kind: 'batch' as const,
        id: batch.batch_id,
        completedAt: batch.completed_at_ms,
        summary: `${batch.settled_count} / ${batch.total_count} finished · ${
          batch.status === 'cancelled' ? 'Cancelled' : 'Completed'
        }${batch.outcome_counts.failed ? ` · ${batch.outcome_counts.failed} failed` : ''}`,
      })),
  ];
  // Keep fast runs discoverable even when they finish between queue polls.
  return entries
    .filter(
      (entry) =>
        entry.completedAt != null &&
        nowMs.value - entry.completedAt < 60_000 &&
        entry.completedAt <= nowMs.value &&
        !(entry.kind === 'batch'
          ? snapshot.value?.active_run?.batch_id === entry.id
          : snapshot.value?.active_run?.run_id === entry.id) &&
        !snapshot.value?.queued.some(
          (queued) =>
            entryIdentity(queued).kind === entry.kind &&
            entryIdentity(queued).id === entry.id,
        ),
    )
    .sort((a, b) => b.completedAt! - a.completedAt!)
    .slice(0, 3);
});
function experimentName(kind: 'run' | 'batch', id: string): string {
  if (kind === 'batch') {
    const batch = props.batches?.find((item) => item.batch_id === id);
    return batch ? batchName(batch) : `Batch ${id}`;
  }
  const run = props.runs?.find((item) => item.run_id === id);
  return run ? runName(run) : `Run ${id}`;
}
function entryTestId(entry: BacktestQueueEntry): string {
  const { kind, id } = entryIdentity(entry);
  return `workspace-queue-${kind}-${id}`;
}
function entryIdentity(entry: BacktestQueueEntry): {
  kind: 'run' | 'batch';
  id: string;
} {
  return entry.entry_type === 'batch'
    ? { kind: 'batch', id: entry.batch_id! }
    : { kind: 'run', id: entry.run_id! };
}
function close(): void {
  expanded.value = false;
  trigger.value?.focus();
}
function inspect(kind: 'run' | 'batch', id: string): void {
  close();
  emit('inspect', kind, id);
}
function show(): void {
  visible.value = true;
}
function hide(): void {
  visible.value = false;
  expanded.value = false;
}
defineExpose({ refresh });
onMounted(show);
onActivated(show);
onDeactivated(hide);
onUnmounted(hide);
</script>

<style scoped src="./backtestQueueHealth.css"></style>
