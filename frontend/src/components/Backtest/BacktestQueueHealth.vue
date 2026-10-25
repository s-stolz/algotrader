<template>
  <section v-if="visible" class="floating-pill" aria-label="Backtest queue" data-testid="workspace-queue">
    <BasePopover v-model:show="expanded" trigger="click" placement="top-end" :show-arrow="false" :width="380" :style="{ maxWidth: 'calc(100vw - 32px)' }">
      <template #trigger>
        <button ref="trigger" class="status-pill" :class="{ 'pill-warning': isUnknown || needsAttention }" :aria-expanded="expanded" :aria-controls="panelId" :aria-label="`Backtest activity: ${pillStatus}, ${waitingLabel}`" data-testid="queue-toggle" @keydown.esc.stop="close">
          <span class="status-dot" :class="{ muted: isUnknown || !snapshot?.active_run, amber: needsAttention && !isUnknown }" />
          <strong>{{ pillStatus }}</strong><span class="pill-divider" />
          <span class="secondary">{{ waitingLabel }}</span>
          <n-icon class="pill-chevron" :class="{ 'is-expanded': expanded }" :size="16" aria-hidden="true"><ChevronUpOutline /></n-icon>
        </button>
      </template>
      <section :id="panelId" class="activity-panel" aria-label="Backtest activity details" @keydown.esc.stop="close">
        <div class="list-heading"><h3>Experiments</h3><n-button text aria-label="Close activity details" @click="close"><n-icon :size="16"><CloseOutline /></n-icon></n-button></div>
        <n-skeleton v-if="!snapshot && !readError" text :repeat="2" aria-label="Loading backtest activity" />
        <n-alert v-if="isUnknown" type="warning" class="activity-alert" data-testid="workspace-queue-unknown">
          {{ readError ? `Activity unavailable: ${readError}` : 'Activity status unknown: latest snapshot is old.' }}
          <template v-if="snapshot"> Showing last known activity.</template>
          <n-button size="small" @click="refresh()">Retry</n-button>
        </n-alert>
        <template v-if="snapshot">
          <n-alert v-if="needsAttention" type="warning" class="activity-alert" data-testid="workspace-worker-status">{{ isUnknown ? 'Last known worker status' : 'Worker' }}: {{ snapshot.availability }}. Waiting work may not start.</n-alert>
          <n-alert v-for="fault in snapshot.operational_faults" :key="fault.code" type="error" class="activity-alert" :title="fault.message"><code>{{ fault.code }}</code></n-alert>
          <div class="active-run" data-testid="workspace-queue-active-section">
            <span class="eyebrow">{{ isUnknown ? 'Last known running' : 'Running' }}</span>
            <button v-if="snapshot.active_run" class="experiment-entry" data-testid="queue-view-active" @click="inspect(snapshot.active_run.batch_id ? 'batch' : 'run', snapshot.active_run.batch_id ?? snapshot.active_run.run_id)">
              <strong data-testid="workspace-queue-active">{{ activeName }} →</strong>
              <span class="secondary" v-if="activeBatch">{{ activeBatch.settled_count }} / {{ activeBatch.total_count }} finished<template v-if="activeBatch.outcome_counts.failed"> · {{ activeBatch.outcome_counts.failed }} failed</template></span>
              <span v-else-if="!snapshot.active_run.batch_id" class="secondary">{{ isUnknown ? 'Started' : 'Active for' }} {{ elapsed(snapshot.active_run.started_at_ms) }}{{ isUnknown ? ' ago' : '' }}</span>
              <progress v-if="activeBatch" :value="activeBatch.settled_count" :max="activeBatch.total_count" aria-label="Finished runs" />
              <small v-if="snapshot.active_run.batch_id">{{ isUnknown ? 'Last known running' : 'Currently running' }} #{{ (snapshot.active_run.member_ordinal ?? 0) + 1 }}</small>
            </button>
            <p v-else class="secondary" data-testid="workspace-queue-no-active">{{ isUnknown ? 'Last known active run: none' : 'No backtests running' }}</p>
          </div>
          <span class="eyebrow">{{ isUnknown ? 'Last known queue' : 'Waiting' }} · {{ snapshot.queued.length }}</span>
          <ol v-if="snapshot.queued.length" aria-label="Waiting backtests">
            <li v-for="entry in snapshot.queued" :key="`${entryIdentity(entry).kind}:${entryIdentity(entry).id}`" :data-testid="`workspace-queue-${entryIdentity(entry).kind}-${entryIdentity(entry).id}`">
              <button class="experiment-entry" @click="inspect(entryIdentity(entry).kind, entryIdentity(entry).id)">
                <strong>{{ experimentName(entryIdentity(entry).kind, entryIdentity(entry).id) }} →</strong>
                <small v-if="entry.outcome_counts">{{ Object.values(entry.outcome_counts).reduce((sum, count) => sum + count, 0) }} runs · {{ finishedCount(entry.outcome_counts) }} finished<template v-if="entry.outcome_counts.failed"> · {{ entry.outcome_counts.failed }} failed</template></small>
                <small v-else>Single backtest · waiting {{ elapsed(entry.submitted_at_ms) }}</small>
              </button>
            </li>
          </ol>
          <p v-else class="secondary" data-testid="workspace-queue-empty">{{ isUnknown ? 'Last known queue had no waiting work.' : 'No waiting work.' }}</p>
          <template v-if="recentExperiments.length">
            <span class="eyebrow">Recently finished</span>
            <ol aria-label="Recently finished experiments">
              <li v-for="entry in recentExperiments" :key="`${entry.kind}:${entry.id}`">
                <button class="experiment-entry" @click="inspect(entry.kind, entry.id)">
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
import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref, useId } from 'vue';
import BasePopover from '@/components/Common/BasePopover.vue';
import { fetchBacktestQueue } from '@/api/backtesterClient';
import type { BacktestBatch, BacktestRun, BacktestQueueEntry, BacktestQueueSnapshot } from '@/types/backtesterContracts';
import { batchName, runName } from '@/views/backtestWorkspaceRuns';

const props = defineProps<{ runs?: BacktestRun[] | null; batches?: BacktestBatch[] | null }>();
const emit = defineEmits<{ inspect: [kind: 'run' | 'batch', id: string] }>();
const expanded = ref(false);
const visible = ref(true);
const trigger = ref<HTMLButtonElement | null>(null);
const panelId = useId();
const POLL_INTERVAL_MS = 5000;
const CLOCK_INTERVAL_MS = 1000;
const snapshot = ref<BacktestQueueSnapshot | null>(null);
const readError = ref<string | null>(null);
const nowMs = ref(Date.now());
const isUnknown = computed(() => readError.value !== null ||
  (snapshot.value !== null && nowMs.value - snapshot.value.snapshot_at_ms >
    snapshot.value.stale_after_ms));
const needsAttention = computed(() => snapshot.value !== null &&
  (snapshot.value.availability !== 'healthy' || snapshot.value.operational_faults.length > 0));
const pillStatus = computed(() => isUnknown.value ? 'Status unknown' : !snapshot.value ? 'Connecting' :
  needsAttention.value ? 'Needs attention' : snapshot.value.active_run ? '1 running' : 'Idle');
const waitingLabel = computed(() => !snapshot.value ? 'Queue unknown' :
  `${isUnknown.value ? 'Last known: ' : ''}${snapshot.value.queued.length} waiting`);
const activeName = computed(() => {
  const active = snapshot.value?.active_run;
  return active ? experimentName(active.batch_id ? 'batch' : 'run', active.batch_id ?? active.run_id) : '';
});
const activeBatch = computed(() => props.batches?.find(batch => batch.batch_id === snapshot.value?.active_run?.batch_id));
function finishedCount(counts: BacktestBatch['outcome_counts']): number {
  return counts.succeeded + counts.failed + counts.cancelled;
}
const recentExperiments = computed(() => {
  const entries = [
    ...(props.runs ?? []).filter(run => !run.batch_id && ['succeeded', 'failed', 'cancelled'].includes(run.status)).map(run => ({
      kind: 'run' as const, id: run.run_id, completedAt: run.completed_at_ms,
      summary: run.status === 'succeeded' ? 'Completed' : run.status === 'failed' ? 'Failed' : 'Cancelled',
    })),
    ...(props.batches ?? []).filter(batch => ['completed', 'cancelled'].includes(batch.status)).map(batch => ({
      kind: 'batch' as const, id: batch.batch_id, completedAt: batch.completed_at_ms,
      summary: `${batch.settled_count} / ${batch.total_count} finished · ${batch.status === 'cancelled' ? 'Cancelled' : 'Completed'}${batch.outcome_counts.failed ? ` · ${batch.outcome_counts.failed} failed` : ''}`,
    })),
  ];
  // Keep fast runs discoverable even when they finish between queue polls.
  return entries.filter(entry => entry.completedAt != null && nowMs.value - entry.completedAt < 60_000 &&
    entry.completedAt <= nowMs.value &&
    !(entry.kind === 'batch' ? snapshot.value?.active_run?.batch_id === entry.id : snapshot.value?.active_run?.run_id === entry.id) &&
    !snapshot.value?.queued.some(queued => entryIdentity(queued).kind === entry.kind && entryIdentity(queued).id === entry.id))
    .sort((a, b) => b.completedAt! - a.completedAt!).slice(0, 3);
});
function experimentName(kind: 'run' | 'batch', id: string): string {
  if (kind === 'batch') {
    const batch = props.batches?.find((item) => item.batch_id === id);
    return batch ? batchName(batch) : `Batch ${id}`;
  }
  const run = props.runs?.find((item) => item.run_id === id);
  return run ? runName(run) : `Run ${id}`;
}
function entryIdentity(entry: BacktestQueueEntry): { kind: 'run' | 'batch'; id: string } {
  return entry.entry_type === 'batch' ? { kind: 'batch', id: entry.batch_id! } : { kind: 'run', id: entry.run_id! };
}
function close(): void {
  expanded.value = false;
  trigger.value?.focus();
}
function inspect(kind: 'run' | 'batch', id: string): void {
  close();
  emit('inspect', kind, id);
}
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
    readError.value = error instanceof Error ? error.message : 'Queue read failed';
  } finally {
    if (request === generation) readPending = false;
  }
}

function start(): void {
  if (isActive) return;
  isActive = true;
  visible.value = true;
  nowMs.value = Date.now();
  void refresh();
  pollTimer = setInterval(() => { void refresh(true); }, POLL_INTERVAL_MS);
  clockTimer = setInterval(() => { nowMs.value = Date.now(); }, CLOCK_INTERVAL_MS);
}

function stop(): void {
  isActive = false;
  visible.value = false;
  expanded.value = false;
  ++generation;
  readPending = false;
  if (pollTimer) clearInterval(pollTimer);
  if (clockTimer) clearInterval(clockTimer);
  pollTimer = null;
  clockTimer = null;
}

defineExpose({ refresh });
onMounted(start);
onActivated(start);
onDeactivated(stop);
onUnmounted(stop);
</script>

<style scoped>

.floating-pill { position: fixed; right: 32px; bottom: 16px; z-index: 101; color: #dce4ed; font-size: 13px; }
.status-pill { display: flex; align-items: center; gap: 10px; min-height: 40px; padding: 0 14px; border: 1px solid #3d5062; border-radius: 22px; background: #18212c; color: #dce4ed; box-shadow: 0 4px 18px #0005; font: inherit; cursor: pointer; font-variant-numeric: tabular-nums; }
.status-pill:hover { background: #233141; border-color: #6c8aa3; }.status-pill:focus-visible { outline: 2px solid #68ceab; outline-offset: 3px; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #68ceab; flex-shrink: 0; }.status-dot.muted { background: #929baa; }.status-dot.amber { background: #edb96b; }
.pill-divider { height: 14px; width: 1px; background: #415061; }.pill-chevron { color: #92a8b8; flex: 0 0 16px; width: 16px; height: 16px; transform-origin: center; }.pill-chevron.is-expanded { transform: rotate(180deg); }.pill-warning { border-color: #ba9157; }
.activity-panel { color: #dce4ed; font-size: 13px; max-height: min(480px, calc(100dvh - 110px)); overflow-y: auto; padding: 6px; font-variant-numeric: tabular-nums; }
.list-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; }.activity-panel > .list-heading { margin-bottom: 18px; }h3 { font-size: 13px; margin: 0; font-weight: 500; }strong { font-weight: 500; }
.secondary, small { color: #92a8b8; font-size: 12px; }.eyebrow { display: block; margin: 0 0 8px; line-height: 1.4; font-size: 10px; letter-spacing: 1.5px; color: #92a8b8; text-transform: uppercase; }
.active-run { margin-bottom: 20px; overflow-wrap: anywhere; }.active-run p { margin: 0; line-height: 1.5; }
.activity-panel > p.secondary { margin: 0 0 20px; line-height: 1.5; }.activity-panel > :last-child, .activity-panel > p.secondary:last-child { margin-bottom: 0; }
.experiment-entry { display: grid; gap: 6px; width: 100%; padding: 0; text-align: left; border: 0; background: transparent; color: inherit; font: inherit; line-height: 1.5; cursor: pointer; overflow-wrap: anywhere; }
.experiment-entry:hover strong { color: #68ceab; }.experiment-entry:focus-visible { outline: 2px solid #68ceab; outline-offset: 3px; }
progress { display: block; width: 100%; height: 5px; margin: 4px 0; border: 0; accent-color: #68ceab; }progress::-webkit-progress-bar { background: #344351; border-radius: 5px; }progress::-webkit-progress-value { background: #68ceab; border-radius: 5px; }
ol { list-style: none; padding: 0; margin: 0 0 20px; }li + li { margin-top: 12px; padding-top: 12px; border-top: 1px solid #293340; }.activity-alert { margin: 12px 0; }
@media(max-width: 420px) { .status-pill { gap: 7px; padding: 0 10px; font-size: 12px; } }
</style>
