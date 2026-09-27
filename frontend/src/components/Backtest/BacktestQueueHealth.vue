<template>
  <section class="queue-health" aria-label="Backtest queue" data-testid="workspace-queue">
    <h2>Queue and worker</h2>
    <p v-if="!snapshot && !readError" role="status">Loading queue health…</p>
    <p v-if="isUnknown" role="alert" data-testid="workspace-queue-unknown">
      Queue and worker status unknown{{ readError ? `: ${readError}` : '; latest snapshot is old' }}.
    </p>
    <template v-if="snapshot">
      <p
        v-if="!isUnknown"
        :role="snapshot.availability === 'healthy' ? 'status' : 'alert'"
        data-testid="workspace-worker-status"
      >
        Worker {{ snapshot.availability }}.
        <span v-if="snapshot.last_heartbeat_ms === null">No worker heartbeat recorded.</span>
        <span v-else>Last heartbeat {{ elapsed(snapshot.last_heartbeat_ms) }} ago.</span>
      </p>
      <p class="telemetry-note">
        {{ isUnknown ? 'Last known snapshot' : 'Snapshot' }}:
        {{ elapsed(snapshot.snapshot_at_ms) }} ago.
        Queue positions are estimates and may change; no start time or ETA is promised.
      </p>
      <ul v-if="snapshot.operational_faults.length" class="faults" aria-label="Worker faults">
        <li v-for="fault in snapshot.operational_faults" :key="fault.code" role="alert">
          {{ fault.message }} ({{ fault.code }})
        </li>
      </ul>
      <p v-if="snapshot.active_run" data-testid="workspace-queue-active">
        {{ isUnknown ? 'Last known active run' : 'Active run' }}:
        {{ snapshot.active_run.run_id }} · active for {{ elapsed(snapshot.active_run.started_at_ms) }}
        <span v-if="snapshot.active_run.batch_id">
          · Batch {{ snapshot.active_run.batch_id }} member #{{ (snapshot.active_run.member_ordinal ?? 0) + 1 }}
        </span>
      </p>
      <p v-else data-testid="workspace-queue-no-active">
        {{ isUnknown ? 'Last known active run: none' : 'No active run.' }}
      </p>
      <p v-if="snapshot.queued.length === 0" data-testid="workspace-queue-empty">
        {{ isUnknown ? 'Last known queue had no waiting work.' : 'No waiting work.' }}
      </p>
      <ol v-else aria-label="Waiting backtests">
        <li
          v-for="entry in snapshot.queued"
          :key="entry.entry_type === 'batch' ? `batch:${entry.batch_id}` : `run:${entry.run_id}`"
          :data-testid="entry.entry_type === 'batch' ?
            `workspace-queue-batch-${entry.batch_id}` : `workspace-queue-run-${entry.run_id}`"
        >
          {{ entry.entry_type === 'batch' ? `Batch ${entry.batch_id}` : entry.run_id }}
          · estimated position {{ entry.estimated_position }} ·
          waiting {{ elapsed(entry.submitted_at_ms) }}
          <template v-if="entry.entry_type === 'batch'">
            · next member #{{ (entry.next_member_ordinal ?? 0) + 1 }}
            · {{ entry.outcome_counts?.succeeded ?? 0 }} succeeded,
            {{ entry.outcome_counts?.failed ?? 0 }} failed,
            {{ entry.outcome_counts?.cancelled ?? 0 }} cancelled
          </template>
        </li>
      </ol>
    </template>
  </section>
</template>

<script setup lang="ts">
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
.queue-health { margin-bottom: 24px; }
.queue-health h2 { font-size: 18px; }
.queue-health p { margin: 8px 0; }
.telemetry-note { color: #aeb8c8; }
.faults { color: #ffb4b4; }
</style>
