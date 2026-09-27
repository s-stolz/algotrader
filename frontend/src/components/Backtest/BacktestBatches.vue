<template>
  <section v-if="batchId" aria-label="Backtest Batch" class="batch-history">
    <section v-if="selectedBatch" aria-label="Accepted Batch" class="batch-detail">
      <h3>Accepted Batch {{ selectedBatch.batch_id }}</h3>
      <p>{{ selectedBatch.status }} · {{ selectedBatch.member_count }} fixed members ·
        {{ selectedBatch.raw_count }} raw candidates · {{ selectedBatch.excluded_count }} excluded ·
        revision {{ selectedBatch.lifecycle_revision }}</p>
      <p v-if="members">{{ settledCount }} / {{ selectedBatch.member_count }} settled ·
        {{ executedCount }} executed · {{ outcomeLabel }}</p>
      <p v-if="detailError" role="alert">Batch detail unavailable. {{ detailError }}</p>
      <details>
        <summary>Accepted sweep settings and Strategy Metadata Snapshot</summary>
        <pre>{{ JSON.stringify(selectedBatch.accepted_definition, null, 2) }}</pre>
        <pre>{{ JSON.stringify(selectedBatch.strategy_metadata, null, 2) }}</pre>
      </details>
      <p v-if="members && members.length === 0" role="alert">Accepted Batch has no members.</p>
      <n-data-table
        v-if="members && members.length"
        data-testid="workspace-batch-members"
        :columns="memberColumns"
        :data="members"
        :row-key="(run: BacktestRun) => run.run_id"
        :row-props="memberRowProps"
        :pagination="{ pageSize: 20 }"
        size="small"
      />
      <details v-if="events">
        <summary>Lifecycle events ({{ events.length }})</summary>
        <ol><li v-for="event in events" :key="event.revision">
          {{ event.revision }} · {{ event.event_type }} · {{ event.status }} · {{ event.occurred_at }}
        </li></ol>
      </details>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { NDataTable } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import {
  getBacktestBatch, listBacktestBatchEvents, listBacktestBatchMembers,
} from '@/api/backtesterClient';
import type { BacktestBatch, BacktestBatchEvent, BacktestRun } from '@/types/backtesterContracts';

const emit = defineEmits<{ 'select-run': [run: BacktestRun] }>();
const props = defineProps<{ batchId: string | null }>();
const selectedBatch = ref<BacktestBatch | null>(null);
const members = ref<BacktestRun[] | null>(null);
const events = ref<BacktestBatchEvent[] | null>(null);
const detailError = ref<string | null>(null);
let detailRevision = 0;
let timer: ReturnType<typeof setInterval> | null = null;

const settledCount = computed(() => members.value?.filter((run) =>
  ['succeeded', 'failed', 'cancelled'].includes(run.status)).length ?? 0);
const executedCount = computed(() => members.value?.filter((run) =>
  ['succeeded', 'failed'].includes(run.status)).length ?? 0);
const outcomeLabel = computed(() => {
  const counts = new Map<string, number>();
  for (const run of members.value ?? []) counts.set(run.status, (counts.get(run.status) ?? 0) + 1);
  return [...counts.entries()].map(([status, count]) => `${status}: ${count}`).join(' · ');
});

const memberColumns: DataTableColumns<BacktestRun> = [
  { title: '#', key: 'ordinal', render: (run) => String((run.member_ordinal ?? 0) + 1) },
  { title: 'Run', key: 'run_id', render: (run) => run.run_id },
  { title: 'Market', key: 'market', render: (run) => run.request.symbols[0] ?? '—' },
  { title: 'Timeframe', key: 'timeframe', render: (run) => run.request.timeframe },
  { title: 'Parameters', key: 'parameters', render: (run) =>
    JSON.stringify(run.request.strategy.parameters) },
  { title: 'Allowed Directions', key: 'directions', render: (run) =>
    run.request.execution.allowed_directions },
  { title: 'Status', key: 'status', render: (run) => run.status },
  { title: 'Return (%)', key: 'return', render: (run) =>
    typeof run.metrics?.total_return_pct === 'number' ?
      String(run.metrics.total_return_pct) : '—' },
];

function memberRowProps(run: BacktestRun): Record<string, unknown> {
  return { 'data-testid': `workspace-member-${run.run_id}`, tabindex: 0,
    onClick: () => emit('select-run', run),
    onKeydown: (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        emit('select-run', run);
      }
    } };
}

async function loadDetail(batchId: string): Promise<void> {
  const revision = ++detailRevision;
  detailError.value = null;
  try {
    const [batch, loadedMembers, loadedEvents] = await Promise.all([
      getBacktestBatch(batchId), listBacktestBatchMembers(batchId), listBacktestBatchEvents(batchId),
    ]);
    if (revision !== detailRevision) return;
    selectedBatch.value = batch;
    members.value = loadedMembers;
    events.value = loadedEvents;
  } catch (error) {
    if (revision === detailRevision) {
      detailError.value = error instanceof Error ? error.message : 'Read failed';
    }
  }
}

onMounted(() => {
  if (props.batchId) void loadDetail(props.batchId);
  timer = setInterval(() => { if (props.batchId) void loadDetail(props.batchId); }, 5000);
});
watch(() => props.batchId, (batchId) => {
  ++detailRevision;
  selectedBatch.value = null;
  members.value = null;
  events.value = null;
  if (batchId) void loadDetail(batchId);
});
onUnmounted(() => {
  ++detailRevision;
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.batch-history { margin-top: 24px; }
.batch-detail { margin-top: 16px; }
pre { max-height: 300px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
