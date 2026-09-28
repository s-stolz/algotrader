<template>
  <section class="queue-health" aria-label="Backtest queue" data-testid="workspace-queue">
    <div class="queue-summary">
      <n-icon size="17" class="queue-icon"><server-outline /></n-icon>
      <h2>Queue and worker</h2>
      <n-tag :type="healthType" size="small" round :bordered="false" class="health-tag">
        {{ isUnknown ? 'Status unknown' : snapshot?.availability ?? 'Connecting' }}
      </n-tag>
      <span v-if="snapshot" class="queue-summary-count">
        {{ isUnknown ? 'Last known: ' : '' }}{{ snapshot.active_run ? '1 active run' : 'Idle' }} · {{ snapshot.queued.length }} waiting
      </span>
    </div>
    <n-skeleton v-if="!snapshot && !readError" text :repeat="2" class="queue-loading" aria-label="Loading queue health" />
    <n-alert v-if="isUnknown" type="warning" class="queue-alert" data-testid="workspace-queue-unknown">
      Queue and worker status unknown{{ readError ? `: ${readError}` : '; latest snapshot is old' }}.
    </n-alert>
    <details v-if="snapshot" class="queue-details">
      <summary>Activity details</summary>
      <div class="worker-metrics">
        <div class="worker-state" data-testid="workspace-worker-status">
          <span class="metric-label">Worker status</span>
          <n-tag :type="healthType" :bordered="false">
            {{ isUnknown ? 'Status unknown' : `Worker ${snapshot.availability}` }}
          </n-tag>
        </div>
        <n-statistic
:label="isUnknown ? 'Last known heartbeat' : 'Last heartbeat'"
          :value="snapshot.last_heartbeat_ms === null ? '—' : elapsed(snapshot.last_heartbeat_ms)"
>
          <template v-if="snapshot.last_heartbeat_ms !== null" #suffix><span class="metric-suffix">ago</span></template>
          <template v-else #suffix><span class="metric-suffix">No worker heartbeat recorded</span></template>
        </n-statistic>
        <n-statistic :label="isUnknown ? 'Last known snapshot' : 'Snapshot age'" :value="elapsed(snapshot.snapshot_at_ms)">
          <template #suffix><span class="metric-suffix">ago</span></template>
        </n-statistic>
      </div>
      <div v-if="snapshot.operational_faults.length" class="faults" aria-label="Worker faults">
        <n-alert v-for="fault in snapshot.operational_faults" :key="fault.code" type="error" :title="fault.message">
          <code>{{ fault.code }}</code>
        </n-alert>
      </div>
      <div class="activity-grid">
        <section class="activity-card" aria-label="Active execution">
          <header class="activity-heading">
            <n-icon size="16"><pulse-outline /></n-icon>
            <h3>{{ isUnknown ? 'Last known active run' : 'Active run' }}</h3>
            <n-tag v-if="snapshot.active_run" size="small" :bordered="false" :type="isUnknown ? 'default' : 'info'">
              {{ isUnknown ? 'Last known' : 'In progress' }}
            </n-tag>
          </header>
          <div v-if="snapshot.active_run" class="active-run" data-testid="workspace-queue-active">
            <span class="metric-label">{{ isUnknown ? 'Last known active run' : 'Run ID' }}</span>
            <code class="run-identity">{{ snapshot.active_run.run_id }}</code>
            <span class="run-duration"><n-icon><time-outline /></n-icon>
              {{ isUnknown ? 'Started' : 'Active for' }} {{ elapsed(snapshot.active_run.started_at_ms) }}{{ isUnknown ? ' ago' : '' }}
            </span>
            <div v-if="snapshot.active_run.batch_id" class="active-batch">
              <n-tag size="small" :bordered="false">Member #{{ (snapshot.active_run.member_ordinal ?? 0) + 1 }}</n-tag>
              <span class="metric-label">Batch <code>{{ snapshot.active_run.batch_id }}</code></span>
            </div>
          </div>
          <n-empty
v-else
size="small"
class="activity-empty"
data-testid="workspace-queue-no-active"
            :description="isUnknown ? 'Last known active run: none' : 'No active run'"
>
            <template #icon><n-icon><pause-circle-outline /></n-icon></template>
          </n-empty>
        </section>
        <section class="activity-card" aria-label="Waiting queue">
          <header class="activity-heading">
            <n-icon size="16"><list-outline /></n-icon>
            <h3>{{ isUnknown ? 'Last known queue' : 'Waiting queue' }}</h3>
            <n-tag size="small" round :bordered="false">{{ snapshot.queued.length }}</n-tag>
          </header>
          <n-empty
v-if="snapshot.queued.length === 0"
size="small"
class="activity-empty"
data-testid="workspace-queue-empty"
            :description="isUnknown ? 'Last known queue had no waiting work' : 'No waiting work'"
>
            <template #icon><n-icon><checkmark-circle-outline /></n-icon></template>
          </n-empty>
          <ol v-else class="waiting-list" aria-label="Waiting backtests">
            <li
v-for="entry in snapshot.queued"
              :key="entry.entry_type === 'batch' ? `batch:${entry.batch_id}` : `run:${entry.run_id}`"
              :data-testid="entry.entry_type === 'batch' ? `workspace-queue-batch-${entry.batch_id}` : `workspace-queue-run-${entry.run_id}`"
>
              <div class="waiting-heading">
                <n-tag size="small" :bordered="false" type="info">Est. #{{ entry.estimated_position }}</n-tag>
                <span>{{ entry.entry_type === 'batch' ? 'Batch' : 'Run' }}</span>
                <span class="waiting-time">Waiting {{ elapsed(entry.submitted_at_ms) }}</span>
              </div>
              <code class="run-identity">{{ entry.entry_type === 'batch' ? entry.batch_id : entry.run_id }}</code>
              <div v-if="entry.entry_type === 'batch'" class="batch-outcomes">
                <span class="metric-label">Next member #{{ (entry.next_member_ordinal ?? 0) + 1 }}</span>
                <n-tag size="small" :bordered="false" type="success">{{ entry.outcome_counts?.succeeded ?? 0 }} succeeded</n-tag>
                <n-tag size="small" :bordered="false" :type="entry.outcome_counts?.failed ? 'error' : 'default'">{{ entry.outcome_counts?.failed ?? 0 }} failed</n-tag>
                <n-tag size="small" :bordered="false">{{ entry.outcome_counts?.cancelled ?? 0 }} cancelled</n-tag>
              </div>
            </li>
          </ol>
        </section>
      </div>
      <p class="telemetry-note"><n-icon size="14"><information-circle-outline /></n-icon>
        Queue positions are estimates and may change; no start time or ETA is promised.
      </p>
    </details>
  </section>
</template>

<script setup lang="ts">
import { NAlert, NEmpty, NIcon, NSkeleton, NStatistic, NTag } from 'naive-ui';
import { CheckmarkCircleOutline, InformationCircleOutline, ListOutline, PauseCircleOutline, PulseOutline, ServerOutline, TimeOutline } from '@vicons/ionicons5';
import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref } from 'vue';

import { fetchBacktestQueue } from '@/api/backtesterClient';
import type { BacktestQueueSnapshot } from '@/types/backtesterContracts';

const POLL_INTERVAL_MS = 5000;
const CLOCK_INTERVAL_MS = 1000;
const snapshot = ref<BacktestQueueSnapshot | null>(null);
const readError = ref<string | null>(null);
const nowMs = ref(Date.now());
const isUnknown = computed(() => readError.value !== null ||
  (snapshot.value !== null && nowMs.value - snapshot.value.snapshot_at_ms >
    snapshot.value.stale_after_ms));
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
    readError.value = error instanceof Error ? error.message : 'Queue read failed';
  } finally {
    if (request === generation) readPending = false;
  }
}

function start(): void {
  if (isActive) return;
  isActive = true;
  nowMs.value = Date.now();
  void refresh();
  pollTimer = setInterval(() => { void refresh(true); }, POLL_INTERVAL_MS);
  clockTimer = setInterval(() => { nowMs.value = Date.now(); }, CLOCK_INTERVAL_MS);
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

defineExpose({ refresh });
onMounted(start);
onActivated(start);
onDeactivated(stop);
onUnmounted(stop);
</script>

<style scoped>
.queue-health { border: 1px solid #303b46; border-radius: 10px; background: #18212a; padding: 13px 18px; font-variant-numeric: tabular-nums; position: relative; }
.queue-summary { display: flex; align-items: center; gap: 10px; padding-right: 120px; min-height: 24px; }
.queue-summary h2 { font-size: 13px; font-weight: 600; margin: 0; }
.queue-icon { color: #8facbe; flex-shrink: 0; }
.health-tag { text-transform: capitalize; }
.queue-summary-count { margin-left: auto; color: #a3b2bf; font-size: 12px; }
.queue-details summary { position: absolute; right: 18px; top: 17px; color: #92a8b8; font-size: 12px; cursor: pointer; }
.queue-details summary:hover { color: #dce5ed; }
.queue-details summary:focus-visible { outline: 2px solid #68ceab; outline-offset: 4px; border-radius: 2px; }
.queue-details[open] { padding-top: 20px; border-top: 1px solid #2d3a46; margin-top: 13px; }
.queue-alert, .queue-loading { margin-top: 14px; }
.worker-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-bottom: 20px; gap: 20px; }
.worker-metrics > :not(:first-child) { border-left: 1px solid #2d3a46; padding-left: 24px; }
.worker-state { display: flex; flex-direction: column; align-items: flex-start; gap: 10px; }
.metric-label, .metric-suffix { font-size: 12px; color: #92a8b8; }
.worker-metrics :deep(.n-statistic__label) { font-size: 12px; color: #92a8b8; }
.worker-metrics :deep(.n-statistic-value__content) { font-size: 22px; }
.activity-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); gap: 14px; }
.activity-card { min-width: 0; border: 1px solid #2d3a46; border-radius: 8px; background: #151e27; overflow: hidden; }
.activity-heading { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid #273440; color: #9bafbf; }
.activity-heading h3 { font-size: 12px; font-weight: 500; color: #d0dbe5; margin: 0; flex: 1; }
.activity-empty { padding: 26px 16px; }
.active-run { display: flex; flex-direction: column; align-items: flex-start; gap: 10px; padding: 16px; font-size: 12px; }
.run-identity { display: block; font-size: 12px; color: #d0dbe5; overflow-wrap: anywhere; }
.run-duration { display: flex; align-items: center; gap: 6px; color: #9bafbf; }
.active-batch { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding-top: 4px; overflow-wrap: anywhere; }
.waiting-list { list-style: none; padding: 0; margin: 0; max-height: 280px; overflow-y: auto; }
.waiting-list li { display: grid; gap: 10px; padding: 14px 16px; }
.waiting-list li + li { border-top: 1px solid #273440; }
.waiting-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; font-size: 12px; }
.waiting-time { margin-left: auto; color: #92a8b8; }
.batch-outcomes { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.batch-outcomes .metric-label { margin-right: 4px; }
.telemetry-note { display: flex; align-items: flex-start; gap: 6px; color: #8798a8; font-size: 11px; margin: 14px 0 0; }
.telemetry-note .n-icon { flex-shrink: 0; margin-top: 2px; }
.faults { display: grid; gap: 8px; margin-bottom: 16px; }
@media (max-width: 700px) {
  .queue-summary { flex-wrap: wrap; gap: 8px; }
  .queue-summary-count { margin-left: 0; flex-basis: 100%; }
  .activity-grid { grid-template-columns: minmax(0, 1fr); }
  .worker-metrics { gap: 12px; }
  .worker-metrics > :not(:first-child) { padding-left: 12px; }
}
@media (max-width: 460px) {
  .queue-health { padding: 12px; }
  .queue-summary { padding-right: 0; }
  .queue-details summary { position: static; margin-top: 12px; }
  .queue-details[open] { padding-top: 0; }
  .worker-metrics { grid-template-columns: minmax(0, 1fr); margin-top: 16px; }
  .worker-metrics > :not(:first-child) { padding: 10px 0 0; border-left: 0; border-top: 1px solid #2d3a46; }
}
</style>
