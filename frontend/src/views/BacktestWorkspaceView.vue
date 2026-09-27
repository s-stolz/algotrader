<template>
  <main class="workspace">
    <header class="workspace-header">
      <div>
        <h1>Backtest Workspace</h1>
        <p>Saved standalone Backtest Runs and accepted Batches</p>
      </div>
      <div class="header-actions">
        <n-button type="primary" data-testid="workspace-create" @click="creationOpen = true">
          Create Backtest
        </n-button>
        <n-button data-testid="workspace-refresh" :loading="isRefreshing" @click="refreshWorkspace">
          Refresh
        </n-button>
        <n-button data-testid="workspace-chart-return" @click="router.push('/')">
          Return to chart
        </n-button>
      </div>
    </header>

    <BacktestCreationDrawer
      v-model:show="creationOpen"
      @submitted="createdRun"
      @submitted-batch="refreshWorkspace"
    />

    <BacktestQueueHealth ref="queueHealth" />

    <section aria-label="Saved Backtest Runs">
      <div class="filters">
        <n-input
          v-model:value="search"
          data-testid="workspace-search"
          clearable
          placeholder="Search saved runs and batches"
          aria-label="Search saved runs and batches"
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
        <n-select
          v-model:value="failedFilter"
          data-testid="workspace-failed-filter"
          aria-label="Filter by failed runs"
          :options="failedOptions"
        />
      </div>

      <p v-if="isLoading" role="status">Loading saved runs…</p>
      <p v-if="readError" role="alert">
        Run history unavailable; current lifecycle status is unknown. {{ readError }}
      </p>
      <p v-if="deleteError" role="alert">{{ deleteError }}</p>
      <p v-if="cancelError" role="alert">{{ cancelError }}</p>
      <p v-if="runs !== null && batches !== null && historyRows.length === 0 && !readError" role="status">
        No saved Backtest Runs or Batches.
      </p>
      <p v-else-if="runs !== null && batches !== null && filteredHistory.length === 0 && !readError" role="status">
        No Backtest Runs or Batches match these filters.
      </p>

      <n-data-table
        v-if="runs !== null && batches !== null"
        data-testid="workspace-history"
        :columns="historyColumns"
        :data="filteredHistory"
        :row-key="rowKey"
        :row-props="historyRowProps"
        :pagination="{ pageSize: 15 }"
        :bordered="false"
        size="small"
      />
      <BacktestBatches :batch-id="selectedBatchId" @members="receiveMembers" />
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
      <p v-if="!selectedRunId && !selectedBatchId">Select a saved run or Batch to inspect its request and results.</p>
      <p v-if="detailLoading" role="status">Loading selected Backtest…</p>
      <p v-if="detailError" role="alert">{{ detailError }}</p>
      <p v-if="overlayStore.error" role="alert">{{ overlayStore.error }}</p>
      <template v-if="currentRows.length">
        <div class="comparison-controls">
          <n-input
            v-model:value="memberSearch"
            data-testid="comparison-search"
            clearable
            placeholder="Filter current runs"
            aria-label="Filter current runs"
          />
          <div class="column-chooser">
            <span>Columns</span>
            <n-button
              v-for="preset in presetNames"
              :key="preset"
              size="small"
              :data-testid="`comparison-preset-${preset}`"
              @click="applyPreset(preset)"
            >
              {{ preset }}
            </n-button>
            <details><summary>Choose columns</summary>
              <label v-for="column in optionalColumns" :key="column.key">
                <input
                  type="checkbox"
                  :checked="visibleColumns.includes(column.key)"
                  :data-testid="`comparison-column-${column.key}`"
                  @change="toggleColumn(column.key)"
                />{{ column.title }}
              </label>
            </details>
          </div>
        </div>
        <n-data-table
          :key="visibleColumns.join(',')"
          data-testid="workspace-current-backtest"
          :columns="comparisonColumns"
          :data="filteredCurrentRows"
          :row-key="(run: BacktestRun) => run.run_id"
          :row-props="currentRowProps"
          :pagination="false"
          :max-height="360"
          :scroll-x="comparisonScrollWidth"
          :bordered="false"
          size="small"
          @update:sorter="updateComparisonSort"
        />
        <p v-if="!filteredCurrentRows.length" role="status">No current runs match this filter. Selected runs remain selected.</p>
        <p v-if="compatibilityDifferences.length" data-testid="comparison-compatibility" role="note">
          Compared runs differ in {{ compatibilityDifferences.join(', ') }}. Interpret their results in context.
        </p>
        <p v-if="selectedComparisonIds.length === 0" role="status">
          Select successful runs to inspect exact equity and drawdown.
        </p>
        <div v-else class="curve-inspection">
          <ul class="curve-status">
            <li v-for="id in selectedComparisonIds" :key="id" :data-testid="`curve-status-${id}`">
              {{ analysisRunName(id) }}:
              <template v-if="analysis[id]?.loading">Loading exact Equity Replay…</template>
              <template v-else-if="analysis[id]?.error">Exact Equity Replay read failed: {{ analysis[id]?.error }}. Saved metrics remain available.</template>
              <template v-else-if="analysis[id]?.curve?.availability === 'unavailable'">Exact Equity Replay unavailable: {{ equityUnavailableReason(analysis[id]?.curve?.reason) }}. Saved metrics remain available.</template>
              <template v-else-if="analysis[id]?.curve?.availability === 'exact'">
                Ending equity: {{ analysis[id]?.curve?.equity_curve.at(-1)?.equity }}
                <span v-if="analysis[id]?.curve?.sampled"> · Showing {{ analysis[id]?.curve?.returned_point_count }} of {{ analysis[id]?.curve?.source_point_count }} exact points (sampled).</span>
              </template>
            </li>
          </ul>
          <EquityReplayCharts :series="chartSeries" />
        </div>
      </template>
      <template v-if="selectedRun">
        <p v-if="selectedRun.error_message" class="run-error">
          {{ selectedRun.error_message }}
        </p>
        <p v-if="chartReason" class="chart-reason">{{ chartReason }}</p>
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
    <ExecutionLogDrawer
      v-if="logRun"
      :run="logRun"
      :show="logRun !== null"
      @close="logRun = null"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, h, onActivated, onDeactivated, onMounted, onUnmounted, ref, shallowRef } from 'vue';
import { NButton, NDataTable, NIcon, NInput, NSelect, NTag, NTooltip } from 'naive-ui';
import type { DataTableColumns, SelectOption } from 'naive-ui';
import { DocumentTextOutline } from '@vicons/ionicons5';
import { useRouter } from 'vue-router';

import { cancelBacktestRun, deleteBacktestRun, fetchBacktestEquityCurve, getBacktestRun, listBacktestBatches, listBacktestBatchMembers, listBacktestRuns } from '@/api/backtesterClient';
import ExecutionLogDrawer from '@/components/Backtest/ExecutionLogDrawer.vue';
import BacktestBatches from '@/components/Backtest/BacktestBatches.vue';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import { BACKTEST_BATCH_STATUSES, BACKTEST_RUN_STATUSES, type BacktestBatch, type BacktestRun, type EquityReplayResponse } from '@/types/backtesterContracts';
import BacktestCreationDrawer from './BacktestCreationDrawer.vue';
import EquityReplayCharts from './EquityReplayCharts.vue';
import { COLUMN_PRESETS, compareRuns, differingSettings,
  type ComparisonSortKey, type ReplaySeries } from './backtestComparison';

import {
  displayWinRate, equityUnavailableReason, formatMagnitude, formatSigned,
  formatUtcDate, runMarket,
  runName, savedMetric, strategyVersion, timeframeDuration, type HistorySortKey,
} from './backtestWorkspaceRuns';

defineOptions({ name: 'BacktestWorkspaceView' });

const POLL_INTERVAL_MS = 5000;
const router = useRouter();
const workspaceStore = useBacktestWorkspaceStore();
const overlayStore = useBacktestOverlayStore();
const marketsStore = useMarketsStore();
const queueHealth = ref<InstanceType<typeof BacktestQueueHealth> | null>(null);
const runs = ref<BacktestRun[] | null>(null);
const batches = shallowRef<BacktestBatch[] | null>(null);
type HistoryEntry = { kind: 'run'; run: BacktestRun } | { kind: 'batch'; batch: BacktestBatch };
const isLoading = ref(false);
const isRefreshing = ref(false);
const readError = ref<string | null>(null);
const detailError = ref<string | null>(null);
const deleteError = ref<string | null>(null);
const cancelError = ref<string | null>(null);
const cancellingRunIds = ref<ReadonlySet<string>>(new Set());
const deletingRunIds = ref<ReadonlySet<string>>(new Set());
const detailLoading = ref(false);
type AnalysisState = { loading: boolean; error: string | null;
  curve: EquityReplayResponse | null; detail: BacktestRun | null };
const analysis = ref<Record<string, AnalysisState>>({});
const batchMembers = ref<BacktestRun[]>([]);
const selectedComparisonIds = ref<string[]>([]);
const memberSearch = ref('');
const visibleColumns = ref<string[]>([...COLUMN_PRESETS.Performance]);
const presetNames = Object.keys(COLUMN_PRESETS) as (keyof typeof COLUMN_PRESETS)[];
const currentRows = computed(() => (selectedBatchId.value ? batchMembers.value :
  selectedRun.value ? [selectedRun.value] : []).map((run) =>
  analysis.value[run.run_id]?.detail ?? run));
const comparisonSortKey = ref<ComparisonSortKey>('ordinal');
const comparisonSortOrder = ref<'ascend' | 'descend'>('ascend');
const filteredCurrentRows = computed(() => currentRows.value.filter((run) => {
  const query = memberSearch.value.trim().toLowerCase();
  return !query || [runName(run), run.run_id, run.status, runMarket(run),
    run.request.timeframe, ...Object.entries(run.request.strategy.parameters)
      .map(([key, value]) => `${key} ${String(value)}`)]
    .some((value) => value.toLowerCase().includes(query));
}).sort((left, right) => (comparisonSortOrder.value === 'ascend' ? 1 : -1) *
  compareRuns(left, right, comparisonSortKey.value)));
const selectedComparisonRuns = computed(() => selectedComparisonIds.value
  .map((id) => currentRows.value.find((run) => run.run_id === id))
  .filter((run): run is BacktestRun => run?.status === 'succeeded'));
const compatibilityDifferences = computed(() => differingSettings(selectedComparisonRuns.value));
const chartSeries = computed<ReplaySeries[]>(() => selectedComparisonRuns.value.flatMap((run) => {
  const curve = analysis.value[run.run_id]?.curve;
  return curve?.availability === 'exact' ? [{ runId: run.run_id,
    name: comparisonRunLabel(run), ordinal: run.member_ordinal,
    points: curve.equity_curve }] : [];
}));
const creationOpen = ref(false);
const selectedBatchId = ref<string | null>(null);
const search = ref('');
const statusFilter = ref('all');
const typeFilter = ref('all');
const marketFilter = ref('all');
const strategyFilter = ref('all');
const timeframeFilter = ref('all');
const failedFilter = ref('all');
const selectedRunId = computed(() => workspaceStore.selectedRunId);
const selectedRun = computed(() => workspaceStore.selectedRun);
const logRun = ref<BacktestRun | null>(null);
const chartReason = computed(() => selectedRun.value
  ? overlayStore.getBacktestRunSelectability(selectedRun.value).reason : null);
let pollTimer: ReturnType<typeof setInterval> | null = null;
let readGeneration = 0;
let activeHistoryRead: Promise<void> | null = null;
let refreshAfterCurrentRead = false;
let detailSequence = 0;
let analysisSequence = 0;
const analysisTokens = new Map<string, number>();
let isActive = false;

const statusOptions: SelectOption[] = [
  { label: 'All statuses', value: 'all' },
  ...[...new Set([...BACKTEST_RUN_STATUSES, ...BACKTEST_BATCH_STATUSES])]
    .map((status) => ({ label: status, value: status })),
];
const typeOptions: SelectOption[] = [
  { label: 'All types', value: 'all' },
  { label: 'Standalone', value: 'standalone' },
  { label: 'Parameter Sweep', value: 'batch' },
];
const failedOptions: SelectOption[] = [
  { label: 'All outcomes', value: 'all' },
  { label: 'With failed runs', value: 'with_failed' },
];
function optionsFrom(values: string[], allLabel: string): SelectOption[] {
  return [{ label: allLabel, value: 'all' }, ...[...new Set(values)].sort().map(
    (value) => ({ label: value, value }),
  )];
}
function batchMarkets(batch: BacktestBatch): string[] {
  return batch.market_contexts.map((market) =>
    market.exchange ? `${market.exchange}:${market.symbol}` : market.symbol);
}
function batchTimeframes(batch: BacktestBatch): string[] {
  return batch.timeframes;
}
const marketOptions = computed(() => optionsFrom([
  ...(runs.value ?? []).map(runMarket), ...(batches.value ?? []).flatMap(batchMarkets),
], 'All Markets'));
const strategyOptions = computed(() => optionsFrom(
  [...(runs.value ?? []).map((run) => run.request.strategy.strategy_id),
    ...(batches.value ?? []).map((batch) => batch.strategy_id)], 'All Strategies',
));
const timeframeOptions = computed(() => optionsFrom([
  ...(runs.value ?? []).map((run) => run.request.timeframe),
  ...(batches.value ?? []).flatMap(batchTimeframes),
], 'All Timeframes'));

const historyRows = computed<HistoryEntry[]>(() => [
  ...(runs.value ?? []).filter((run) => !run.batch_id).map((run) => ({ kind: 'run' as const, run })),
  ...(batches.value ?? []).map((batch) => ({ kind: 'batch' as const, batch })),
]);
const filteredHistory = computed(() => historyRows.value.filter((entry) => {
  const query = search.value.trim().toLowerCase();
  if (entry.kind === 'run') {
    const run = entry.run;
    return (statusFilter.value === 'all' || run.status === statusFilter.value) &&
      (typeFilter.value === 'all' || typeFilter.value === 'standalone') &&
      (failedFilter.value === 'all' || run.status === 'failed') &&
      (marketFilter.value === 'all' || runMarket(run) === marketFilter.value) &&
      (strategyFilter.value === 'all' || run.request.strategy.strategy_id === strategyFilter.value) &&
      (timeframeFilter.value === 'all' || run.request.timeframe === timeframeFilter.value) &&
      (!query || [runName(run), run.run_id, run.status, runMarket(run),
        run.request.timeframe, run.request.strategy.strategy_id]
        .some((value) => value.toLowerCase().includes(query)));
  }
  const batch = entry.batch;
  return (statusFilter.value === 'all' || batch.status === statusFilter.value) &&
    (typeFilter.value === 'all' || typeFilter.value === 'batch') &&
    (failedFilter.value === 'all' || batch.has_failed_members) &&
    (marketFilter.value === 'all' || batchMarkets(batch).includes(marketFilter.value)) &&
    (strategyFilter.value === 'all' || batch.strategy_id === strategyFilter.value) &&
    (timeframeFilter.value === 'all' || batchTimeframes(batch).includes(timeframeFilter.value)) &&
    (!query || [batch.batch_id, batch.submission_id, batch.status,
      batch.strategy_id, ...batchMarkets(batch), ...batchTimeframes(batch)]
      .some((value) => value.toLowerCase().includes(query)));
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
      if (JSON.stringify(workspaceStore.selectedRun) !== JSON.stringify(detail)) {
        workspaceStore.selectRun(detail);
      }
    }
  } catch (error) {
    if (sequence === detailSequence && workspaceStore.selectedRunId === runId) {
      detailError.value = errorMessage(error);
    }
  } finally {
    if (sequence === detailSequence) detailLoading.value = false;
  }
}

function analysisRunName(id: string): string {
  const run = currentRows.value.find((candidate) => candidate.run_id === id);
  return run ? comparisonRunLabel(run) : id;
}

function comparisonRunLabel(run: BacktestRun): string {
  return run.member_ordinal == null ? runName(run) :
    `#${run.member_ordinal + 1} · ${runName(run)}`;
}

function loadAnalysis(refresh = false): void {
  const ids = [...selectedComparisonIds.value];
  const kept = new Set(ids);
  for (const id of analysisTokens.keys()) {
    if (!kept.has(id)) analysisTokens.delete(id);
  }
  analysis.value = Object.fromEntries(ids.flatMap((id) =>
    analysis.value[id] ? [[id, analysis.value[id]]] : []));
  for (const id of ids) {
    if (!refresh && analysis.value[id]) continue;
    const token = ++analysisSequence;
    analysisTokens.set(id, token);
    analysis.value[id] = { loading: true, error: null, curve: null,
      detail: analysis.value[id]?.detail ?? null };
    void (async () => {
      try {
        const detail = await getBacktestRun(id);
        if (detail.status !== 'succeeded') throw new Error('Run is no longer successful');
        if (analysisTokens.get(id) === token) analysis.value[id] = {
          loading: true, error: null, curve: null, detail,
        };
        const curve = await fetchBacktestEquityCurve(id);
        if (analysisTokens.get(id) === token) analysis.value[id] = {
          loading: false, error: null, curve, detail,
        };
      } catch (error) {
        if (analysisTokens.get(id) === token) analysis.value[id] = {
          loading: false, error: errorMessage(error), curve: null,
          detail: analysis.value[id]?.detail ?? null,
        };
      }
    })();
  }
}

function setComparison(ids: string[], refresh = false): void {
  const nextIds = [...new Set(ids)].filter((id) =>
    currentRows.value.some((run) => run.run_id === id && run.status === 'succeeded'));
  if (!refresh && nextIds.length === selectedComparisonIds.value.length &&
    nextIds.every((id, index) => id === selectedComparisonIds.value[index])) return;
  selectedComparisonIds.value = nextIds;
  loadAnalysis(refresh);
}

function toggleComparison(run: BacktestRun): void {
  if (run.status !== 'succeeded') return;
  setComparison(selectedComparisonIds.value.includes(run.run_id)
    ? selectedComparisonIds.value.filter((id) => id !== run.run_id)
    : [...selectedComparisonIds.value, run.run_id]);
}

function receiveMembers(batchId: string, members: BacktestRun[]): void {
  if (batchId !== selectedBatchId.value) return;
  const changed = JSON.stringify(batchMembers.value) !== JSON.stringify(members);
  if (changed) batchMembers.value = members;
  const eligible = selectedComparisonIds.value.filter((id) =>
    members.some((run) => run.run_id === id && run.status === 'succeeded'));
  setComparison(eligible, changed);
  const selected = members.find((run) => run.run_id === selectedRunId.value);
  if (selected && changed) workspaceStore.selectRun(selected);
}

async function readRuns(): Promise<void> {
  const generation = ++readGeneration;
  isLoading.value = runs.value === null;
  isRefreshing.value = runs.value !== null;
  try {
    const [latest, latestBatches] = await Promise.all([
      listBacktestRuns({ membership: 'standalone' }), listBacktestBatches(),
    ]);
    if (generation !== readGeneration || !isActive) return;
    runs.value = latest;
    batches.value = latestBatches;
    readError.value = null;
    if (logRun.value) {
      logRun.value = latest.find((run) => run.run_id === logRun.value?.run_id) ?? null;
    }
    const selected = latest.find((run) => run.run_id === selectedRunId.value);
    if (selected) {
      const changed = JSON.stringify(selectedRun.value) !== JSON.stringify(selected);
      if (changed) workspaceStore.selectRun(selected);
      void loadSelected(selected.run_id);
      if (changed) setComparison(selectedComparisonIds.value, true);
    } else if (selectedBatchId.value && selectedRunId.value) {
      void loadSelected(selectedRunId.value);
    } else if (selectedRunId.value) {
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
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

function refreshWorkspace(): Promise<void> {
  if (selectedComparisonIds.value.length) loadAnalysis(true);
  void queueHealth.value?.refresh();
  return loadRuns();
}

function selectRun(run: BacktestRun): void {
  workspaceStore.selectRun(run);
  if (selectedBatchId.value === null || selectedComparisonIds.value.length === 0) {
    setComparison(run.status === 'succeeded' ? [run.run_id] : []);
  }
  void loadSelected(run.run_id);
}

async function createdRun(runId: string): Promise<void> {
  void queueHealth.value?.refresh();
  try {
    selectedBatchId.value = null;
    batchMembers.value = [];
    selectRun(await getBacktestRun(runId));
    detailError.value = null;
  } catch (error) {
    detailError.value = errorMessage(error);
  }
  await loadRuns();
}

function rowKey(entry: HistoryEntry): string {
  return entry.kind === 'run' ? entry.run.run_id : entry.batch.batch_id;
}

function historyRowProps(entry: HistoryEntry): Record<string, unknown> {
  const isRun = entry.kind === 'run';
  const select = () => {
    if (entry.kind === 'run') {
      selectedBatchId.value = null;
      batchMembers.value = [];
      selectRun(entry.run);
    } else {
      selectedBatchId.value = entry.batch.batch_id;
      batchMembers.value = [];
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
    }
  };
  return {
    'data-testid': isRun ? `workspace-run-${entry.run.run_id}` : `workspace-batch-${entry.batch.batch_id}`,
    'aria-selected': isRun ? selectedRunId.value === entry.run.run_id : selectedBatchId.value === entry.batch.batch_id,
    tabindex: 0,
    onClick: select,
    onKeydown: (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        select();
      }
    },
  };
}

function cell(value: string, explanation?: string) {
  return h('span', { title: explanation ?? value, class: 'ellipsis-cell',
    style: { display: 'block', overflow: 'hidden', textOverflow: 'ellipsis',
      whiteSpace: 'nowrap' } }, value);
}

function runCell(run: BacktestRun) {
  return h('span', { class: 'run-cell' }, [
    h(NTooltip, null, {
      trigger: () => h(NButton, {
        text: true, size: 'small',
        'data-testid': `workspace-log-${run.run_id}`,
        'aria-label': `View execution log for ${runName(run)}`,
        onKeydown: (event: KeyboardEvent) => { event.stopPropagation(); },
        onClick: (event: MouseEvent) => {
          event.stopPropagation();
          logRun.value = run;
        },
      }, { icon: () => h(NIcon, { size: 16 }, { default: () => h(DocumentTextOutline) }) }),
      default: () => 'View execution log',
    }),
    cell(comparisonRunLabel(run), run.run_id),
  ]);
}

function entrySortValue(entry: HistoryEntry, key: HistorySortKey | 'progress'): string | number {
  if (entry.kind === 'run') {
    const run = entry.run;
    const values: Record<HistorySortKey | 'progress', string | number> = {
      name: runName(run), type: 'Standalone',
      strategy: `${run.request.strategy.strategy_id} ${strategyVersion(run)}`,
      market: runMarket(run), timeframe: timeframeDuration(run.request.timeframe) ?? run.request.timeframe,
      start: run.request.start_ms, end: run.request.end_ms, status: run.status,
      duration: run.request.end_ms - run.request.start_ms, submitted: run.submitted_at_ms,
      progress: ['succeeded', 'failed', 'cancelled'].includes(run.status) ? 1 : 0,
    };
    return values[key];
  }
  const batch = entry.batch;
  const shared = batch.accepted_definition.shared_request;
  const durations = batchTimeframes(batch).map(timeframeDuration).filter((value) => value !== null);
  const values: Record<HistorySortKey | 'progress', string | number> = {
    name: batch.batch_id, type: 'Parameter Sweep',
    strategy: `${batch.strategy_id} v${batch.strategy_version}`,
    market: batchMarkets(batch).join(', '),
    timeframe: durations.length ? Math.min(...durations) : batchTimeframes(batch).join(', '),
    start: Number(shared.start_ms ?? 0), end: Number(shared.end_ms ?? 0), status: batch.status,
    duration: Number(shared.end_ms ?? 0) - Number(shared.start_ms ?? 0),
    submitted: batch.accepted_at_ms,
    progress: batch.total_count ? batch.settled_count / batch.total_count : 0,
  };
  return values[key];
}
function compareHistoryEntries(left: HistoryEntry, right: HistoryEntry,
  key: HistorySortKey | 'progress'): number {
  const a = entrySortValue(left, key);
  const b = entrySortValue(right, key);
  const result = typeof a === 'number' && typeof b === 'number' ? a - b
    : String(a).localeCompare(String(b), undefined, { numeric: true });
  return result || String(entrySortValue(left, 'name')).localeCompare(
    String(entrySortValue(right, 'name')), undefined, { numeric: true },
  ) || rowKey(left).localeCompare(rowKey(right), undefined, { numeric: true });
}
function historyColumn(title: string, key: HistorySortKey | 'progress',
  render: (entry: HistoryEntry) => ReturnType<typeof h>): DataTableColumns<HistoryEntry>[number] {
  return {
    title, key, sorter: (left, right) => compareHistoryEntries(left, right, key),
    ellipsis: { tooltip: true }, render,
  };
}

const historyColumns: DataTableColumns<HistoryEntry> = [
  historyColumn('Name', 'name', (entry) => entry.kind === 'run'
    ? runCell(entry.run) : cell(entry.batch.batch_id)),
  historyColumn('Type', 'type', (entry) => cell(entry.kind === 'run' ? 'Standalone' : 'Parameter Sweep')),
  historyColumn('Strategy / version', 'strategy', (entry) => cell(entry.kind === 'run'
    ? `${entry.run.request.strategy.strategy_id} · ${strategyVersion(entry.run)}`
    : `${entry.batch.strategy_id} · v${entry.batch.strategy_version}`,
  )),
  historyColumn('Market', 'market', (entry) => cell(entry.kind === 'run'
    ? runMarket(entry.run) : batchMarkets(entry.batch).join(', '))),
  historyColumn('Timeframe', 'timeframe', (entry) => cell(entry.kind === 'run'
    ? entry.run.request.timeframe : batchTimeframes(entry.batch).join(', '))),
  historyColumn('Start date', 'start', (entry) => cell(formatUtcDate(entry.kind === 'run'
    ? entry.run.request.start_ms : Number(entry.batch.accepted_definition.shared_request.start_ms)))),
  historyColumn('End date', 'end', (entry) => cell(formatUtcDate(entry.kind === 'run'
    ? entry.run.request.end_ms : Number(entry.batch.accepted_definition.shared_request.end_ms)))),
  historyColumn('Status', 'status', (entry) => {
    const status = entry.kind === 'run' ? entry.run.status : entry.batch.status;
    return h(NTag, { size: 'small', type: status === 'succeeded' || status === 'completed'
      ? 'success' : status === 'failed' ? 'error' : 'info',
    title: status === 'cancelling' ? 'Execution is being stopped; capacity stays held until exit is confirmed.' : undefined },
    { default: () => status });
  }),
  historyColumn('Settled', 'progress', (entry) => cell(entry.kind === 'run'
    ? '—' : `${entry.batch.settled_count} / ${entry.batch.total_count}` +
      (entry.batch.has_failed_members ?
        ` · ${entry.batch.outcome_counts.failed} failed` : ''))),
  {
    title: 'Cancel', key: 'cancel', render: (entry) => entry.kind === 'run' ? h(NButton, {
      text: true, size: 'small',
      'data-testid': `workspace-cancel-${entry.run.run_id}`,
      disabled: !['queued', 'running'].includes(entry.run.status) ||
        cancellingRunIds.value.has(entry.run.run_id),
      title: 'Cancel this Backtest Run',
      onClick: (event: MouseEvent) => {
        event.stopPropagation();
        void cancelRun(entry.run);
      },
    }, { default: () => 'Cancel' }) : cell('—'),
  },
  {
    title: 'Delete', key: 'delete', render: (entry) => entry.kind === 'run' ? h(NButton, {
      text: true,
      size: 'small',
      'data-testid': `workspace-delete-${entry.run.run_id}`,
      disabled: (entry.run.status !== 'succeeded' && entry.run.status !== 'failed') ||
        deletingRunIds.value.has(entry.run.run_id),
      title: 'Delete terminal Backtest Run and its saved results, Fills, and Closed Trades',
      onClick: (event: MouseEvent) => {
        event.stopPropagation();
        void deleteRun(entry.run);
      },
    }, { default: () => 'Delete' }) : cell('—'),
  },
];

function metricCell(run: BacktestRun, key: string, explanation: string,
  suffix = '', positiveMagnitude = false) {
  const value = run.status === 'succeeded' ? savedMetric(run, key) : null;
  const display = positiveMagnitude
    ? formatMagnitude(value, suffix)
    : formatSigned(value, suffix);
  return cell(display, explanation);
}
function countCell(run: BacktestRun, key: string, explanation: string) {
  return cell(run.status === 'succeeded' ? savedMetric(run, key)?.toString() ?? '—' : '—',
    explanation);
}
function directionPnl(run: BacktestRun, direction: 'long' | 'short') {
  if (run.status !== 'succeeded') return cell('—');
  const count = savedMetric(run, `${direction}_trade_count`);
  const pnl = count === 0 ? 0 : savedMetric(run, `${direction}_realized_pnl`);
  return cell(formatSigned(pnl), 'Saved sum of realized PnL from ' + direction +
    ' Closed Trades, signed account units. Zero when there were no trades.');
}
type ComparisonColumn = { title: string; key: string; width: number;
  render: (run: BacktestRun) => ReturnType<typeof h> };
const parameterKeys = computed(() => [...new Set(currentRows.value.flatMap((run) =>
  Object.keys(run.request.strategy.parameters)))].sort());
const optionalColumns = computed<ComparisonColumn[]>(() => [
  { title: 'Status', key: 'status', width: 120, render: (run) => cell(run.status) },
  { title: 'Strategy / version', key: 'strategy', width: 190, render: (run) => cell(
    `${run.request.strategy.strategy_id} · ${strategyVersion(run)}`) },
  { title: 'Market', key: 'market', width: 165, render: (run) => cell(runMarket(run)) },
  { title: 'Timeframe', key: 'timeframe', width: 120, render: (run) => cell(run.request.timeframe) },
  { title: 'Start', key: 'start', width: 130, render: (run) => cell(formatUtcDate(run.request.start_ms)) },
  { title: 'End', key: 'end', width: 130, render: (run) => cell(formatUtcDate(run.request.end_ms)) },
  { title: 'Initial capital', key: 'capital', width: 155, render: (run) => cell(
    String(run.request.initial_capital), 'Saved request Initial capital, in account units.') },
  { title: 'Engine', key: 'engine', width: 150, render: (run) => cell(run.request.engine) },
  { title: 'Allowed Directions', key: 'directions', width: 165,
    render: (run) => cell(run.request.execution.allowed_directions) },
  { title: 'Commission (bps)', key: 'commission', width: 155,
    render: (run) => cell(String(run.request.execution.commission_bps)) },
  { title: 'Slippage (bps)', key: 'slippage', width: 150,
    render: (run) => cell(String(run.request.execution.slippage_bps)) },
  ...parameterKeys.value.map((name) => ({ title: `Parameter: ${name}`, key: `parameter:${name}`,
    width: 180, render: (run: BacktestRun) => cell(
      Object.hasOwn(run.request.strategy.parameters, name)
        ? JSON.stringify(run.request.strategy.parameters[name]) : '—') })),
  { title: 'Return (%)', key: 'return', width: 145, render: (run) => metricCell(run,
    'total_return_pct', 'Saved signed percentage: (ending equity / first recorded equity − 1) × 100. First recorded equity follows the first Candle executions and fees; it can differ from Initial capital.', '%') },
  { title: 'Max drawdown (%)', key: 'drawdown', width: 175,
    render: (run) => metricCell(run, 'max_drawdown_pct',
      'Positive magnitude of the saved largest peak-to-trough recorded equity loss, in percent.', '%', true) },
  { title: 'Ending equity', key: 'ending', width: 155, render: (run) => cell(
    run.status === 'succeeded' && analysis.value[run.run_id]?.curve?.availability === 'exact'
      ? String(analysis.value[run.run_id]?.curve?.equity_curve.at(-1)?.equity ?? '—') : '—',
    'Final point of exact Equity Replay, in account units. Unavailable replay leaves this missing.') },
  { title: 'Trades', key: 'trades', width: 115, render: (run) => countCell(run,
    'trade_count', 'Saved count of Closed Trades. Zero is different from a missing result.') },
  { title: 'Long trades', key: 'long-count', width: 135, render: (run) => countCell(run,
    'long_trade_count', 'Saved count of long Closed Trades.') },
  { title: 'Long win rate', key: 'long-win', width: 150, render: (run) => cell(
    run.status === 'succeeded' ? displayWinRate(run, 'long') : '—',
    'Profitable long Closed Trades divided by long Closed Trades, in percent; No trades if count is zero.') },
  { title: 'Long PnL', key: 'long-pnl', width: 140,
    render: (run) => directionPnl(run, 'long') },
  { title: 'Short trades', key: 'short-count', width: 140, render: (run) => countCell(run,
    'short_trade_count', 'Saved count of short Closed Trades.') },
  { title: 'Short win rate', key: 'short-win', width: 155, render: (run) => cell(
    run.status === 'succeeded' ? displayWinRate(run, 'short') : '—',
    'Profitable short Closed Trades divided by short Closed Trades, in percent; No trades if count is zero.') },
  { title: 'Short PnL', key: 'short-pnl', width: 140,
    render: (run) => directionPnl(run, 'short') },
]);
const comparisonColumns = computed<DataTableColumns<BacktestRun>>(() => [
  { title: 'Compare', key: 'compare', width: 85, fixed: 'left', render: (run) => h('input', {
    type: 'checkbox', checked: selectedComparisonIds.value.includes(run.run_id),
    disabled: run.status !== 'succeeded',
    'data-testid': `comparison-select-${run.run_id}`,
    'aria-label': `Compare ${runName(run)}`,
    onClick: (event: MouseEvent) => event.stopPropagation(),
    onChange: () => toggleComparison(run),
  }) },
  { title: 'Run', key: 'name', width: 225, fixed: 'left', render: runCell,
    sorter: (a, b) => compareRuns(a, b, 'name'),
    sortOrder: comparisonSortKey.value === 'name' ? comparisonSortOrder.value : false as const },
  { title: 'Cancel', key: 'cancel', width: 100, render: (run) => h(NButton, {
    text: true, size: 'small',
    'data-testid': `workspace-cancel-${run.run_id}`,
    disabled: !['queued', 'running'].includes(run.status) || cancellingRunIds.value.has(run.run_id),
    onClick: (event: MouseEvent) => {
      event.stopPropagation();
      void cancelRun(run);
    },
  }, { default: () => 'Cancel' }) },
  ...optionalColumns.value.filter((column) => visibleColumns.value.includes(column.key))
    .map((column) => ({ ...column,
      ...(comparisonSortKeys.includes(column.key as ComparisonSortKey) ? {
        sorter: (a: BacktestRun, b: BacktestRun) => compareRuns(a, b,
          column.key as ComparisonSortKey),
        sortOrder: comparisonSortKey.value === column.key ? comparisonSortOrder.value : false as const,
      } : {}),
    })),
]);
const comparisonSortKeys: string[] = ['name', 'status', 'market', 'timeframe',
  'capital', 'return', 'drawdown'];
const comparisonScrollWidth = computed(() => 410 + optionalColumns.value
  .filter((column) => visibleColumns.value.includes(column.key))
  .reduce((width, column) => width + column.width, 0));

function updateComparisonSort(sorter: { columnKey: string | number; order: 'ascend' | 'descend' | false }) {
  if (sorter.order && comparisonSortKeys.includes(String(sorter.columnKey))) {
    comparisonSortKey.value = String(sorter.columnKey) as ComparisonSortKey;
    comparisonSortOrder.value = sorter.order;
  } else {
    comparisonSortKey.value = 'ordinal';
    comparisonSortOrder.value = 'ascend';
  }
}
function toggleColumn(key: string): void {
  visibleColumns.value = visibleColumns.value.includes(key)
    ? visibleColumns.value.filter((column) => column !== key)
    : [...visibleColumns.value, key];
}
function applyPreset(preset: keyof typeof COLUMN_PRESETS): void {
  visibleColumns.value = [...COLUMN_PRESETS[preset],
    ...(preset === 'Run settings' ? parameterKeys.value.map((name) => `parameter:${name}`) : [])];
}
function currentRowProps(run: BacktestRun): Record<string, unknown> {
  const select = () => selectRun(run);
  return { 'data-testid': `workspace-member-${run.run_id}`,
    'aria-selected': selectedRunId.value === run.run_id, tabindex: 0,
    onClick: select, onKeydown: (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault(); select();
      }
    } };
}

function formatTimestamp(timestamp: number | null | undefined): string {
  return timestamp == null ? '—' : new Date(timestamp).toISOString();
}

async function cancelRun(run: BacktestRun): Promise<void> {
  if (!['queued', 'running'].includes(run.status) || cancellingRunIds.value.has(run.run_id)) return;
  cancellingRunIds.value = new Set([...cancellingRunIds.value, run.run_id]);
  cancelError.value = null;
  try {
    await cancelBacktestRun(run.run_id);
    await refreshWorkspace();
    if (run.batch_id && selectedBatchId.value === run.batch_id) {
      receiveMembers(run.batch_id, await listBacktestBatchMembers(run.batch_id));
    }
  } catch (error) {
    cancelError.value = errorMessage(error);
    await refreshWorkspace();
  } finally {
    const pending = new Set(cancellingRunIds.value);
    pending.delete(run.run_id);
    cancellingRunIds.value = pending;
  }
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
    if (logRun.value?.run_id === run.run_id) logRun.value = null;
    if (selectedRunId.value === run.run_id) {
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
    }
    if (overlayStore.selectedRunId === run.run_id) overlayStore.clearOverlay();
    void queueHealth.value?.refresh();
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
  analysisTokens.clear();
  logRun.value = null;
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
.comparison-controls { display: flex; align-items: flex-start; gap: 16px; margin: 12px 0; }
.comparison-controls .n-input { max-width: 260px; }
.column-chooser { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.column-chooser details { position: relative; }
.column-chooser summary { cursor: pointer; }
.column-chooser details[open] { display: grid; max-height: 280px; overflow: auto;
  padding: 8px; border: 1px solid #536274; background: #192330; z-index: 2; }
.column-chooser label { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.curve-status { padding-left: 20px; }
.request-details { margin-top: 16px; }
.curve-inspection { width: 100%; margin-top: 20px; }
.request-details dl { display: grid; grid-template-columns: max-content 1fr; gap: 8px 20px; }
.request-details dt { color: #aeb8c8; }
.request-details dd { margin: 0; overflow-wrap: anywhere; }
.run-error, .chart-reason { color: #ffb4b4; }
.run-cell { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; }
@media (max-width: 900px) {
  .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workspace-header { align-items: flex-start; flex-direction: column; }
}
</style>
