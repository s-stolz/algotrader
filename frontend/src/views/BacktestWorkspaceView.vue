<template>
  <main class="workspace">
    <header class="workspace-header">
      <div>
        <h1>Backtest Workspace</h1>
        <p>Saved standalone Backtest Runs</p>
      </div>
      <div class="header-actions">
        <n-button data-testid="workspace-refresh" :loading="isRefreshing" @click="loadRuns()">
          Refresh
        </n-button>
        <n-button data-testid="workspace-chart-return" @click="router.push('/')">
          Return to chart
        </n-button>
      </div>
    </header>

    <section aria-label="Saved Backtest Runs">
      <div class="filters">
        <n-input
          v-model:value="search"
          data-testid="workspace-search"
          clearable
          placeholder="Search saved runs"
          aria-label="Search saved runs"
        />
        <n-select
          v-model:value="statusFilter"
          data-testid="workspace-status-filter"
          aria-label="Filter by status"
          :options="statusOptions"
        />
        <n-select
          v-model:value="typeFilter"
          data-testid="workspace-type-filter"
          aria-label="Filter by type"
          :options="typeOptions"
        />
        <n-select
          v-model:value="marketFilter"
          data-testid="workspace-market-filter"
          aria-label="Filter by Market"
          :options="marketOptions"
        />
        <n-select
          v-model:value="strategyFilter"
          data-testid="workspace-strategy-filter"
          aria-label="Filter by Strategy"
          :options="strategyOptions"
        />
        <n-select
          v-model:value="timeframeFilter"
          data-testid="workspace-timeframe-filter"
          aria-label="Filter by Timeframe"
          :options="timeframeOptions"
        />
      </div>

      <p v-if="isLoading" role="status">Loading saved runs…</p>
      <p v-if="readError" role="alert">
        Run history unavailable; current lifecycle status is unknown. {{ readError }}
      </p>
      <p v-if="deleteError" role="alert">{{ deleteError }}</p>
      <p v-if="runs !== null && runs.length === 0 && !readError" role="status">
        No saved Backtest Runs.
      </p>
      <p v-else-if="runs !== null && filteredRuns.length === 0 && !readError" role="status">
        No Backtest Runs match these filters.
      </p>

      <n-data-table
        v-if="runs !== null"
        data-testid="workspace-history"
        :columns="historyColumns"
        :data="filteredRuns"
        :row-key="rowKey"
        :row-props="historyRowProps"
        :pagination="{ pageSize: 15 }"
        :bordered="false"
        size="small"
      />
    </section>

    <section class="current-backtest" aria-label="Current Backtest">
      <div class="section-heading">
        <h2>Current Backtest</h2>
        <n-button
          v-if="selectedRun"
          data-testid="workspace-open-chart"
          :disabled="overlayStore.isLoading || !!chartReason"
          @click="openOnChart"
        >Open on chart</n-button>
      </div>
      <p v-if="!selectedRunId">Select a saved run to inspect its request and results.</p>
      <p v-if="detailLoading" role="status">Loading selected Backtest…</p>
      <p v-if="detailError" role="alert">{{ detailError }}</p>
      <p v-if="overlayStore.error" role="alert">{{ overlayStore.error }}</p>
      <template v-if="selectedRun">
        <p v-if="selectedRun.error_message" class="run-error">
          {{ selectedRun.error_message }}
        </p>
        <p v-if="chartReason" class="chart-reason">{{ chartReason }}</p>
        <n-data-table
          data-testid="workspace-current-backtest"
          :columns="detailColumns"
          :data="[selectedRun]"
          :row-key="rowKey"
          :bordered="false"
          :scroll-x="1860"
          size="small"
        />
        <details class="request-details">
          <summary>Saved request and execution settings</summary>
          <dl>
            <dt>Run ID</dt><dd>{{ selectedRun.run_id }}</dd>
            <dt>Strategy parameters</dt>
            <dd>{{ JSON.stringify(selectedRun.request.strategy.parameters) }}</dd>
            <dt>Engine</dt><dd>{{ selectedRun.request.engine }}</dd>
            <dt>Data granularity</dt><dd>{{ selectedRun.request.data_granularity }}</dd>
            <dt>Allowed Directions</dt>
            <dd>{{ selectedRun.request.execution.allowed_directions }}</dd>
            <dt>Execution settings</dt>
            <dd>{{ JSON.stringify(selectedRun.request.execution) }}</dd>
            <dt>Submitted</dt><dd>{{ formatTimestamp(selectedRun.submitted_at_ms) }}</dd>
            <dt>Started</dt><dd>{{ formatTimestamp(selectedRun.started_at_ms) }}</dd>
            <dt>Completed</dt><dd>{{ formatTimestamp(selectedRun.completed_at_ms) }}</dd>
          </dl>
        </details>
      </template>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, h, onActivated, onDeactivated, onMounted, onUnmounted, ref } from 'vue';
import { NButton, NDataTable, NInput, NSelect, NTag } from 'naive-ui';
import type { DataTableColumns, SelectOption } from 'naive-ui';
import { useRouter } from 'vue-router';

import { deleteBacktestRun, getBacktestRun, listBacktestRuns } from '@/api/backtesterClient';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import { BACKTEST_RUN_STATUSES, type BacktestRun } from '@/types/backtesterContracts';

import {
  compareHistoryRuns, displayWinRate, formatMagnitude, formatSigned, formatUtcDate, runMarket,
  runName, savedMetric, strategyVersion, type HistorySortKey,
} from './backtestWorkspaceRuns';

defineOptions({ name: 'BacktestWorkspaceView' });

const POLL_INTERVAL_MS = 5000;
const router = useRouter();
const workspaceStore = useBacktestWorkspaceStore();
const overlayStore = useBacktestOverlayStore();
const marketsStore = useMarketsStore();
const runs = ref<BacktestRun[] | null>(null);
const isLoading = ref(false);
const isRefreshing = ref(false);
const readError = ref<string | null>(null);
const detailError = ref<string | null>(null);
const deleteError = ref<string | null>(null);
const deletingRunIds = ref<ReadonlySet<string>>(new Set());
const detailLoading = ref(false);
const search = ref('');
const statusFilter = ref('all');
const typeFilter = ref('all');
const marketFilter = ref('all');
const strategyFilter = ref('all');
const timeframeFilter = ref('all');
const selectedRunId = computed(() => workspaceStore.selectedRunId);
const selectedRun = computed(() => workspaceStore.selectedRun);
const chartReason = computed(() => selectedRun.value
  ? overlayStore.getBacktestRunSelectability(selectedRun.value).reason : null);
let pollTimer: ReturnType<typeof setInterval> | null = null;
let readGeneration = 0;
let activeHistoryRead: Promise<void> | null = null;
let refreshAfterCurrentRead = false;
let detailSequence = 0;
let isActive = false;

const statusOptions: SelectOption[] = [
  { label: 'All statuses', value: 'all' },
  ...BACKTEST_RUN_STATUSES.map((status) => ({ label: status, value: status })),
];
const typeOptions: SelectOption[] = [
  { label: 'All types', value: 'all' },
  { label: 'Standalone', value: 'standalone' },
];
function optionsFrom(values: string[], allLabel: string): SelectOption[] {
  return [{ label: allLabel, value: 'all' }, ...[...new Set(values)].sort().map(
    (value) => ({ label: value, value }),
  )];
}
const marketOptions = computed(() => optionsFrom(
  (runs.value ?? []).map(runMarket), 'All Markets',
));
const strategyOptions = computed(() => optionsFrom(
  (runs.value ?? []).map((run) => run.request.strategy.strategy_id), 'All Strategies',
));
const timeframeOptions = computed(() => optionsFrom(
  (runs.value ?? []).map((run) => run.request.timeframe), 'All Timeframes',
));

const filteredRuns = computed(() => (runs.value ?? []).filter((run) => {
  const query = search.value.trim().toLowerCase();
  return (statusFilter.value === 'all' || run.status === statusFilter.value) &&
    (typeFilter.value === 'all' || typeFilter.value === 'standalone') &&
    (marketFilter.value === 'all' || runMarket(run) === marketFilter.value) &&
    (strategyFilter.value === 'all' || run.request.strategy.strategy_id === strategyFilter.value) &&
    (timeframeFilter.value === 'all' || run.request.timeframe === timeframeFilter.value) &&
    (!query || [
      runName(run), run.run_id, run.status, runMarket(run),
      run.request.timeframe, run.request.strategy.strategy_id,
    ].some((value) => value.toLowerCase().includes(query)));
}));

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'The Backtest service could not be read.';
}

async function loadSelected(runId: string): Promise<void> {
  const sequence = ++detailSequence;
  detailLoading.value = true;
  detailError.value = null;
  try {
    const detail = await getBacktestRun(runId);
    if (sequence === detailSequence && workspaceStore.selectedRunId === runId) {
      workspaceStore.selectRun(detail);
    }
  } catch (error) {
    if (sequence === detailSequence && workspaceStore.selectedRunId === runId) {
      detailError.value = errorMessage(error);
    }
  } finally {
    if (sequence === detailSequence) detailLoading.value = false;
  }
}

async function readRuns(): Promise<void> {
  const generation = ++readGeneration;
  isLoading.value = runs.value === null;
  isRefreshing.value = runs.value !== null;
  try {
    const latest = await listBacktestRuns();
    if (generation !== readGeneration || !isActive) return;
    runs.value = latest;
    readError.value = null;
    const selected = latest.find((run) => run.run_id === selectedRunId.value);
    if (selected) {
      workspaceStore.selectRun(selected);
      void loadSelected(selected.run_id);
    } else if (selectedRunId.value) {
      workspaceStore.clearSelection();
      ++detailSequence;
    }
  } catch (error) {
    if (generation === readGeneration && isActive) readError.value = errorMessage(error);
  } finally {
    if (generation !== readGeneration) return;
    activeHistoryRead = null;
    if (refreshAfterCurrentRead && isActive) {
      refreshAfterCurrentRead = false;
      void loadRuns();
      return;
    }
    isLoading.value = false;
    isRefreshing.value = false;
  }
}

function loadRuns(shouldQueue = true): Promise<void> {
  if (!isActive) return Promise.resolve();
  if (activeHistoryRead) {
    if (shouldQueue) refreshAfterCurrentRead = true;
    return activeHistoryRead;
  }
  activeHistoryRead = readRuns();
  return activeHistoryRead;
}

function selectRun(run: BacktestRun): void {
  workspaceStore.selectRun(run);
  void loadSelected(run.run_id);
}

function rowKey(run: BacktestRun): string {
  return run.run_id;
}

function historyRowProps(run: BacktestRun): Record<string, unknown> {
  return {
    'data-testid': `workspace-run-${run.run_id}`,
    'aria-selected': selectedRunId.value === run.run_id,
    tabindex: 0,
    onClick: () => selectRun(run),
    onKeydown: (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectRun(run);
      }
    },
  };
}

function cell(value: string, explanation?: string) {
  return h('span', { title: explanation ?? value, class: 'ellipsis-cell' }, value);
}

function historyColumn(title: string, key: HistorySortKey,
  render: (run: BacktestRun) => ReturnType<typeof h>): DataTableColumns<BacktestRun>[number] {
  return {
    title, key, sorter: (left, right) => compareHistoryRuns(left, right, key),
    ellipsis: { tooltip: true }, render,
  };
}

const historyColumns: DataTableColumns<BacktestRun> = [
  historyColumn('Name', 'name', (run) => cell(runName(run))),
  historyColumn('Type', 'type', () => cell('Standalone')),
  historyColumn('Strategy / version', 'strategy', (run) => cell(
    `${run.request.strategy.strategy_id} · ${strategyVersion(run)}`,
  )),
  historyColumn('Market', 'market', (run) => cell(runMarket(run))),
  historyColumn('Timeframe', 'timeframe', (run) => cell(run.request.timeframe)),
  historyColumn('Start date', 'start', (run) => cell(formatUtcDate(run.request.start_ms))),
  historyColumn('End date', 'end', (run) => cell(formatUtcDate(run.request.end_ms))),
  historyColumn('Status', 'status', (run) => h(NTag, {
    size: 'small', type: run.status === 'succeeded' ? 'success'
      : run.status === 'failed' ? 'error' : 'info',
  }, { default: () => run.status })),
  {
    title: 'Delete', key: 'delete', render: (run) => h(NButton, {
      text: true,
      size: 'small',
      'data-testid': `workspace-delete-${run.run_id}`,
      disabled: (run.status !== 'succeeded' && run.status !== 'failed') ||
        deletingRunIds.value.has(run.run_id),
      title: 'Delete terminal Backtest Run and its saved results, Fills, and Closed Trades',
      onClick: (event: MouseEvent) => {
        event.stopPropagation();
        void deleteRun(run);
      },
    }, { default: () => 'Delete' }),
  },
];

function metricCell(run: BacktestRun, key: string, explanation: string,
  suffix = '', positiveMagnitude = false) {
  const value = savedMetric(run, key);
  const display = positiveMagnitude
    ? formatMagnitude(value, suffix)
    : formatSigned(value, suffix);
  return cell(display, explanation);
}
const detailColumns: DataTableColumns<BacktestRun> = [
  { title: 'Run', key: 'name', render: (run) => cell(runName(run)) },
  { title: 'Status', key: 'status', render: (run) => cell(run.status) },
  { title: 'Strategy / version', key: 'strategy', render: (run) => cell(
    `${run.request.strategy.strategy_id} · ${strategyVersion(run)}`,
  ) },
  { title: 'Market', key: 'market', render: (run) => cell(runMarket(run)) },
  { title: 'Timeframe', key: 'timeframe', render: (run) => cell(run.request.timeframe) },
  { title: 'Start', key: 'start', render: (run) => cell(formatUtcDate(run.request.start_ms)) },
  { title: 'End', key: 'end', render: (run) => cell(formatUtcDate(run.request.end_ms)) },
  { title: 'Initial capital', key: 'capital', render: (run) => cell(
    String(run.request.initial_capital), 'Initial capital from the saved request, in account units.',
  ) },
  { title: 'Return (%)', key: 'return', render: (run) => metricCell(run, 'total_return_pct',
    'Saved signed Return uses the first recorded equity snapshot as its baseline. That snapshot follows the first Candle executions and fees and may differ from Initial capital.', '%') },
  { title: 'Max drawdown (%)', key: 'drawdown', render: (run) => metricCell(run, 'max_drawdown_pct',
    'Positive magnitude of the saved largest peak-to-trough recorded equity loss.', '%', true) },
  { title: 'Trades', key: 'trades', render: (run) => cell(
    savedMetric(run, 'trade_count')?.toString() ?? '—',
    'Saved count of Closed Trades. A zero count is distinct from a missing result.',
  ) },
  { title: 'Long win rate', key: 'long-win', render: (run) => cell(displayWinRate(run, 'long'),
    'Saved percentage of profitable long Closed Trades; No trades when long count is zero.') },
  { title: 'Short win rate', key: 'short-win', render: (run) => cell(displayWinRate(run, 'short'),
    'Saved percentage of profitable short Closed Trades; No trades when short count is zero.') },
  { title: 'Long PnL', key: 'long-pnl', render: (run) => metricCell(run, 'long_realized_pnl',
    'Saved signed realized PnL from long Closed Trades, in account units.') },
  { title: 'Short PnL', key: 'short-pnl', render: (run) => metricCell(run, 'short_realized_pnl',
    'Saved signed realized PnL from short Closed Trades, in account units.') },
];

function formatTimestamp(timestamp: number | null | undefined): string {
  return timestamp == null ? '—' : new Date(timestamp).toISOString();
}

async function deleteRun(run: BacktestRun): Promise<void> {
  if ((run.status !== 'succeeded' && run.status !== 'failed') ||
    deletingRunIds.value.has(run.run_id)) return;
  if (!window.confirm('Delete this Backtest and all saved results, trades and fills? This cannot be undone.')) return;
  deletingRunIds.value = new Set([...deletingRunIds.value, run.run_id]);
  deleteError.value = null;
  try {
    await deleteBacktestRun(run.run_id);
    runs.value = runs.value?.filter((candidate) => candidate.run_id !== run.run_id) ?? null;
    if (selectedRunId.value === run.run_id) {
      workspaceStore.clearSelection();
      ++detailSequence;
    }
    if (overlayStore.selectedRunId === run.run_id) overlayStore.clearOverlay();
    await loadRuns();
  } catch (error) {
    deleteError.value = errorMessage(error);
  } finally {
    const stillDeleting = new Set(deletingRunIds.value);
    stillDeleting.delete(run.run_id);
    deletingRunIds.value = stillDeleting;
  }
}

async function openOnChart(): Promise<void> {
  const run = selectedRun.value;
  if (!run) return;
  if (marketsStore.all.length === 0) await marketsStore.fetch();
  try {
    const selection = await overlayStore.selectRun(run);
    if (selection.selectable) await router.push('/');
  } catch {
    // The overlay store exposes the read failure beside the selected run.
  }
}

function startPolling(): void {
  if (isActive) return;
  isActive = true;
  if (marketsStore.all.length === 0) void marketsStore.fetch();
  void loadRuns();
  pollTimer = setInterval(() => { void loadRuns(false); }, POLL_INTERVAL_MS);
}

function stopPolling(): void {
  isActive = false;
  ++readGeneration;
  activeHistoryRead = null;
  refreshAfterCurrentRead = false;
  isLoading.value = false;
  isRefreshing.value = false;
  ++detailSequence;
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

onMounted(startPolling);
onActivated(startPolling);
onDeactivated(stopPolling);
onUnmounted(stopPolling);
</script>

<style scoped>
.workspace { min-height: calc(100vh - 20px); }
.workspace-header, .section-heading {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
}
.workspace-header { margin-bottom: 24px; }
.workspace-header h1 { margin: 0; font-size: 24px; }
.workspace-header p { margin: 4px 0; color: #aeb8c8; }
.header-actions { display: flex; gap: 8px; }
.filters {
  display: grid; grid-template-columns: minmax(220px, 2fr) repeat(5, minmax(120px, 1fr));
  gap: 8px; margin-bottom: 12px;
}
.current-backtest { margin-top: 32px; }
.section-heading h2 { font-size: 18px; }
.request-details { margin-top: 16px; }
.request-details dl { display: grid; grid-template-columns: max-content 1fr; gap: 8px 20px; }
.request-details dt { color: #aeb8c8; }
.request-details dd { margin: 0; overflow-wrap: anywhere; }
.run-error, .chart-reason { color: #ffb4b4; }
.ellipsis-cell { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 900px) {
  .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workspace-header { align-items: flex-start; flex-direction: column; }
}
</style>
