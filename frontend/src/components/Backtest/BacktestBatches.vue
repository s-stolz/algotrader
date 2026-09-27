<template>
  <section v-if="batchId" aria-label="Backtest Batch" class="batch-history">
    <p v-if="detailError" role="alert">Batch detail unavailable. {{ detailError }}</p>
    <section v-if="selectedBatch" aria-label="Accepted Batch" class="batch-detail">
      <h3>Accepted Batch {{ selectedBatch.batch_id }}</h3>
      <p>{{ selectedBatch.status }} · {{ selectedBatch.member_count }} fixed members ·
        {{ selectedBatch.raw_count }} raw candidates · {{ selectedBatch.excluded_count }} excluded ·
        revision {{ selectedBatch.lifecycle_revision }}</p>
      <div
        v-if="selectedBatch.status === 'queued' || selectedBatch.status === 'running' ||
        selectedBatch.status === 'pausing' || selectedBatch.status === 'paused'"
      >
        <button
          v-if="selectedBatch.status === 'queued' || selectedBatch.status === 'running'"
          type="button"
          :disabled="controlPending"
          @click="control('pause')"
        >Pause Batch</button>
        <button
          v-else
          type="button"
          :disabled="controlPending"
          @click="control('resume')"
        >Resume Batch</button>
        <button
          type="button"
          :disabled="controlPending"
          data-testid="workspace-cancel-batch"
          @click="control('cancel')"
        >Cancel Batch</button>
      </div>
      <p v-if="selectedBatch.status === 'pausing'" role="status">
        Pausing after the active member finishes.
      </p>
      <p v-if="selectedBatch.status === 'paused'" role="status">Batch paused.</p>
      <p v-if="selectedBatch.status === 'cancelling'" role="status">
        Cancelling Batch: active execution is being stopped; capacity remains held until cleanup commits.
      </p>
      <p v-if="selectedBatch.status === 'cancelled'" role="status">Batch cancelled.</p>
      <p v-if="selectedBatch.cancel_requested_at_ms">Cancellation accepted:
        {{ formatTimestamp(selectedBatch.cancel_requested_at_ms) }}.
      </p>
      <p v-if="controlError" role="alert">{{ controlError }}</p>
      <p>{{ selectedBatch.settled_count }} / {{ selectedBatch.total_count }} settled ·
        {{ selectedBatch.executed_count }} executed · {{ outcomeLabel }}</p>
      <p v-if="selectedBatch.outcome_counts.failed > 0" role="status">
        {{ selectedBatch.outcome_counts.failed }} member failure{{ selectedBatch.outcome_counts.failed === 1 ? '' : 's' }}.
        Successful member results remain available.
      </p>
      <p v-if="selectedBatch.active_member_ordinal !== null">
        Active member #{{ selectedBatch.active_member_ordinal + 1 }}.
      </p>
      <p v-if="selectedBatch.next_member_ordinal !== null">
        Next member #{{ selectedBatch.next_member_ordinal + 1 }}.
      </p>
      <p>First started: {{ formatTimestamp(selectedBatch.started_at_ms) }} ·
        Terminal: {{ formatTimestamp(selectedBatch.completed_at_ms) }}</p>
      <details>
        <summary>Accepted sweep settings and Strategy Metadata Snapshot</summary>
        <pre>{{ JSON.stringify(selectedBatch.accepted_definition, null, 2) }}</pre>
        <pre>{{ JSON.stringify(selectedBatch.strategy_metadata, null, 2) }}</pre>
      </details>
      <p v-if="members && members.length === 0" role="alert">Accepted Batch has no members.</p>
      <details v-if="events">
        <summary>Lifecycle events ({{ events.length }})</summary>
        <ol><li v-for="event in events" :key="event.revision">
          {{ event.revision }} · {{ event.event_type }} ·
          {{ event.prior_status ?? (event.revision === 0 ? 'initial' : 'unknown') }} → {{ event.status }} ·
          {{ formatTimestamp(event.occurred_at_ms) }}
          <span v-if="event.trigger_run_id"> · run {{ event.trigger_run_id }}</span>
          <span v-if="event.command_id"> · command {{ event.command_id }}</span>
        </li></ol>
      </details>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from 'vue';
import {
  controlBacktestBatch, getBacktestBatch,
  listBacktestBatchEvents, listBacktestBatchMembers,
} from '@/api/backtesterClient';
import type { BacktestBatch, BacktestBatchEvent, BacktestRun } from '@/types/backtesterContracts';

const emit = defineEmits<{ members: [batchId: string, runs: BacktestRun[]]; cancelled: [] }>();
const props = defineProps<{ batchId: string | null }>();
const selectedBatch = ref<BacktestBatch | null>(null);
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

const outcomeLabel = computed(() => selectedBatch.value ?
  Object.entries(selectedBatch.value.outcome_counts)
    .filter(([, count]) => count > 0)
    .map(([status, count]) => `${status}: ${count}`).join(' · ') : '');

function formatTimestamp(timestamp: number | null): string {
  return timestamp === null ? '—' : new Date(timestamp).toISOString();
}

async function loadDetail(batchId: string, background = false): Promise<void> {
  if (!isActive || (background && readPending)) return;
  readPending = true;
  const revision = ++detailRevision;
  try {
    const [batch, loadedMembers, loadedEvents] = await Promise.all([
      getBacktestBatch(batchId), listBacktestBatchMembers(batchId), listBacktestBatchEvents(batchId),
    ]);
    if (revision !== detailRevision) return;
    for (const command of ['pause', 'resume', 'cancel'] as const) {
      const pending = commandIds[command];
      if (pending && loadedEvents.some((event) => event.command_id === pending)) {
        delete commandIds[command];
        controlError.value = null;
      }
    }
    detailError.value = null;
    selectedBatch.value = batch;
    members.value = loadedMembers;
    events.value = loadedEvents;
    emit('members', batchId, loadedMembers);
  } catch (error) {
    if (revision === detailRevision) {
      detailError.value = error instanceof Error ? error.message : 'Read failed';
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
      if (command === 'cancel') emit('cancelled');
    }
  } catch (error) {
    if (props.batchId === batchId) {
      controlError.value = error instanceof Error ? error.message : 'Batch command failed';
      await loadDetail(batchId);
    }
  } finally {
    controlPending.value = false;
  }
}

function start(): void {
  if (isActive) return;
  isActive = true;
  if (props.batchId) void loadDetail(props.batchId);
  timer = setInterval(() => { if (props.batchId) void loadDetail(props.batchId, true); }, 5000);
}
function stop(): void {
  isActive = false;
  ++detailRevision;
  readPending = false;
  if (timer) clearInterval(timer);
  timer = null;
}
onMounted(start);
onActivated(start);
onDeactivated(stop);
watch(() => props.batchId, (batchId) => {
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
});
onUnmounted(stop);
</script>

<style scoped>
.batch-history { margin-top: 24px; }
.batch-detail { margin-top: 16px; }
pre { max-height: 300px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
