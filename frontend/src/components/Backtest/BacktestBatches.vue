<template>
  <section v-if="batchId" aria-label="Backtest Batch" class="batch-history">
    <p v-if="detailError" class="notice error" role="alert">
      Live status unavailable. {{ selectedBatch ? 'Showing the last saved snapshot.' : 'Retrying automatically.' }} {{ detailError }}
    </p>
    <p v-if="!selectedBatch && !detailError" class="loading" role="status">Loading parameter sweep…</p>
    <section v-if="selectedBatch" aria-label="Accepted Batch" class="batch-detail">
      <header class="sweep-header">
        <div>
          <div class="eyebrow">PARAMETER SWEEP <span :title="selectedBatch.batch_id">{{ selectedBatch.batch_id.slice(0, 8) }}</span></div>
          <h3>{{ selectedBatch.strategy_metadata.display_name }}</h3>
          <p class="context">Version {{ selectedBatch.strategy_metadata.strategy_version }}
            <span aria-hidden="true">·</span> {{ selectedBatch.markets.join(', ') }}
            <span aria-hidden="true">·</span> {{ selectedBatch.timeframes.join(', ') }}</p>
        </div>
        <div class="header-actions">
          <div v-if="selectedBatch.started_at_ms !== null" class="elapsed">
            <span>{{ isTerminal ? 'Total time' : 'Time since start' }}</span><strong>{{ elapsed }}</strong>
          </div>
          <span class="status-badge" :class="detailError ? 'unknown' : selectedBatch.status" role="status">
            <span class="status-dot" />{{ detailError ? 'Status unknown' : statusLabel }}
          </span>
          <template v-if="canControl">
            <n-button size="small" :disabled="controlPending" @click="control(canPause ? 'pause' : 'resume')">
              <template #icon><n-icon :component="canPause ? PauseOutline : PlayOutline" /></template>
              {{ canPause ? 'Pause Batch' : 'Resume Batch' }}
            </n-button>
            <n-button
              size="small"
              quaternary
              type="error"
              :disabled="controlPending"
              data-testid="workspace-cancel-batch"
              @click="control('cancel')"
            >Cancel Batch</n-button>
          </template>
        </div>
      </header>

      <div class="progress-panel">
        <div class="progress-heading">
          <div><strong>{{ selectedBatch.settled_count }} <span>/ {{ selectedBatch.total_count }}</span></strong><span class="progress-label">runs settled</span></div>
          <span class="progress-percent">{{ progressPercent }}<small>%</small></span>
        </div>
        <div
          class="progress-track"
          role="progressbar"
          aria-label="Settled runs"
          :aria-valuenow="selectedBatch.settled_count"
          :aria-valuemin="0"
          :aria-valuemax="selectedBatch.total_count"
          :aria-valuetext="`${selectedBatch.settled_count} / ${selectedBatch.total_count} settled; ${selectedBatch.executed_count} executed`"
        >
          <span
            v-for="outcome in outcomes"
            :key="outcome.status"
            :class="outcome.status"
            :style="{ width: `${outcome.count / selectedBatch.total_count * 100}%` }"
          />
        </div>
        <div class="progress-caption">
          <span>{{ selectedBatch.executed_count }} executed <span class="muted">· Successes and failures</span></span>
          <span>{{ detailError ? 'Updates interrupted' : isTerminal ? 'Final results' : 'Updates every 5 seconds' }}</span>
        </div>
        <dl class="outcome-grid">
          <div v-for="outcome in outcomes" :key="outcome.status" :class="outcome.status">
            <dt><span class="legend-dot" />{{ outcome.label }}</dt><dd>{{ outcome.count }}</dd>
          </div>
        </dl>
      </div>

      <div v-if="activityMessage" class="activity-panel" :class="{ 'is-live': !isTerminal && !detailError }">
        <n-icon :component="activityIcon" size="20" />
        <div class="activity-copy">
          <p role="status">{{ activityMessage }}</p>
          <p v-if="activeMember" class="muted active-context">
            {{ activeMember.request.symbols.join(', ') }} · {{ activeMember.request.timeframe }}
            <span v-for="(value, name) in activeMember.request.strategy.parameters" :key="name">
              · {{ parameterLabel(String(name)) }}: {{ JSON.stringify(value) }}
            </span>
          </p>
          <p v-if="selectedBatch.next_member_ordinal !== null" class="muted">
            {{ selectedBatch.status === 'paused' || selectedBatch.status === 'pausing' ? 'Next on resume' : 'Up next' }}:
            run #{{ selectedBatch.next_member_ordinal + 1 }}
          </p>
        </div>
      </div>
      <p v-if="selectedBatch.outcome_counts.failed > 0" class="notice warning" role="status">
        {{ selectedBatch.outcome_counts.failed }} run{{ selectedBatch.outcome_counts.failed === 1 ? '' : 's' }} failed.
        Successful results remain available in Run analysis below.
      </p>
      <p v-if="controlPending" class="notice" role="status">Applying batch command…</p>
      <p v-if="controlError" class="notice error" role="alert">{{ controlError }}</p>
      <p v-if="members && members.length === 0" class="notice error" role="alert">Accepted Batch has no members.</p>

      <dl class="sweep-facts">
        <div><dt>Runs in sweep</dt><dd>{{ selectedBatch.member_count }} <span>of {{ selectedBatch.raw_count }} combinations</span></dd></div>
        <div><dt>Excluded before starting</dt><dd>{{ selectedBatch.excluded_count }} <span>invalid combinations</span></dd></div>
        <div><dt>Started · UTC</dt><dd>{{ formatTimestamp(selectedBatch.started_at_ms) }}</dd></div>
        <div><dt>{{ selectedBatch.status === 'cancelled' ? 'Cancelled' : 'Finished' }} · UTC</dt><dd>{{ formatTimestamp(selectedBatch.completed_at_ms) }}</dd></div>
      </dl>
      <p v-if="selectedBatch.cancel_requested_at_ms != null" class="cancellation-note">
        Cancellation accepted: {{ formatTimestamp(selectedBatch.cancel_requested_at_ms) }} UTC.
      </p>

      <div class="sweep-details">
        <details>
          <summary>Sweep settings <span>Saved at submission</span></summary>
          <dl class="settings-grid">
            <div><dt>Selected markets</dt><dd>{{ selections?.markets.map((market) => `${market.symbol} (${market.exchange})`).join(', ') }}</dd></div>
            <div><dt>Selected timeframes</dt><dd>{{ selections?.timeframes.join(', ') }}</dd></div>
            <div><dt>Allowed directions</dt><dd>{{ selections?.allowed_directions.map(directionLabel).join(', ') }}</dd></div>
            <div v-for="(axis, name) in selections?.parameters" :key="name">
              <dt>{{ parameterLabel(String(name)) }} <small>{{ axis.mode }}</small></dt>
              <dd>{{ axis.values.map((value) => JSON.stringify(value)).join(', ') }}</dd>
            </div>
          </dl>
          <details class="technical-details">
            <summary>Full saved definition and strategy metadata</summary>
            <p>Lifecycle revision {{ selectedBatch.lifecycle_revision }}</p>
            <pre>{{ JSON.stringify(selectedBatch.accepted_definition, null, 2) }}</pre>
            <pre>{{ JSON.stringify(selectedBatch.strategy_metadata, null, 2) }}</pre>
          </details>
        </details>
        <details v-if="events">
          <summary>Activity history <span>{{ events.length }} events</span></summary>
          <ol class="event-timeline">
            <li v-for="event in events" :key="event.revision">
              <div class="event-heading"><strong>{{ eventLabel(event.event_type) }}</strong><time>{{ formatTimestamp(event.occurred_at_ms) }} UTC</time></div>
              <p>{{ event.prior_status ?? (event.revision === 0 ? 'initial' : 'unknown') }} → {{ event.status }} <span class="muted">· revision {{ event.revision }}</span></p>
              <p v-if="event.reason" class="muted">{{ eventLabel(event.reason) }}</p>
              <details v-if="event.trigger_run_id || event.command_id" class="event-identifiers">
                <summary>Event identifiers</summary>
                <p v-if="event.trigger_run_id">run {{ event.trigger_run_id }}</p>
                <p v-if="event.command_id">command {{ event.command_id }}</p>
              </details>
            </li>
          </ol>
        </details>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { NButton, NIcon } from 'naive-ui';
import { CheckmarkCircleOutline, HourglassOutline, PauseOutline, PlayOutline, StopCircleOutline } from '@vicons/ionicons5';
import { computed, onActivated, onDeactivated, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import {
  controlBacktestBatch, getBacktestBatch,
  listBacktestBatchEvents, listBacktestBatchMembers,
} from '@/api/backtesterClient';
import type { BacktestBatch, BacktestBatchEvent, BacktestRun } from '@/types/backtesterContracts';

const emit = defineEmits<{ members: [batchId: string, runs: BacktestRun[]]; cancelled: [] }>();
const props = defineProps<{ batchId: string | null }>();
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
const canPause = computed(() => ['queued', 'running'].includes(selectedBatch.value?.status ?? ''));
const canControl = computed(() => ['queued', 'running', 'pausing', 'paused'].includes(selectedBatch.value?.status ?? ''));
const isTerminal = computed(() => ['completed', 'cancelled'].includes(selectedBatch.value?.status ?? ''));
const selections = computed(() => selectedBatch.value?.accepted_definition.normalized_selections);
const progressPercent = computed(() => {
  const batch = selectedBatch.value;
  return batch?.total_count ? Math.floor(batch.settled_count / batch.total_count * 100) : 0;
});
const outcomes = computed(() => ([
  { status: 'succeeded', label: 'Succeeded' },
  { status: 'failed', label: 'Failed' },
  { status: 'cancelled', label: 'Cancelled' },
  { status: 'running', label: 'Running' },
  { status: 'cancelling', label: 'Stopping' },
  { status: 'queued', label: 'Queued' },
] as const).map((outcome) => ({ ...outcome, count: selectedBatch.value?.outcome_counts[outcome.status] ?? 0 })));
const activeMember = computed(() => selectedBatch.value?.active_member_ordinal == null ? null :
  members.value?.find((member) => member.member_ordinal === selectedBatch.value?.active_member_ordinal));
const statusLabel = computed(() => {
  const batch = selectedBatch.value;
  if (!batch) return '';
  if (batch.status === 'completed' && batch.outcome_counts.failed > 0) return 'Completed with failures';
  return eventLabel(batch.status);
});
const activityMessage = computed(() => {
  const batch = selectedBatch.value;
  if (!batch) return '';
  if (detailError.value) return 'Live activity is unavailable. Retrying automatically.';
  switch (batch.status) {
    case 'queued': return 'Waiting for an execution slot.';
    case 'running': return batch.active_member_ordinal === null
      ? 'Waiting for the next run to start.' : `Running #${batch.active_member_ordinal + 1} of ${batch.total_count}`;
    case 'pausing': return 'Pausing after the active run finishes.';
    case 'paused': return 'Batch paused. Resume to continue queued runs.';
    case 'cancelling': return 'Stopping active execution. Cancellation will finish after cleanup.';
    case 'cancelled': return 'Batch cancelled. Previously completed results are still available.';
    case 'completed': return '';
  }
});
const activityIcon = computed(() => {
  switch (selectedBatch.value?.status) {
    case 'completed': return CheckmarkCircleOutline;
    case 'paused': case 'pausing': return PauseOutline;
    case 'cancelled': case 'cancelling': return StopCircleOutline;
    case 'running': return PlayOutline;
    default: return HourglassOutline;
  }
});
const elapsed = computed(() => {
  const batch = selectedBatch.value;
  if (batch?.started_at_ms == null) return '—';
  const seconds = Math.max(0, Math.floor(((batch.completed_at_ms ?? nowMs.value) - batch.started_at_ms) / 1000));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;
});
const timestampFormatter = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'UTC',
});
function formatTimestamp(timestamp: number | null): string {
  return timestamp === null ? '—' : timestampFormatter.format(timestamp);
}
function eventLabel(value: string): string {
  const words = value.replaceAll('_', ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}
function parameterLabel(name: string): string {
  return selectedBatch.value?.strategy_metadata.parameters.find((parameter) => parameter.name === name)?.display_name ?? eventLabel(name);
}
function directionLabel(value: string): string {
  return ({ long_only: 'Long only', short_only: 'Short only', long_and_short: 'Long and short' })[value] ?? value;
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
  nowMs.value = Date.now();
  clockTimer = setInterval(() => { nowMs.value = Date.now(); }, 1000);
  if (props.batchId) void loadDetail(props.batchId);
  timer = setInterval(() => { if (props.batchId) void loadDetail(props.batchId, true); }, 5000);
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
.batch-history { margin-bottom: 20px; color: #e3eaf0; font-size: 13px; }
.batch-detail { background: #19222c; border: 1px solid #33414e; border-radius: 14px; overflow: hidden; }
.sweep-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px; padding: 24px 28px; }
.eyebrow { display: flex; align-items: center; gap: 12px; color: #9db1c2; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; }
.eyebrow span { color: #98aaba; font: 11px ui-monospace, monospace; letter-spacing: 0; }
h3 { margin: 6px 0; font-size: 23px; line-height: 1.3; font-weight: 600; }
p { margin: 0; }
.context { display: flex; flex-wrap: wrap; gap: 8px; color: #a8b8c6; }
.header-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.status-badge { display: inline-flex; align-items: center; gap: 7px; border: 1px solid #47627b; border-radius: 20px; padding: 6px 11px; font-size: 12px; color: #aecff3; background: #203347; }
.status-dot, .legend-dot { display: inline-block; flex-shrink: 0; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.status-badge.completed { color: #91e0c1; border-color: #385e53; background: #203b34; }
.status-badge.pausing, .status-badge.paused, .status-badge.cancelling, .status-badge.unknown { color: #edc791; border-color: #645539; background: #383124; }
.status-badge.cancelled { color: #b5c0cc; border-color: #4a5562; background: #2a323c; }
.progress-panel { margin: 0 28px 16px; padding: 20px; border: 1px solid #2f4050; border-radius: 10px; background: #141e28; }
.progress-heading { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 15px; }
.progress-heading strong { font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums; }
.progress-heading strong span { font-size: 22px; color: #8fa3b5; font-weight: 400; }
.progress-label { margin-left: 12px; color: #acbdca; }
.progress-percent { color: #d9e8f3; font-size: 23px; font-variant-numeric: tabular-nums; }
.progress-percent small { color: #8fa3b5; font-size: 13px; margin-left: 2px; }
.progress-track { height: 8px; display: flex; overflow: hidden; border-radius: 6px; background: #303e4d; }
.progress-track span { transition: width .35s ease; }
.progress-track .succeeded { background: #68ceab; }
.progress-track .failed { background: #ee9099; }
.progress-track .cancelled { background: #8996a7; }
.progress-track .running { background: repeating-linear-gradient(120deg, #578dba 0, #578dba 5px, #426d92 5px, #426d92 10px); }
.progress-track .cancelling { background: #c8a169; }
.progress-caption { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-top: 10px; font-size: 11px; color: #a9bccb; }
.muted { color: #99adbd; }
.outcome-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin: 22px 0 0; }
.outcome-grid > div { border-left: 1px solid #304150; padding-left: 16px; }
.outcome-grid > div:first-child { border-left: 0; padding-left: 0; }
dt { color: #9fb2c2; font-size: 11px; }
dd { margin: 6px 0 0; }
.outcome-grid dt { display: flex; align-items: center; gap: 7px; }
.outcome-grid dd { font-size: 22px; font-weight: 500; font-variant-numeric: tabular-nums; }
.succeeded .legend-dot, .succeeded dd { color: #7cd8b7; }
.failed .legend-dot, .failed dd { color: #ee9ca5; }
.cancelled .legend-dot { color: #a2afbf; }
.running .legend-dot, .running dd { color: #8dbfe9; }
.cancelling .legend-dot { color: #edc791; }
.queued .legend-dot { color: #71899d; }
.activity-panel { display: flex; align-items: center; gap: 14px; margin: 20px 28px; padding: 4px 0; color: #a7bbcb; }
.activity-panel.is-live > .n-icon { color: #91c4e9; }
.activity-copy { flex: 1; min-width: 0; }
.activity-copy > p:first-child { color: #d9e5ed; font-weight: 500; }
.activity-copy .muted { font-size: 12px; margin-top: 5px; line-height: 1.6; }
.active-context { overflow-wrap: anywhere; max-height: 90px; overflow: auto; }
.elapsed { display: inline-flex; align-items: baseline; gap: 6px; white-space: nowrap; color: #9fb2c2; font-size: 12px; }
.elapsed strong { color: #d9e5ed; font-weight: 500; font-variant-numeric: tabular-nums; }
.sweep-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 20px; margin: 0; padding: 20px 28px; border-top: 1px solid #2d3b48; }
.sweep-facts dd { font-size: 12px; line-height: 1.6; }
.sweep-facts dd span { color: #9fb2c2; }
.notice { margin: 12px 28px; padding: 11px 14px; border: 1px solid #415266; border-radius: 7px; line-height: 1.6; }
.notice.error { color: #ffc0c4; background: #342830; border-color: #67454d; }
.notice.warning { color: #e9c797; background: #302c25; border-color: #534934; }
.loading { padding: 24px; color: #acbdca; }
.cancellation-note { margin: 0 28px 16px; color: #a9bccb; font-size: 12px; }
.sweep-details { border-top: 1px solid #2d3b48; }
.sweep-details > details { padding: 15px 28px; }
.sweep-details > details + details { border-top: 1px solid #2d3b48; }
summary { cursor: pointer; color: #c7d6e1; font-size: 12px; }
summary::marker { color: #8aa3b7; }
summary:focus-visible { outline: 2px solid #8dbfe9; outline-offset: 5px; border-radius: 2px; }
summary > span { margin-left: 10px; color: #95aabb; font-size: 11px; }
.settings-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; margin: 20px 0; }
.settings-grid dd { overflow-wrap: anywhere; white-space: pre-wrap; line-height: 1.6; }
.settings-grid small { margin-left: 5px; color: #bbcad5; }
.technical-details { padding: 12px; background: #141e28; border-radius: 6px; }
pre { max-height: 300px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; color: #aabcca; }
.event-timeline { list-style: none; padding: 0 0 0 15px; margin: 20px 0 0 4px; border-left: 1px solid #3b5163; }
.event-timeline li { position: relative; padding: 0 0 20px 8px; }
.event-timeline li:last-child { padding-bottom: 0; }
.event-timeline li::before { content: ''; position: absolute; left: -20px; top: 5px; width: 7px; height: 7px; background: #86a8bf; border-radius: 50%; }
.event-heading { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px; }
.event-heading strong { font-size: 12px; font-weight: 500; }
.event-heading time { color: #9fb2c2; font-size: 11px; }
.event-timeline p { margin-top: 5px; font-size: 12px; overflow-wrap: anywhere; }
.event-identifiers { margin-top: 8px; }
.event-identifiers summary { color: #97adbe; font-size: 11px; }
@media (prefers-reduced-motion: reduce) { .progress-track span { transition: none; } }
@media (max-width: 900px) {
  .sweep-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .settings-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 600px) {
  .sweep-header, .sweep-facts, .sweep-details > details { padding: 18px; }
  .progress-panel { margin: 0 18px 16px; padding: 16px; }
  .outcome-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); row-gap: 20px; }
  .outcome-grid > div:nth-child(4) { border-left: 0; padding-left: 0; }
  .activity-panel { margin: 18px; align-items: flex-start; flex-wrap: wrap; }
  .notice { margin: 12px 18px; }
  .progress-label { display: block; margin: 2px 0 0; font-size: 12px; }
  .progress-caption .muted { display: none; }
  .settings-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
