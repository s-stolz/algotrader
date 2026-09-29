<template>
  <n-config-provider :theme-overrides="workspaceTheme">
  <main class="workspace">
    <nav v-if="page === 'analysis'" class="analysis-breadcrumb" aria-label="Backtest location">
      <n-button text data-testid="workspace-history-return" @click="backToHistory">
        <template #icon><n-icon :component="ArrowBackOutline" /></template>All backtests
      </n-button>
      <span aria-hidden="true">/</span><span>Run analysis</span>
    </nav>
    <header class="workspace-header">
      <div>
        <div class="eyebrow">RESEARCH / BACKTESTS</div>
        <h1>{{ page === 'history' ? 'Backtest Workspace' : analysisTitle }}</h1>
        <p>{{ page === 'history' ? 'Build experiments. Review results. Refine your strategy.' : analysisSubtitle }}</p>
      </div>
      <n-button type="primary" data-testid="workspace-create" @click="creationOpen = true">
        <template #icon><n-icon :component="AddOutline" /></template>Create Backtest
      </n-button>
    </header>

    <BacktestCreationDrawer
      v-model:show="creationOpen"
      @submitted="createdRun"
      @submitted-batch="createdBatch"
    />

    <div class="workspace-refresh">
      <span>{{ readError ? 'History updates unavailable' : 'History checks automatically every 5 seconds' }}</span>
      <n-button data-testid="workspace-refresh" size="small" quaternary :loading="isRefreshing" @click="refreshWorkspace">
        <template #icon><n-icon :component="RefreshOutline" /></template>{{ readError ? 'Retry now' : 'Check now' }}
      </n-button>
    </div>
    <BacktestQueueHealth ref="queueHealth" />
      <p v-if="readError" role="alert">
        Run history unavailable; current lifecycle status is unknown. {{ readError }}
      </p>
      <p v-if="deleteError" role="alert">{{ deleteError }}</p>
      <p v-if="selectionNotice" role="status">{{ selectionNotice }}</p>
      <p v-if="cancelError" role="alert">{{ cancelError }}</p>

    <section v-show="page === 'history'" class="history-page" aria-label="Saved Backtest Runs">
      <div class="workspace-summary">
        <div><span>Saved experiments</span><strong>{{ historyRows.length }}</strong></div>
        <div><span>In progress</span><strong>{{ activeHistoryCount }}</strong></div>
        <div><span>Completed</span><strong>{{ completedHistoryCount }}</strong></div>
        <div><span>With failed runs</span><strong class="failure-count">{{ failedHistoryCount }}</strong></div>
      </div>
      <div class="table-panel">
      <div class="section-heading history-heading">
        <div><h2>Experiment history</h2><p>Open a backtest to explore its configuration and performance.</p></div>
        <n-tag :bordered="false" size="small">{{ filteredHistory.length }} experiments</n-tag>
      </div>
      <div class="filters">
        <n-input
          v-model:value="search"
          data-testid="workspace-search"
          clearable
          placeholder="Search saved runs and batches"
          aria-label="Search saved runs and batches"
        />
        <BaseSelect
          v-model:value="statusFilter"
          data-testid="workspace-status-filter"
          aria-label="Filter by status"
          :options="statusOptions"
        />
        <BaseSelect
          v-model:value="typeFilter"
          data-testid="workspace-type-filter"
          aria-label="Filter by type"
          :options="typeOptions"
        />
        <BaseSelect
          v-model:value="marketFilter"
          data-testid="workspace-market-filter"
          aria-label="Filter by Market"
          :options="marketOptions"
        />
        <BaseSelect
          v-model:value="strategyFilter"
          data-testid="workspace-strategy-filter"
          aria-label="Filter by Strategy"
          :options="strategyOptions"
        />
        <BaseSelect
          v-model:value="timeframeFilter"
          data-testid="workspace-timeframe-filter"
          aria-label="Filter by Timeframe"
          :options="timeframeOptions"
        />
        <BaseSelect
          v-model:value="failedFilter"
          data-testid="workspace-failed-filter"
          aria-label="Filter by failed runs"
          :options="failedOptions"
        />
      </div>

      <p v-if="isLoading" role="status">Loading saved runs…</p>

      <p v-if="runs !== null && batches !== null && historyRows.length === 0 && !readError" role="status">
        No saved Backtest Runs or Batches.
      </p>
      <p v-else-if="runs !== null && batches !== null && filteredHistory.length === 0 && !readError" role="status">
        No Backtest Runs or Batches match these filters.
      </p>

      <BaseDataTable
        v-if="runs !== null && batches !== null"
        data-testid="workspace-history"
        :columns="historyColumns"
        :data="filteredHistory"
        :row-key="rowKey"
        :row-props="historyRowProps"
        :pagination="historyPagination"
        :scroll-x="1470"
        :max-height="540"
        size="medium"
        striped
      />
      </div>
    </section>

    <section v-show="page === 'analysis'" class="current-backtest" aria-label="Current Backtest">
      <BacktestBatches :batch-id="selectedBatchId" @members="receiveMembers" @cancelled="refreshWorkspace" />
      <div class="table-panel">
      <div class="analysis-context" v-if="selectedRun && !selectedBatchId">
        <span>{{ runMarket(selectedRun) }}</span><span>{{ selectedRun.request.timeframe }}</span>
        <span>{{ formatUtcDate(selectedRun.request.start_ms) }} — {{ formatUtcDate(selectedRun.request.end_ms) }} UTC</span>
        <n-tag size="small" :type="selectedRun.status === 'succeeded' ? 'success' : selectedRun.status === 'failed' ? 'error' : 'info'" :bordered="false">{{ selectedRun.status }}</n-tag>
      </div>
      <div class="section-heading">
        <div><h2>Run analysis</h2><p>Compare saved metrics and inspect exact performance over time.</p></div>
      </div>
      <p v-if="!selectedRunId && !selectedBatchId">Select a saved run or Batch to inspect its request and results.</p>
      <p v-if="detailLoading" role="status">Loading selected Backtest…</p>
      <p v-if="detailError" role="alert">{{ detailError }}</p>
      <p v-if="overlayStore.error" role="alert">{{ overlayStore.error }}</p>
      <template v-if="currentRows.length">
        <div class="comparison-controls">
          <span class="column-count">{{ columnSettings.visibleKeys.length }} columns shown</span>
          <BasePopover
            trigger="click"
            placement="bottom-end"
            :width="500"
            :style="{ maxWidth: 'calc(100vw - 32px)', marginBottom: '16px' }"
          >
            <template #trigger>
              <n-button size="small" round data-testid="comparison-columns" aria-label="Run analysis columns">
                <template #icon><n-icon :component="OptionsOutline" /></template>Columns
              </n-button>
            </template>
            <div class="column-popover">
              <section
                v-for="group in columnGroups"
                :key="group.title"
                :aria-label="group.title"
                class="column-group"
              >
                <div class="column-group-heading">
                  <h3>{{ group.title }}</h3>
                  <BaseCheckbox
                    :checked="group.enabled"
                    :indeterminate="group.indeterminate"
                    :data-testid="`comparison-group-${group.title}`"
                    :aria-label="`Show all ${group.title} columns`"
                    @update:checked="setColumnGroup(group.columns, $event)"
                  />
                </div>
                <div class="column-options">
                  <BaseCheckbox
                    v-for="column in group.columns"
                    :key="column.key"
                    :checked="columnSettings.visibleKeys.includes(column.key)"
                    :data-testid="`comparison-column-${column.key}`"
                    @update:checked="setColumn(column.key, $event)"
                  >
                    {{ column.title }}
                  </BaseCheckbox>
                </div>
              </section>
              <div v-if="!hasDefaultColumns" class="column-popover-footer">
                <n-button size="small" round data-testid="comparison-reset-columns" @click="resetColumns">
                  <template #icon><n-icon :component="RefreshOutline" /></template>Reset to default
                </n-button>
              </div>
            </div>
          </BasePopover>
        </div>
        <BaseDataTable
          data-testid="workspace-current-backtest"
          :columns="comparisonColumns"
          :data="sortedCurrentRows"
          :row-key="(run: BacktestRun) => run.run_id"
          :row-props="currentRowProps"
          :pagination="analysisPagination"
          :paginate-single-page="true"
          :max-height="360"
          :scroll-x="comparisonScrollWidth"
          size="small"
          @update:sorter="updateComparisonSort"
        />
        <p class="column-count">The header checkbox selects successful runs on this page. Selections are retained across pages.</p>
        <p v-if="compatibilityDifferences.length" data-testid="comparison-compatibility" role="note">
          Compared runs differ in {{ compatibilityDifferences.join(', ') }}. Interpret their results in context.
        </p>
        <p v-if="selectedComparisonIds.length === 0" role="status">
          Select successful runs to inspect exact equity and drawdown.
        </p>
        <div v-else class="curve-inspection">
          <ul v-if="curveStatusIds.length" class="curve-status">
            <li v-for="id in curveStatusIds" :key="id" :data-testid="`curve-status-${id}`">
              {{ analysisRunName(id) }}:
              <template v-if="analysis[id]?.error">Exact Equity Replay read failed: {{ analysis[id]?.error }}. Saved metrics remain available.</template>
              <template v-else-if="analysis[id]?.curve?.availability === 'unavailable'">Exact Equity Replay unavailable: {{ equityUnavailableReason(analysis[id]?.curve?.reason) }}. Saved metrics remain available.</template>
            </li>
          </ul>
          <EquityReplayCharts v-if="chartSeries.length" :series="chartSeries" :sampled="hasSampledCurve" />
        </div>
      </template>
      <template v-if="selectedRun">
        <p v-if="selectedRun.error_message" class="run-error">
          {{ selectedRun.error_message }}
        </p>
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
      </div>
    </section>
    <ExecutionLogDrawer
      v-if="logRun"
      :run="logRun"
      :show="logRun !== null"
      @close="logRun = null"
    />
  </main>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed, h, onActivated, onDeactivated, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import BasePopover from '@/components/Common/BasePopover.vue';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import { baseSelectTheme } from '@/components/Common/baseSelectTheme';
import { NButton, NCheckbox, NConfigProvider, NIcon, NInput, NSkeleton, NTag, NTooltip } from 'naive-ui';
import type { DataTableColumns, GlobalThemeOverrides, PaginationProps, SelectOption } from 'naive-ui';
import { DocumentTextOutline, BarChartOutline, ArrowBackOutline, AddOutline, RefreshOutline, OptionsOutline, CopyOutline, TrashOutline, StopCircleOutline, TimeOutline, PlayCircleOutline, HourglassOutline, CheckmarkCircleOutline, CloseCircleOutline, BanOutline } from '@vicons/ionicons5';
import { useRouter } from 'vue-router';

import { cancelBacktestRun, deleteBacktestBatch, deleteBacktestRun, fetchBacktestEquityCurve, getBacktestRun, listBacktestBatches, listBacktestBatchMembers, listBacktestRuns } from '@/api/backtesterClient';
import ExecutionLogDrawer from '@/components/Backtest/ExecutionLogDrawer.vue';
import BacktestBatches from '@/components/Backtest/BacktestBatches.vue';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';
import { getBacktestRunSelectability, useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import { BACKTEST_BATCH_STATUSES, BACKTEST_RUN_STATUSES, type BacktestBatch, type BacktestRun, type BacktestRunStatus, type EquityReplayResponse } from '@/types/backtesterContracts';
import BacktestCreationDrawer from './BacktestCreationDrawer.vue';
import { reuseBatch, reuseStandalone } from './backtestReuse';
import EquityReplayCharts from './EquityReplayCharts.vue';
import { compareRuns, differingSettings,
  type ComparisonSortKey, type ReplaySeries } from './backtestComparison';

import {
  displayWinRate, equityUnavailableReason, formatMagnitude, formatSigned,
  formatUtcDate, runMarket,
  runName, savedMetric, strategyVersion, timeframeDuration, type HistorySortKey,
} from './backtestWorkspaceRuns';

defineOptions({ name: 'BacktestWorkspaceView' });

const POLL_INTERVAL_MS = 5000;
const ALL_ANALYSIS_ROWS = Number.MAX_SAFE_INTEGER;
const workspaceTheme: GlobalThemeOverrides = {
  common: { fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif' },
  Select: baseSelectTheme,
};
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
const selectionNotice = ref<string | null>(null);
const cancelError = ref<string | null>(null);
const cancellingRunIds = ref<ReadonlySet<string>>(new Set());
const deletingRunIds = ref<ReadonlySet<string>>(new Set());
const deletingBatchIds = ref<ReadonlySet<string>>(new Set());
const detailLoading = ref(false);
type AnalysisState = { loading: boolean; error: string | null;
  curve: EquityReplayResponse | null; detail: BacktestRun | null };
const analysis = ref<Record<string, AnalysisState>>({});
const batchMembers = ref<BacktestRun[]>([]);
const selectedComparisonIds = ref<string[]>([]);
const defaultColumns = ['status', 'market', 'timeframe', 'capital',
  'return', 'drawdown', 'ending', 'trades'];
const columnSettings = ref({ visibleKeys: [...defaultColumns] });
const hasDefaultColumns = computed(() => columnSettings.value.visibleKeys.length === defaultColumns.length &&
  defaultColumns.every((key) => columnSettings.value.visibleKeys.includes(key)));
const currentRows = computed(() => (selectedBatchId.value ? batchMembers.value :
  selectedRun.value ? [selectedRun.value] : []).map((run) =>
  analysis.value[run.run_id]?.detail ?? run));
const comparisonSortKey = ref<ComparisonSortKey>('ordinal');
const comparisonSortOrder = ref<'ascend' | 'descend'>('ascend');
const sortedCurrentRows = computed(() => [...currentRows.value].sort((left, right) =>
  (comparisonSortOrder.value === 'ascend' ? 1 : -1) *
  compareRuns(left, right, comparisonSortKey.value)));
const analysisPage = ref(1);
const analysisPageSize = ref(20);
const analysisPagination = computed<PaginationProps>(() => ({
  page: analysisPage.value,
  pageSize: analysisPageSize.value,
  showSizePicker: true,
  pageSizes: [
    { label: '20 rows', value: 20 },
    { label: '50 rows', value: 50 },
    { label: '100 rows', value: 100 },
    { label: 'All rows', value: ALL_ANALYSIS_ROWS },
  ],
  selectProps: { menuProps: { class: 'base-select-menu' } },
  onChange: (page: number) => { analysisPage.value = page; },
  onUpdatePageSize: (size: number) => {
    analysisPageSize.value = size;
    analysisPage.value = 1;
  },
}));
const visibleAnalysisRows = computed(() => sortedCurrentRows.value.slice(
  (analysisPage.value - 1) * analysisPageSize.value,
  analysisPage.value * analysisPageSize.value,
));
const selectedComparisonRuns = computed(() => selectedComparisonIds.value
  .map((id) => currentRows.value.find((run) => run.run_id === id))
  .filter((run): run is BacktestRun => run?.status === 'succeeded'));
const compatibilityDifferences = computed(() => differingSettings(selectedComparisonRuns.value));
const curveStatusIds = computed(() => selectedComparisonIds.value.filter((id) =>
  analysis.value[id]?.error || analysis.value[id]?.curve?.availability === 'unavailable'));
const hasSampledCurve = computed(() => selectedComparisonIds.value.some((id) =>
  analysis.value[id]?.curve?.sampled));
const chartSeries = computed<ReplaySeries[]>(() => selectedComparisonRuns.value.flatMap((run) => {
  const curve = analysis.value[run.run_id]?.curve;
  return curve?.availability === 'exact' ? [{ runId: run.run_id,
    name: comparisonRunLabel(run), ordinal: run.member_ordinal,
    points: curve.equity_curve }] : [];
}));
const creationOpen = ref(false);
const page = ref<'history' | 'analysis'>('history');
const historyPagination = ref({ page: 1, pageSize: 15, onChange: (page: number) => {
  historyPagination.value.page = page;
} });
const analysisTitle = computed(() => selectedBatchId.value
  ? `${batches.value?.find((batch) => batch.batch_id === selectedBatchId.value)?.strategy_metadata.display_name ?? 'Parameter Sweep'} analysis`
  : selectedRun.value ? `${selectedRun.value.request.strategy.strategy_id.replaceAll('_', ' ')} analysis` : 'Backtest analysis');
const analysisSubtitle = computed(() => selectedBatchId.value
  ? `Parameter Sweep · ${batchMembers.value.length} runs · ${selectedBatchId.value}`
  : selectedRun.value ? `Standalone run · ${selectedRun.value.run_id}` : 'Loading saved backtest');
function backToHistory(): void {
  page.value = 'history';
  void router.push('/backtests');
}
function showAnalysis(kind: 'run' | 'batch', id: string): void {
  page.value = 'analysis';
  void router.push(`/backtests/${kind}/${encodeURIComponent(id)}`);
}
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
watch(() => currentRows.value.length, (count) => {
  analysisPage.value = Math.min(analysisPage.value, Math.max(1, Math.ceil(count / analysisPageSize.value)));
});
watch(() => selectedBatchId.value ?? selectedRun.value?.run_id, () => {
  analysisPage.value = 1;
});
const logRun = ref<BacktestRun | null>(null);
const openingChartRunId = ref<string | null>(null);
function chartUnavailableReason(run: BacktestRun): string | null {
  return marketsStore.all.length === 0 ? getBacktestRunSelectability(run).reason
    : overlayStore.getBacktestRunSelectability(run).reason;
}
let pollTimer: ReturnType<typeof setInterval> | null = null;
let readGeneration = 0;
let activeHistoryRead: Promise<void> | null = null;
let refreshAfterCurrentRead = false;
let detailSequence = 0;
let pendingDetailId: string | null = null;
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
const activeHistoryCount = computed(() => historyRows.value.filter((entry) =>
  entry.kind === 'run' ? ['queued', 'running', 'cancelling'].includes(entry.run.status)
    : !['completed', 'cancelled'].includes(entry.batch.status)).length);
const completedHistoryCount = computed(() => historyRows.value.filter((entry) =>
  entry.kind === 'run' ? entry.run.status === 'succeeded' : entry.batch.status === 'completed').length);
const failedHistoryCount = computed(() => historyRows.value.filter((entry) =>
  entry.kind === 'run' ? entry.run.status === 'failed' : entry.batch.has_failed_members).length);
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

async function loadSelected(runId: string, background = false): Promise<void> {
  if (background && pendingDetailId === runId) return;
  pendingDetailId = runId;
  const sequence = ++detailSequence;
  detailLoading.value = !background;
  try {
    const detail = await getBacktestRun(runId);
    if (sequence === detailSequence && workspaceStore.selectedRunId === runId) {
      if (JSON.stringify(workspaceStore.selectedRun) !== JSON.stringify(detail)) {
        workspaceStore.selectRun(detail);
      }
      detailError.value = null;
    }
  } catch (error) {
    if (sequence === detailSequence && workspaceStore.selectedRunId === runId) {
      detailError.value = errorMessage(error);
    }
  } finally {
    if (sequence === detailSequence) {
      detailLoading.value = false;
      pendingDetailId = null;
    }
  }
}

function analysisRunName(id: string): string {
  const run = currentRows.value.find((candidate) => candidate.run_id === id);
  return run ? comparisonRunLabel(run) : id;
}

function comparisonRunLabel(run: BacktestRun): string {
  return `#${(run.member_ordinal ?? 0) + 1}`;
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
    if (!refresh && analysis.value[id] && (!analysis.value[id].loading || analysisTokens.has(id))) continue;
    const token = ++analysisSequence;
    analysisTokens.set(id, token);
    analysis.value[id] = { loading: true, error: null, curve: analysis.value[id]?.curve ?? null,
      detail: analysis.value[id]?.detail ?? null };
    void (async () => {
      try {
        const detail = await getBacktestRun(id);
        if (detail.status !== 'succeeded') throw new Error('Run is no longer successful');
        if (analysisTokens.get(id) === token) analysis.value[id] = {
          loading: true, error: null, curve: analysis.value[id]?.curve ?? null, detail,
        };
        const curve = await fetchBacktestEquityCurve(id);
        if (analysisTokens.get(id) === token) analysis.value[id] = {
          loading: false, error: null, curve, detail,
        };
      } catch (error) {
        if (analysisTokens.get(id) === token) analysis.value[id] = {
          loading: false, error: errorMessage(error), curve: analysis.value[id]?.curve ?? null,
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
  if (logRun.value?.batch_id === batchId) {
    logRun.value = members.find((run) => run.run_id === logRun.value?.run_id) ?? null;
  }
  const eligible = selectedComparisonIds.value.filter((id) =>
    members.some((run) => run.run_id === id && run.status === 'succeeded'));
  setComparison(eligible);
  const selected = members.find((run) => run.run_id === selectedRunId.value);
  if (selected && changed) workspaceStore.selectRun(selected);
}

async function readRuns(): Promise<void> {
  const generation = ++readGeneration;
  isLoading.value = runs.value === null;

  try {
    const [latest, latestBatches] = await Promise.all([
      listBacktestRuns({ membership: 'standalone' }), listBacktestBatches(),
    ]);
    if (generation !== readGeneration || !isActive) return;
    runs.value = latest;
    batches.value = latestBatches;
    readError.value = null;
    if (logRun.value && !logRun.value.batch_id) {
      logRun.value = latest.find((run) => run.run_id === logRun.value?.run_id) ?? null;
    }
    if ((overlayStore.selectedRun?.batch_id &&
      !latestBatches.some((batch) => batch.batch_id === overlayStore.selectedRun?.batch_id)) ||
      (overlayStore.selectedRun && !overlayStore.selectedRun.batch_id &&
        !latest.some((run) => run.run_id === overlayStore.selectedRunId))) {
      overlayStore.clearOverlay();
      selectionNotice.value = 'The chart overlay was cleared because its saved Backtest is unavailable.';
    }
    if (selectedBatchId.value && !latestBatches.some((batch) => batch.batch_id === selectedBatchId.value)) {
      selectedBatchId.value = null;
      batchMembers.value = [];
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
      selectionNotice.value = 'The selected Backtest Batch is no longer available.';
    }
    const selected = latest.find((run) => run.run_id === selectedRunId.value);
    if (selected) {
      const changed = JSON.stringify(selectedRun.value) !== JSON.stringify(selected);
      if (changed) workspaceStore.selectRun(selected);
      void loadSelected(selected.run_id, true);
      if (changed) setComparison(selectedComparisonIds.value);
    } else if (selectedBatchId.value && selectedRunId.value) {
      void loadSelected(selectedRunId.value, true);
    } else if (selectedRunId.value) {
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
      selectionNotice.value = 'The selected Backtest Run is no longer available.';
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
  isRefreshing.value = true;
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

function createFrom(entry: HistoryEntry): void {
  workspaceStore.createFromSaved(entry.kind === 'run'
    ? reuseStandalone(entry.run) : reuseBatch(entry.batch));
  creationOpen.value = true;
}

async function createdBatch(batchId: string): Promise<void> {
  selectedBatchId.value = batchId;
  batchMembers.value = [];
  workspaceStore.clearSelection();
  ++detailSequence;
  setComparison([]);
  showAnalysis('batch', batchId);
  await refreshWorkspace();
}

async function createdRun(runId: string): Promise<void> {
  void queueHealth.value?.refresh();
  try {
    selectedBatchId.value = null;
    batchMembers.value = [];
    selectRun(await getBacktestRun(runId));
    showAnalysis('run', runId);
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
    selectionNotice.value = null;
    showAnalysis(entry.kind, rowKey(entry));
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

function executionLogAction(run: BacktestRun, label: string) {
  return h(NTooltip, null, {
    trigger: () => h(NButton, {
      text: true, size: 'small',
      'data-testid': `workspace-log-${run.run_id}`,
      'aria-label': `View execution log for ${label}`,
      onKeydown: (event: KeyboardEvent) => { event.stopPropagation(); },
      onClick: (event: MouseEvent) => {
        event.stopPropagation();
        logRun.value = run;
      },
    }, { icon: () => h(NIcon, { size: 16 }, { default: () => h(DocumentTextOutline) }) }),
    default: () => 'View execution log',
  });
}

function historyRunCell(run: BacktestRun) {
  return h('span', { class: 'run-cell' }, [
    executionLogAction(run, runName(run)),
    h('span', { class: 'run-identity' }, [cell(runName(run) === run.run_id
      ? `${run.request.strategy.strategy_id.replaceAll('_', ' ')}${run.member_ordinal == null ? '' : ` #${run.member_ordinal + 1}`}`
      : run.member_ordinal == null ? runName(run) : `#${run.member_ordinal + 1} · ${runName(run)}`, run.run_id), h('small', run.run_id.slice(0, 8))]),
  ]);
}

function analysisRunActions(run: BacktestRun) {
  return h('div', { class: 'row-actions' }, [
    executionLogAction(run, `run ${comparisonRunLabel(run)}`),
    h(NTooltip, null, {
      trigger: () => h('span', { class: 'run-chart-action' }, [h(NButton, {
        text: true, size: 'small',
        'data-testid': `workspace-chart-${run.run_id}`,
        'aria-label': `Open run ${comparisonRunLabel(run)} on chart`,
        disabled: openingChartRunId.value !== null || overlayStore.isLoading || !!chartUnavailableReason(run),
        loading: openingChartRunId.value === run.run_id,
        onKeydown: (event: KeyboardEvent) => { event.stopPropagation(); },
        onClick: (event: MouseEvent) => {
          event.stopPropagation();
          void openOnChart(run);
        },
      }, { icon: () => h(NIcon, { size: 16, component: BarChartOutline }) })]),
      default: () => chartUnavailableReason(run) ?? 'Open on chart',
    }),
    ...(['queued', 'running'].includes(run.status) ? [h(NTooltip, null, {
      trigger: () => h(NButton, {
        text: true, size: 'small',
        'data-testid': `workspace-cancel-${run.run_id}`,
        'aria-label': `Cancel run ${comparisonRunLabel(run)}`,
        disabled: cancellingRunIds.value.has(run.run_id),
        loading: cancellingRunIds.value.has(run.run_id),
        onKeydown: (event: KeyboardEvent) => { event.stopPropagation(); },
        onClick: (event: MouseEvent) => {
          event.stopPropagation();
          void cancelRun(run);
        },
      }, { icon: () => h(NIcon, { size: 16, component: StopCircleOutline }) }),
      default: () => 'Cancel run',
    })] : []),
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
    title, key, width: ({ name: 235, type: 145, strategy: 190, market: 175, timeframe: 110, start: 125, end: 125, status: 120, progress: 125 } as Record<string, number>)[key] ?? 120,
    fixed: key === 'name' ? 'left' : undefined, sorter: (left, right) => compareHistoryEntries(left, right, key),
    ellipsis: { tooltip: true }, render,
  };
}

const historyColumns: DataTableColumns<HistoryEntry> = [
  historyColumn('Name', 'name', (entry) => entry.kind === 'run'
    ? historyRunCell(entry.run) : cell(entry.batch.batch_id)),
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
  { title: 'Actions', key: 'actions', width: 125, fixed: 'right', render: (entry) =>
    h('div', { class: 'row-actions', onKeydown: (event: KeyboardEvent) => event.stopPropagation() }, [
      h(NButton, { quaternary: true, circle: true, size: 'small',
        'data-testid': `workspace-create-from-${rowKey(entry)}`,
        'aria-label': `Create from this ${entry.kind} ${rowKey(entry)}`, title: 'Create from this',
        onClick: (event: MouseEvent) => { event.stopPropagation(); createFrom(entry); },
      }, { icon: () => h(NIcon, { component: CopyOutline }) }),
      ...(entry.kind === 'run' && ['queued', 'running'].includes(entry.run.status) ? [h(NButton, { quaternary: true, circle: true, size: 'small',
        'data-testid': `workspace-cancel-${entry.run.run_id}`, 'aria-label': 'Cancel run', title: 'Cancel run',
        disabled: !['queued', 'running'].includes(entry.run.status) || cancellingRunIds.value.has(entry.run.run_id),
        onClick: (event: MouseEvent) => { event.stopPropagation(); void cancelRun(entry.run); },
      }, { icon: () => h(NIcon, { component: StopCircleOutline }) })] : []),
      h(NButton, { quaternary: true, circle: true, size: 'small', type: 'error',
        'data-testid': entry.kind === 'run' ? `workspace-delete-${entry.run.run_id}` : `workspace-delete-batch-${entry.batch.batch_id}`,
        'aria-label': `Delete ${entry.kind}`, title: `Delete ${entry.kind}`,
        disabled: entry.kind === 'run' ? !['succeeded', 'failed', 'cancelled'].includes(entry.run.status) || deletingRunIds.value.has(entry.run.run_id)
          : !['completed', 'cancelled'].includes(entry.batch.status) || deletingBatchIds.value.has(entry.batch.batch_id),
        onClick: (event: MouseEvent) => { event.stopPropagation();
          if (entry.kind === 'run') void deleteRun(entry.run); else void deleteBatch(entry.batch);
        },
      }, { icon: () => h(NIcon, { component: TrashOutline }) }),
    ]),
  },
];

function metricCell(run: BacktestRun, key: string, explanation: string,
  suffix = '', positiveMagnitude = false) {
  const value = run.status === 'succeeded' ? savedMetric(run, key) : null;
  const display = positiveMagnitude
    ? formatMagnitude(value, suffix)
    : formatSigned(value, suffix);
  return h('span', { class: value == null || positiveMagnitude ? undefined
    : value < 0 ? 'negative-metric' : value > 0 ? 'positive-metric' : undefined }, cell(display, explanation));
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
const runStatusIcons = {
  queued: { icon: TimeOutline, label: 'Queued', color: '#9aafbf' },
  running: { icon: PlayCircleOutline, label: 'Running', color: '#70c0e8' },
  cancelling: { icon: HourglassOutline, label: 'Cancelling', color: '#e8bc70' },
  succeeded: { icon: CheckmarkCircleOutline, label: 'Succeeded', color: '#7cd8b7' },
  failed: { icon: CloseCircleOutline, label: 'Failed', color: '#e88b8b' },
  cancelled: { icon: BanOutline, label: 'Cancelled', color: '#9aafbf' },
} satisfies Record<BacktestRunStatus, { icon: typeof TimeOutline; label: string; color: string }>;

function runStatusCell(run: BacktestRun) {
  const { icon, label, color } = runStatusIcons[run.status];
  return h(NTooltip, null, {
    trigger: () => h('span', { class: 'run-status-icon', role: 'img',
      'aria-label': label, tabindex: 0 }, h(NIcon, {
      component: icon, size: 20, color, 'aria-hidden': true,
    })),
    default: () => label,
  });
}

type ComparisonColumn = { title: string; key: string; width: number; align?: 'center';
  group: 'Run settings' | 'Performance' | 'Long / short';
  render: (run: BacktestRun) => ReturnType<typeof h> };
const parameterKeys = computed(() => [...new Set(currentRows.value.flatMap((run) =>
  Object.keys(run.request.strategy.parameters)))].sort());
const optionalColumns = computed<ComparisonColumn[]>(() => [
  { title: 'Status', key: 'status', group: 'Run settings', width: 100, align: 'center', render: runStatusCell },
  { title: 'Strategy / version', key: 'strategy', group: 'Run settings', width: 190, render: (run) => cell(
    `${run.request.strategy.strategy_id} · ${strategyVersion(run)}`) },
  { title: 'Market', key: 'market', group: 'Run settings', width: 165, render: (run) => cell(runMarket(run)) },
  { title: 'Timeframe', key: 'timeframe', group: 'Run settings', width: 120, render: (run) => cell(run.request.timeframe) },
  { title: 'Start', key: 'start', group: 'Run settings', width: 130, render: (run) => cell(formatUtcDate(run.request.start_ms)) },
  { title: 'End', key: 'end', group: 'Run settings', width: 130, render: (run) => cell(formatUtcDate(run.request.end_ms)) },
  { title: 'Initial capital', key: 'capital', group: 'Performance', width: 155, render: (run) => cell(
    String(run.request.initial_capital), 'Saved request Initial capital, in account units.') },
  { title: 'Engine', key: 'engine', group: 'Run settings', width: 150, render: (run) => cell(run.request.engine) },
  { title: 'Allowed Directions', key: 'directions', group: 'Run settings', width: 165,
    render: (run) => cell(run.request.execution.allowed_directions) },
  { title: 'Commission (bps)', key: 'commission', group: 'Run settings', width: 155,
    render: (run) => cell(String(run.request.execution.commission_bps)) },
  { title: 'Slippage (bps)', key: 'slippage', group: 'Run settings', width: 150,
    render: (run) => cell(String(run.request.execution.slippage_bps)) },
  ...parameterKeys.value.map((name) => ({ title: `Parameter: ${name}`, key: `parameter:${name}`,
    group: 'Run settings' as const,
    width: 180, render: (run: BacktestRun) => cell(
      Object.hasOwn(run.request.strategy.parameters, name)
        ? JSON.stringify(run.request.strategy.parameters[name]) : '—') })),
  { title: 'Return (%)', key: 'return', group: 'Performance', width: 145, render: (run) => metricCell(run,
    'total_return_pct', 'Saved signed percentage: (ending equity / first recorded equity − 1) × 100. First recorded equity follows the first Candle executions and fees; it can differ from Initial capital.', '%') },
  { title: 'Max drawdown (%)', key: 'drawdown', group: 'Performance', width: 175,
    render: (run) => metricCell(run, 'max_drawdown_pct',
      'Positive magnitude of the saved largest peak-to-trough recorded equity loss, in percent.', '%', true) },
  { title: 'Ending equity', key: 'ending', group: 'Performance', width: 155, render: (run) =>
    analysis.value[run.run_id]?.loading && !analysis.value[run.run_id]?.curve
      ? h('span', { role: 'status', 'aria-label': 'Loading ending equity',
        'data-testid': `ending-loading-${run.run_id}` }, h(NSkeleton, {
        width: 90, height: 16,
        themeOverrides: { color: '#253340', colorEnd: '#354757' },
      }))
      : cell(
        run.status === 'succeeded' && analysis.value[run.run_id]?.curve?.availability === 'exact'
          ? formatSigned(analysis.value[run.run_id]?.curve?.equity_curve.at(-1)?.equity).replace(/^\+/, '') : '—',
        'Final point of exact Equity Replay, in account units. Unavailable replay leaves this missing.') },
  { title: 'Trades', key: 'trades', group: 'Performance', width: 115, render: (run) => countCell(run,
    'trade_count', 'Saved count of Closed Trades. Zero is different from a missing result.') },
  { title: 'Long trades', key: 'long-count', group: 'Long / short', width: 135, render: (run) => countCell(run,
    'long_trade_count', 'Saved count of long Closed Trades.') },
  { title: 'Long win rate', key: 'long-win', group: 'Long / short', width: 150, render: (run) => cell(
    run.status === 'succeeded' ? displayWinRate(run, 'long') : '—',
    'Profitable long Closed Trades divided by long Closed Trades, in percent; No trades if count is zero.') },
  { title: 'Long PnL', key: 'long-pnl', group: 'Long / short', width: 140,
    render: (run) => directionPnl(run, 'long') },
  { title: 'Short trades', key: 'short-count', group: 'Long / short', width: 140, render: (run) => countCell(run,
    'short_trade_count', 'Saved count of short Closed Trades.') },
  { title: 'Short win rate', key: 'short-win', group: 'Long / short', width: 155, render: (run) => cell(
    run.status === 'succeeded' ? displayWinRate(run, 'short') : '—',
    'Profitable short Closed Trades divided by short Closed Trades, in percent; No trades if count is zero.') },
  { title: 'Short PnL', key: 'short-pnl', group: 'Long / short', width: 140,
    render: (run) => directionPnl(run, 'short') },
]);
const columnGroups = computed(() => ['Run settings', 'Performance', 'Long / short']
  .map((title) => {
    const columns = optionalColumns.value.filter((column) => column.group === title);
    const enabledCount = columns.filter((column) => columnSettings.value.visibleKeys.includes(column.key)).length;
    return { title, columns, enabled: enabledCount === columns.length,
      indeterminate: enabledCount > 0 && enabledCount < columns.length };
  }));
const analysisActionsWidth = computed(() => currentRows.value.some((run) =>
  ['queued', 'running'].includes(run.status)) ? 92 : 68);
const selectableComparisonIds = computed(() => visibleAnalysisRows.value
  .filter((run) => run.status === 'succeeded').map((run) => run.run_id));
const selectedComparisonCount = computed(() => selectableComparisonIds.value
  .filter((id) => selectedComparisonIds.value.includes(id)).length);
const comparisonColumns = computed<DataTableColumns<BacktestRun>>(() => [
  { title: () => h(NCheckbox, {
    checked: selectableComparisonIds.value.length > 0 &&
      selectedComparisonCount.value === selectableComparisonIds.value.length,
    indeterminate: selectedComparisonCount.value > 0 &&
      selectedComparisonCount.value < selectableComparisonIds.value.length,
    disabled: selectableComparisonIds.value.length === 0,
    'data-testid': 'comparison-select-all',
    'aria-label': 'Select all successful runs on this page for comparison',
    onClick: (event: MouseEvent) => event.stopPropagation(),
    onKeydown: (event: KeyboardEvent) => event.stopPropagation(),
    'onUpdate:checked': (checked: boolean) => setComparison(checked
      ? [...new Set([...selectedComparisonIds.value, ...selectableComparisonIds.value])]
      : selectedComparisonIds.value.filter((id) => !selectableComparisonIds.value.includes(id))),
  }), key: 'compare', width: 40, align: 'center', fixed: 'left', render: (run) => h(BaseCheckbox, {
    checked: selectedComparisonIds.value.includes(run.run_id),
    disabled: run.status !== 'succeeded',
    'data-testid': `comparison-select-${run.run_id}`,
    'aria-label': `Compare run ${comparisonRunLabel(run)}`,
    onClick: (event: MouseEvent) => event.stopPropagation(),
    onKeydown: (event: KeyboardEvent) => event.stopPropagation(),
    'onUpdate:checked': () => toggleComparison(run),
  }) },
  { title: 'Run', key: 'ordinal', width: 64, fixed: 'left',
    render: (run) => h('span', { class: 'run-identity' }, cell(comparisonRunLabel(run), run.run_id)),
    sorter: (a, b) => compareRuns(a, b, 'ordinal'),
    sortOrder: comparisonSortKey.value === 'ordinal' ? comparisonSortOrder.value : false as const },
  ...optionalColumns.value.filter((column) => columnSettings.value.visibleKeys.includes(column.key))
    .map((column) => ({ ...column,
      ...(comparisonSortKeys.includes(column.key as ComparisonSortKey) ? {
        sorter: (a: BacktestRun, b: BacktestRun) => compareRuns(a, b,
          column.key as ComparisonSortKey),
        sortOrder: comparisonSortKey.value === column.key ? comparisonSortOrder.value : false as const,
      } : {}),
    })),
  { title: 'Actions', key: 'actions', width: analysisActionsWidth.value, fixed: 'right', render: analysisRunActions },
]);
const comparisonSortKeys: string[] = ['ordinal', 'status', 'market', 'timeframe',
  'capital', 'return', 'drawdown'];
const comparisonScrollWidth = computed(() => 104 + analysisActionsWidth.value + optionalColumns.value
  .filter((column) => columnSettings.value.visibleKeys.includes(column.key))
  .reduce((width, column) => width + column.width, 0));

function updateComparisonSort(sorter: { columnKey: string | number; order: 'ascend' | 'descend' | false }) {
  analysisPage.value = 1;
  if (sorter.order && comparisonSortKeys.includes(String(sorter.columnKey))) {
    comparisonSortKey.value = String(sorter.columnKey) as ComparisonSortKey;
    comparisonSortOrder.value = sorter.order;
  } else {
    comparisonSortKey.value = 'ordinal';
    comparisonSortOrder.value = 'ascend';
  }
}
function resetColumns(): void {
  columnSettings.value.visibleKeys = [...defaultColumns];
}
function setColumn(key: string, checked: boolean): void {
  columnSettings.value.visibleKeys = checked
    ? [...new Set([...columnSettings.value.visibleKeys, key])]
    : columnSettings.value.visibleKeys.filter((column) => column !== key);
}
function setColumnGroup(columns: ComparisonColumn[], checked: boolean): void {
  const keys = columns.map((column) => column.key);
  columnSettings.value.visibleKeys = checked
    ? [...new Set([...columnSettings.value.visibleKeys, ...keys])]
    : columnSettings.value.visibleKeys.filter((key) => !keys.includes(key));
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
  if (!['succeeded', 'failed', 'cancelled'].includes(run.status) ||
    deletingRunIds.value.has(run.run_id)) return;
  if (!window.confirm('Delete this Backtest and all saved results, trades and fills? This cannot be undone.')) return;
  deletingRunIds.value = new Set([...deletingRunIds.value, run.run_id]);
  deleteError.value = null;
  try {
    await deleteBacktestRun(run.run_id);
    if (logRun.value?.run_id === run.run_id) logRun.value = null;
    if (selectedRunId.value === run.run_id) {
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
    }
    if (overlayStore.selectedRunId === run.run_id) {
      overlayStore.clearOverlay();
      selectionNotice.value = 'The deleted Backtest Run was removed from the chart overlay.';
    }
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

async function deleteBatch(batch: BacktestBatch): Promise<void> {
  if (!['completed', 'cancelled'].includes(batch.status) ||
    deletingBatchIds.value.has(batch.batch_id)) return;
  if (!window.confirm('Delete this entire Backtest Batch, all members and saved results? This cannot be undone.')) return;
  deletingBatchIds.value = new Set([...deletingBatchIds.value, batch.batch_id]);
  deleteError.value = null;
  try {
    await deleteBacktestBatch(batch.batch_id);
    const overlayBelongsToBatch = overlayStore.selectedRun?.batch_id === batch.batch_id ||
      batchMembers.value.some((member) => member.run_id === overlayStore.selectedRunId);
    if (selectedBatchId.value === batch.batch_id) {
      selectedBatchId.value = null;
      batchMembers.value = [];
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
      logRun.value = null;
      selectionNotice.value = 'The deleted Backtest Batch is no longer selected.';
    }
    if (overlayBelongsToBatch) {
      overlayStore.clearOverlay();
      selectionNotice.value = 'The deleted Backtest Batch was removed from the chart overlay.';
    }
    void queueHealth.value?.refresh();
    await loadRuns();
  } catch (error) {
    deleteError.value = errorMessage(error);
  } finally {
    const stillDeleting = new Set(deletingBatchIds.value);
    stillDeleting.delete(batch.batch_id);
    deletingBatchIds.value = stillDeleting;
  }
}

async function openOnChart(run: BacktestRun): Promise<void> {
  if (openingChartRunId.value !== null || overlayStore.isLoading || chartUnavailableReason(run)) return;
  openingChartRunId.value = run.run_id;
  selectionNotice.value = null;
  try {
    if (marketsStore.all.length === 0) await marketsStore.fetch();
    const selection = await overlayStore.selectRun(run);
    if (selection.selectable) await router.push('/');
  } catch (error) {
    selectionNotice.value = `Could not open run ${comparisonRunLabel(run)} on chart: ${errorMessage(error)}`;
  } finally {
    openingChartRunId.value = null;
  }
}

function startPolling(): void {
  if (isActive) return;
  isActive = true;
  if (marketsStore.all.length === 0) void marketsStore.fetch();
  void loadRuns();
  loadAnalysis();
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
  pendingDetailId = null;
  analysisTokens.clear();
  logRun.value = null;
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

watch(() => router.currentRoute?.value.params, async (params) => {
  if (!params) return;
  if (!params.id) { page.value = 'history'; return; }
  const id = String(params.id);
  page.value = 'analysis';
  if (params.kind === 'batch') {
    if (selectedBatchId.value === id) return;
    selectedBatchId.value = id;
    batchMembers.value = [];
    workspaceStore.clearSelection();
    ++detailSequence;
    setComparison([]);
  } else if (params.kind === 'run' && (selectedBatchId.value || selectedRunId.value !== id)) {
    selectedBatchId.value = null;
    batchMembers.value = [];
    workspaceStore.clearSelection();
    setComparison([]);
    const sequence = ++detailSequence;
    detailLoading.value = true;
    try {
      const run = await getBacktestRun(id);
      if (sequence !== detailSequence) return;
      selectRun(run);
    } catch (error) {
      if (sequence === detailSequence) detailError.value = errorMessage(error);
    } finally {
      if (sequence === detailSequence) detailLoading.value = false;
    }
  }
}, { immediate: true });

onMounted(startPolling);
onActivated(startPolling);
onDeactivated(stopPolling);
onUnmounted(stopPolling);
</script>

<style scoped>
.workspace { font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; min-height: 100%; box-sizing: border-box; max-width: 1800px; margin: 0 auto; padding: 24px 30px 48px; color: #dce4ed; }
.workspace :deep(*) { font-family: inherit; }
.workspace-refresh { display: flex; justify-content: flex-end; align-items: center; gap: 12px; color: #8f9dab; font-size: 12px; margin-bottom: 12px; }
.workspace-header, .section-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.workspace-header { margin-bottom: 28px; }
.eyebrow { font-size: 11px; letter-spacing: .16em; color: #79c9b2; font-weight: 600; margin-bottom: 8px; }
.workspace-header h1 { margin: 0; font-size: 28px; font-weight: 600; letter-spacing: -.7px; text-transform: capitalize; }
.workspace-header p, .section-heading p { margin: 6px 0 0; color: #8f9dab; font-size: 13px; overflow-wrap: anywhere; }
.workspace-header > .n-button { flex-shrink: 0; }
.analysis-breadcrumb { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; color: #8291a2; font-size: 12px; }
.analysis-breadcrumb .n-button { color: #66dfbd; }
.workspace-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 24px 0; }
.workspace-summary > div { padding: 18px 22px; border: 1px solid #2b3541; border-radius: 10px; background: #1b222c; }
.workspace-summary span { display: block; color: #96a5b4; font-size: 12px; }
.workspace-summary strong { display: block; margin-top: 8px; font-size: 27px; font-weight: 500; font-variant-numeric: tabular-nums; }
.failure-count { color: #e7ae7b; }
.table-panel { border: 1px solid #2b3541; border-radius: 12px; background: #1a2029; padding: 22px; overflow: hidden; }
.section-heading h2 { margin: 0; font-size: 17px; font-weight: 600; }
.history-heading { margin-bottom: 22px; }
.filters { display: grid; grid-template-columns: minmax(220px, 2fr) repeat(6, minmax(110px, 1fr)); gap: 10px; margin-bottom: 20px; }
.current-backtest { margin-top: 24px; }
.analysis-context { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; color: #9aafbf; font-size: 12px; margin-bottom: 22px; }
.comparison-controls { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 16px; margin: 22px 0 16px; }
.column-count { color: #94a3b8; align-self: center; }
.column-popover { display: grid; gap: 18px; width: 100%; padding: 4px; box-sizing: border-box; }
.column-popover-footer { display: flex; justify-content: flex-end; border-top: 1px solid #2b3541; padding-top: 16px; }
.column-group + .column-group { border-top: 1px solid #2b3541; padding-top: 16px; }
.column-group-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.column-group h3 { margin: 0; color: #9aafbf; font-size: 12px; font-weight: 600; }
.column-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 16px; margin-top: 10px; }
@media (max-width: 480px) {
  .column-options { grid-template-columns: 1fr; }
}
.curve-status { list-style: none; display: flex; flex-wrap: wrap; gap: 8px 20px; padding: 0; font-size: 12px; color: #9aafbf; }
.request-details { margin-top: 24px; padding: 16px; border: 1px solid #303c49; border-radius: 8px; background: #171e27; }
.request-details summary { cursor: pointer; color: #b7c8d6; }
.curve-inspection { width: 100%; margin-top: 24px; }
.request-details dl { display: grid; grid-template-columns: max-content 1fr; gap: 8px 20px; font-size: 12px; }
.request-details dt { color: #8f9dab; }
.request-details dd { margin: 0; overflow-wrap: anywhere; }
.run-error { color: #f1b1a8; padding: 12px 16px; border-radius: 6px; background: #35272b; }
:deep(.run-cell) { display: inline-flex; align-items: center; gap: 10px; max-width: 100%; }
:deep(.run-identity) { min-width: 0; font-weight: 500; }
:deep(.run-status-icon) { display: inline-flex; vertical-align: middle; }
:deep(.run-identity small) { display: block; color: #8190a0; font-size: 10px; font-family: monospace; margin-top: 3px; }
:deep(.row-actions) { display: flex; align-items: center; gap: 4px; }
:deep(.run-chart-action) { display: inline-flex; align-items: center; }
:deep(.negative-metric) { color: #f0aaa2; }
:deep(.positive-metric) { color: #7dd5b4; }
:deep(.n-data-table-tr) { cursor: pointer; }
@media (max-width: 1200px) { .filters { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
@media (max-width: 700px) { .workspace-header { flex-wrap: wrap; } .workspace-header > .n-button { margin-left: auto; } .workspace-refresh { flex-wrap: wrap; } .workspace { padding: 16px 6px 32px; } .workspace-summary { grid-template-columns: repeat(2, 1fr); gap: 8px; } .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); } .table-panel { padding: 14px; } .section-heading { align-items: flex-start; } }
</style>
