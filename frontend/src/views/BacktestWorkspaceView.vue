<template>
  <n-config-provider :theme-overrides="workspaceTheme">
    <main class="workspace">
      <header
        v-if="page === 'analysis'"
        class="workspace-header"
      >
        <nav
          class="analysis-breadcrumb"
          aria-label="Backtest location"
        >
          <n-button
            text
            data-testid="workspace-history-return"
            @click="backToHistory"
          >
            <template #icon><n-icon :component="ArrowBackOutline" /></template
            >All backtests
          </n-button>
        </nav>
        <n-button
          type="primary"
          data-testid="workspace-create"
          @click="creationOpen = true"
        >
          <template #icon><n-icon :component="AddOutline" /></template>Create
          Backtest
        </n-button>
      </header>

      <BacktestCreationDrawer
        v-model:show="creationOpen"
        @submitted="createdRun"
        @submitted-batch="createdBatch"
      />

      <BacktestQueueHealth ref="queueHealth" />
      <p
        v-if="readError"
        role="alert"
      >
        Run history unavailable; current lifecycle status is unknown.
        {{ readError }}
        <n-button
          data-testid="workspace-refresh"
          size="small"
          quaternary
          :loading="isRefreshing"
          @click="refreshWorkspace"
        >
          <template #icon><n-icon :component="RefreshOutline" /></template>Retry
          now
        </n-button>
      </p>
      <p
        v-if="deleteError"
        role="alert"
        >{{ deleteError }}</p
      >
      <p
        v-if="selectionNotice"
        role="status"
        >{{ selectionNotice }}</p
      >
      <p
        v-if="cancelError"
        role="alert"
        >{{ cancelError }}</p
      >

      <BacktestHistory
        v-show="page === 'history'"
        :history="workspace.history"
        :actions="workspace.historyActions"
        :can-create="page === 'history'"
      />

      <section
        v-show="page === 'analysis'"
        class="current-backtest"
        aria-label="Current Backtest"
      >
        <BacktestBatches
          :batch-id="selectedBatchId"
          @members="receiveMembers"
          @cancelled="refreshWorkspace"
        />
        <div class="table-panel">
          <div
            v-if="selectedRun && !selectedBatchId"
            class="run-heading"
          >
            <h2 class="strategy-name">
              <ExperimentName
                v-if="!selectedRun.batch_id"
                kind="run"
                :experiment-id="selectedRun.run_id"
                :name="selectedRun.name"
              />
              <template v-else>{{ runName(selectedRun) }}</template>
            </h2>
            <div class="analysis-context">
              <n-tag
                size="small"
                :bordered="false"
                >Standalone run</n-tag
              >
              <span>{{ strategyVersion(selectedRun) }}</span>
              <span>{{ runMarket(selectedRun) }}</span
              ><span>{{ selectedRun.request.timeframe }}</span>
              <span
                >{{ formatUtcDate(selectedRun.request.start_ms) }} —
                {{ formatUtcDate(selectedRun.request.end_ms) }} UTC</span
              >
              <n-tag
                size="small"
                :type="
                  selectedRun.status === 'succeeded'
                    ? 'success'
                    : selectedRun.status === 'failed'
                      ? 'error'
                      : 'info'
                "
                :bordered="false"
                >{{ selectedRun.status }}</n-tag
              >
            </div>
          </div>
          <div
            v-else
            class="section-heading"
          >
            <h2>Results</h2>
          </div>
          <p v-if="!selectedRunId && !selectedBatchId"
            >Select a saved run or Batch to inspect its request and results.</p
          >
          <p
            v-if="detailError"
            role="alert"
            >{{ detailError }}</p
          >
          <p
            v-if="overlayStore.error"
            role="alert"
            >{{ overlayStore.error }}</p
          >
          <template v-if="currentRows.length">
            <div class="comparison-controls">
              <span class="column-count"
                >{{ columnSettings.visibleKeys.length }} columns shown</span
              >
              <BasePopover
                trigger="click"
                placement="bottom-end"
                :width="500"
                :style="{
                  maxWidth: 'calc(100vw - 32px)',
                  marginBottom: '16px',
                }"
              >
                <template #trigger>
                  <n-button
                    size="small"
                    round
                    data-testid="comparison-columns"
                    aria-label="Run analysis columns"
                  >
                    <template #icon
                      ><n-icon :component="OptionsOutline" /></template
                    >Columns
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
                        :checked="
                          columnSettings.visibleKeys.includes(column.key)
                        "
                        :data-testid="`comparison-column-${column.key}`"
                        @update:checked="setColumn(column.key, $event)"
                      >
                        {{ column.title }}
                      </BaseCheckbox>
                    </div>
                  </section>
                  <div
                    v-if="!hasDefaultColumns"
                    class="column-popover-footer"
                  >
                    <n-button
                      size="small"
                      round
                      data-testid="comparison-reset-columns"
                      @click="resetColumns"
                    >
                      <template #icon
                        ><n-icon :component="RefreshOutline" /></template
                      >Reset to default
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
            <p class="column-count"
              >The header checkbox selects successful runs on this page.
              Selections are retained across pages.</p
            >
            <p
              v-if="compatibilityDifferences.length"
              data-testid="comparison-compatibility"
              role="note"
            >
              Compared runs differ in {{ compatibilityDifferences.join(', ') }}.
              Interpret their results in context.
            </p>
            <p
              v-if="selectedComparisonIds.length === 0"
              role="status"
            >
              Select successful runs to inspect exact equity and drawdown.
            </p>
            <div
              v-else
              class="curve-inspection"
            >
              <ul
                v-if="curveStatusIds.length"
                class="curve-status"
              >
                <li
                  v-for="id in curveStatusIds"
                  :key="id"
                  :data-testid="`curve-status-${id}`"
                >
                  {{ analysisRunName(id) }}:
                  <template v-if="analysis[id]?.error"
                    >Exact Equity Replay read failed: {{ analysis[id]?.error }}.
                    Saved metrics remain available.</template
                  >
                  <template
                    v-else-if="
                      analysis[id]?.curve?.availability === 'unavailable'
                    "
                    >Exact Equity Replay unavailable:
                    {{ equityUnavailableReason(analysis[id]?.curve?.reason) }}.
                    Saved metrics remain available.</template
                  >
                </li>
              </ul>
              <EquityReplayCharts
                v-if="chartSeries.length"
                :series="chartSeries"
                :sampled="hasSampledCurve"
              />
            </div>
          </template>
          <template v-if="selectedRun">
            <p
              v-if="selectedRun.error_message"
              class="run-error"
            >
              {{ selectedRun.error_message }}
            </p>
            <details class="request-details">
              <summary>Saved request and execution settings</summary>
              <dl>
                <dt>Run ID</dt><dd>{{ selectedRun.run_id }}</dd>
                <dt>Strategy parameters</dt>
                <dd>{{
                  JSON.stringify(selectedRun.request.strategy.parameters)
                }}</dd>
                <dt>Engine</dt><dd>{{ selectedRun.request.engine }}</dd>
                <dt>Data granularity</dt
                ><dd>{{ selectedRun.request.data_granularity }}</dd>
                <dt>Allowed Directions</dt>
                <dd>{{ selectedRun.request.execution.allowed_directions }}</dd>
                <dt>Execution settings</dt>
                <dd>{{ JSON.stringify(selectedRun.request.execution) }}</dd>
                <dt>Submitted</dt
                ><dd>{{ formatTimestamp(selectedRun.submitted_at_ms) }}</dd>
                <dt>Started</dt
                ><dd>{{ formatTimestamp(selectedRun.started_at_ms) }}</dd>
                <dt>Completed</dt
                ><dd>{{ formatTimestamp(selectedRun.completed_at_ms) }}</dd>
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
import { computed, h, ref, watch } from 'vue';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import BasePopover from '@/components/Common/BasePopover.vue';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import { baseSelectTheme } from '@/components/Common/baseSelectTheme';
import {
  NButton,
  NCheckbox,
  NConfigProvider,
  NIcon,
  NSkeleton,
  NTag,
  NTooltip,
} from 'naive-ui';
import type {
  DataTableColumns,
  GlobalThemeOverrides,
  PaginationProps,
} from 'naive-ui';
import {
  DocumentTextOutline,
  BarChartOutline,
  ArrowBackOutline,
  AddOutline,
  RefreshOutline,
  OptionsOutline,
  StopCircleOutline,
  TimeOutline,
  PlayCircleOutline,
  HourglassOutline,
  CheckmarkCircleOutline,
  CloseCircleOutline,
  BanOutline,
} from '@vicons/ionicons5';

import ExecutionLogDrawer from '@/components/Backtest/ExecutionLogDrawer.vue';
import ExperimentName from '@/components/Backtest/ExperimentName.vue';
import BacktestBatches from '@/components/Backtest/BacktestBatches.vue';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';

import {
  type BacktestRun,
  type BacktestRunStatus,
} from '@/types/backtesterContracts';
import BacktestCreationDrawer from './BacktestCreationDrawer.vue';

import EquityReplayCharts from './EquityReplayCharts.vue';
import {
  compareRuns,
  differingSettings,
  type ComparisonSortKey,
  type ReplaySeries,
} from './backtestComparison';

import {
  displayWinRate,
  equityUnavailableReason,
  formatMagnitude,
  formatSigned,
  formatUtcDate,
  runMarket,
  runName,
  savedMetric,
  strategyVersion,
} from './backtestWorkspaceRuns';

import BacktestHistory from './workspace/BacktestHistory.vue';
import { useBacktestWorkspace } from './workspace/useBacktestWorkspace';
import {
  executionLogAvailable,
  executionLogUnavailableReason,
} from './workspace/workspaceExecution';
defineOptions({ name: 'BacktestWorkspaceView' });

const workspace = useBacktestWorkspace();
const {
  overlayStore,
  selectedRunId,
  selectedRun,
  selectedBatchId,
  detailError,
  selectionNotice,
  creationOpen,
  page,
  queueHealth,
  logRun,
  openingChartRunId,
  backToHistory,
  refreshWorkspace,
  selectRun,
  receiveMembers,
  createdRun,
  createdBatch,
  chartUnavailableReason,
  openOnChart,
} = workspace;
const { isRefreshing, readError } = workspace.history;
const { cancelError, deleteError, cancellingRunIds, cancelRun } =
  workspace.commands;
const {
  analysis,
  selectedComparisonIds,
  currentRows,
  setComparison,
  toggleComparison,
} = workspace.inspection;

const ALL_ANALYSIS_ROWS = Number.MAX_SAFE_INTEGER;
const workspaceTheme: GlobalThemeOverrides = {
  common: {
    fontFamily:
      'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
  },
  Select: baseSelectTheme,
};
const defaultColumns = [
  'status',
  'market',
  'timeframe',
  'capital',
  'return',
  'drawdown',
  'ending',
  'trades',
];
const columnSettings = ref({ visibleKeys: [...defaultColumns] });
const hasDefaultColumns = computed(
  () =>
    columnSettings.value.visibleKeys.length === defaultColumns.length &&
    defaultColumns.every((key) =>
      columnSettings.value.visibleKeys.includes(key),
    ),
);
const comparisonSortKey = ref<ComparisonSortKey>('ordinal');
const comparisonSortOrder = ref<'ascend' | 'descend'>('ascend');
const sortedCurrentRows = computed(() =>
  [...currentRows.value].sort(
    (left, right) =>
      (comparisonSortOrder.value === 'ascend' ? 1 : -1) *
      compareRuns(left, right, comparisonSortKey.value),
  ),
);
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
  onChange: (page: number) => {
    analysisPage.value = page;
  },
  onUpdatePageSize: (size: number) => {
    analysisPageSize.value = size;
    analysisPage.value = 1;
  },
}));
const visibleAnalysisRows = computed(() =>
  sortedCurrentRows.value.slice(
    (analysisPage.value - 1) * analysisPageSize.value,
    analysisPage.value * analysisPageSize.value,
  ),
);
const selectedComparisonRuns = computed(() =>
  selectedComparisonIds.value
    .map((id) => currentRows.value.find((run) => run.run_id === id))
    .filter((run): run is BacktestRun => run?.status === 'succeeded'),
);
const compatibilityDifferences = computed(() =>
  differingSettings(selectedComparisonRuns.value),
);
const curveStatusIds = computed(() =>
  selectedComparisonIds.value.filter(
    (id) =>
      analysis.value[id]?.error ||
      analysis.value[id]?.curve?.availability === 'unavailable',
  ),
);
const hasSampledCurve = computed(() =>
  selectedComparisonIds.value.some((id) => analysis.value[id]?.curve?.sampled),
);
const chartSeries = computed<ReplaySeries[]>(() =>
  selectedComparisonRuns.value.flatMap((run) => {
    const curve = analysis.value[run.run_id]?.curve;
    return curve?.availability === 'exact'
      ? [
          {
            runId: run.run_id,
            name: comparisonRunLabel(run),
            ordinal: run.member_ordinal,
            points: curve.equity_curve,
          },
        ]
      : [];
  }),
);
watch(
  () => currentRows.value.length,
  (count) => {
    analysisPage.value = Math.min(
      analysisPage.value,
      Math.max(1, Math.ceil(count / analysisPageSize.value)),
    );
  },
);
watch(
  () => selectedBatchId.value ?? selectedRun.value?.run_id,
  () => {
    analysisPage.value = 1;
  },
);
function analysisRunName(id: string): string {
  const run = currentRows.value.find((candidate) => candidate.run_id === id);
  return run ? comparisonRunLabel(run) : id;
}

function comparisonRunLabel(run: BacktestRun): string {
  return runName(run);
}

function cell(value: string, explanation?: string) {
  return h(
    'span',
    {
      title: explanation ?? value,
      class: 'ellipsis-cell',
      style: {
        display: 'block',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      },
    },
    value,
  );
}

function executionLogAction(run: BacktestRun, label: string) {
  const available = executionLogAvailable(run);
  return h(NTooltip, null, {
    trigger: () =>
      h('span', { class: 'run-log-action' }, [
        h(
          NButton,
          {
            text: true,
            size: 'small',
            'data-testid': `workspace-log-${run.run_id}`,
            'aria-label': available
              ? `View execution log for ${label}`
              : `Execution log unavailable for ${label}`,
            disabled: !available,
            onKeydown: (event: KeyboardEvent) => {
              event.stopPropagation();
            },
            onClick: (event: MouseEvent) => {
              event.stopPropagation();
              if (!available) return;
              logRun.value = run;
            },
          },
          {
            icon: () =>
              h(
                NIcon,
                {
                  size: 16,
                  class: available ? undefined : 'unavailable-log-icon',
                },
                { default: () => h(DocumentTextOutline) },
              ),
          },
        ),
      ]),
    default: () =>
      available ? 'View execution log' : executionLogUnavailableReason(run),
  });
}

function analysisRunActions(run: BacktestRun) {
  return h('div', { class: 'row-actions' }, [
    executionLogAction(run, comparisonRunLabel(run)),
    h(NTooltip, null, {
      trigger: () =>
        h('span', { class: 'run-chart-action' }, [
          h(
            NButton,
            {
              text: true,
              size: 'small',
              'data-testid': `workspace-chart-${run.run_id}`,
              'aria-label': `Open ${comparisonRunLabel(run)} on chart`,
              disabled:
                openingChartRunId.value !== null ||
                overlayStore.isLoading ||
                !!chartUnavailableReason(run),
              loading: openingChartRunId.value === run.run_id,
              onKeydown: (event: KeyboardEvent) => {
                event.stopPropagation();
              },
              onClick: (event: MouseEvent) => {
                event.stopPropagation();
                void openOnChart(run);
              },
            },
            { icon: () => h(NIcon, { size: 16, component: BarChartOutline }) },
          ),
        ]),
      default: () => chartUnavailableReason(run) ?? 'Open on chart',
    }),
    ...(['queued', 'running'].includes(run.status)
      ? [
          h(NTooltip, null, {
            trigger: () =>
              h(
                NButton,
                {
                  text: true,
                  size: 'small',
                  'data-testid': `workspace-cancel-${run.run_id}`,
                  'aria-label': `Cancel ${comparisonRunLabel(run)}`,
                  disabled: cancellingRunIds.value.has(run.run_id),
                  loading: cancellingRunIds.value.has(run.run_id),
                  onKeydown: (event: KeyboardEvent) => {
                    event.stopPropagation();
                  },
                  onClick: (event: MouseEvent) => {
                    event.stopPropagation();
                    void cancelRun(run);
                  },
                },
                {
                  icon: () =>
                    h(NIcon, { size: 16, component: StopCircleOutline }),
                },
              ),
            default: () => 'Cancel run',
          }),
        ]
      : []),
  ]);
}

function metricCell(
  run: BacktestRun,
  key: string,
  explanation: string,
  suffix = '',
  positiveMagnitude = false,
) {
  const value = run.status === 'succeeded' ? savedMetric(run, key) : null;
  const display = positiveMagnitude
    ? formatMagnitude(value, suffix)
    : formatSigned(value, suffix);
  return h(
    'span',
    {
      class:
        value == null || positiveMagnitude
          ? undefined
          : value < 0
            ? 'negative-metric'
            : value > 0
              ? 'positive-metric'
              : undefined,
    },
    cell(display, explanation),
  );
}
function countCell(run: BacktestRun, key: string, explanation: string) {
  return cell(
    run.status === 'succeeded'
      ? (savedMetric(run, key)?.toString() ?? '—')
      : '—',
    explanation,
  );
}
function directionPnl(run: BacktestRun, direction: 'long' | 'short') {
  if (run.status !== 'succeeded') return cell('—');
  const count = savedMetric(run, `${direction}_trade_count`);
  const pnl = count === 0 ? 0 : savedMetric(run, `${direction}_realized_pnl`);
  return cell(
    formatSigned(pnl),
    'Saved sum of realized PnL from ' +
      direction +
      ' Closed Trades, signed account units. Zero when there were no trades.',
  );
}
const runStatusIcons = {
  queued: { icon: TimeOutline, label: 'Queued', color: '#9aafbf' },
  running: { icon: PlayCircleOutline, label: 'Running', color: '#70c0e8' },
  cancelling: { icon: HourglassOutline, label: 'Cancelling', color: '#e8bc70' },
  succeeded: {
    icon: CheckmarkCircleOutline,
    label: 'Succeeded',
    color: '#7cd8b7',
  },
  failed: { icon: CloseCircleOutline, label: 'Failed', color: '#e88b8b' },
  cancelled: { icon: BanOutline, label: 'Cancelled', color: '#9aafbf' },
} satisfies Record<
  BacktestRunStatus,
  { icon: typeof TimeOutline; label: string; color: string }
>;

function runStatusCell(run: BacktestRun) {
  const { icon, label, color } = runStatusIcons[run.status];
  return h(NTooltip, null, {
    trigger: () =>
      h(
        'span',
        {
          class: 'run-status-icon',
          role: 'img',
          'aria-label': label,
          tabindex: 0,
        },
        h(NIcon, {
          component: icon,
          size: 20,
          color,
          'aria-hidden': true,
        }),
      ),
    default: () => label,
  });
}

type ComparisonColumn = {
  title: string;
  key: string;
  width: number;
  align?: 'center';
  group: 'Run settings' | 'Performance' | 'Long / short';
  render: (run: BacktestRun) => ReturnType<typeof h>;
};
const parameterKeys = computed(() =>
  [
    ...new Set(
      currentRows.value.flatMap((run) =>
        Object.keys(run.request.strategy.parameters),
      ),
    ),
  ].sort(),
);
const optionalColumns = computed<ComparisonColumn[]>(() => [
  {
    title: 'Status',
    key: 'status',
    group: 'Run settings',
    width: 100,
    align: 'center',
    render: runStatusCell,
  },
  {
    title: 'Strategy / version',
    key: 'strategy',
    group: 'Run settings',
    width: 190,
    render: (run) =>
      cell(`${run.request.strategy.strategy_id} · ${strategyVersion(run)}`),
  },
  {
    title: 'Market',
    key: 'market',
    group: 'Run settings',
    width: 165,
    render: (run) => cell(runMarket(run)),
  },
  {
    title: 'Timeframe',
    key: 'timeframe',
    group: 'Run settings',
    width: 120,
    render: (run) => cell(run.request.timeframe),
  },
  {
    title: 'Start',
    key: 'start',
    group: 'Run settings',
    width: 130,
    render: (run) => cell(formatUtcDate(run.request.start_ms)),
  },
  {
    title: 'End',
    key: 'end',
    group: 'Run settings',
    width: 130,
    render: (run) => cell(formatUtcDate(run.request.end_ms)),
  },
  {
    title: 'Initial capital',
    key: 'capital',
    group: 'Performance',
    width: 155,
    render: (run) =>
      cell(
        String(run.request.initial_capital),
        'Saved request Initial capital, in account units.',
      ),
  },
  {
    title: 'Engine',
    key: 'engine',
    group: 'Run settings',
    width: 150,
    render: (run) => cell(run.request.engine),
  },
  {
    title: 'Allowed Directions',
    key: 'directions',
    group: 'Run settings',
    width: 165,
    render: (run) => cell(run.request.execution.allowed_directions),
  },
  {
    title: 'Commission (bps)',
    key: 'commission',
    group: 'Run settings',
    width: 155,
    render: (run) => cell(String(run.request.execution.commission_bps)),
  },
  {
    title: 'Slippage (bps)',
    key: 'slippage',
    group: 'Run settings',
    width: 150,
    render: (run) => cell(String(run.request.execution.slippage_bps)),
  },
  ...parameterKeys.value.map((name) => ({
    title: `Parameter: ${name}`,
    key: `parameter:${name}`,
    group: 'Run settings' as const,
    width: 180,
    render: (run: BacktestRun) =>
      cell(
        Object.hasOwn(run.request.strategy.parameters, name)
          ? JSON.stringify(run.request.strategy.parameters[name])
          : '—',
      ),
  })),
  {
    title: 'Return (%)',
    key: 'return',
    group: 'Performance',
    width: 145,
    render: (run) =>
      metricCell(
        run,
        'total_return_pct',
        'Saved signed percentage: (ending equity / first recorded equity − 1) × 100. First recorded equity follows the first Candle executions and fees; it can differ from Initial capital.',
        '%',
      ),
  },
  {
    title: 'Max drawdown (%)',
    key: 'drawdown',
    group: 'Performance',
    width: 175,
    render: (run) =>
      metricCell(
        run,
        'max_drawdown_pct',
        'Positive magnitude of the saved largest peak-to-trough recorded equity loss, in percent.',
        '%',
        true,
      ),
  },
  {
    title: 'Ending equity',
    key: 'ending',
    group: 'Performance',
    width: 155,
    render: (run) =>
      analysis.value[run.run_id]?.loading && !analysis.value[run.run_id]?.curve
        ? h(
            'span',
            {
              role: 'status',
              'aria-label': 'Loading ending equity',
              'data-testid': `ending-loading-${run.run_id}`,
            },
            h(NSkeleton, {
              width: 90,
              height: 16,
              themeOverrides: { color: '#253340', colorEnd: '#354757' },
            }),
          )
        : cell(
            run.status === 'succeeded' &&
              analysis.value[run.run_id]?.curve?.availability === 'exact'
              ? formatSigned(
                  analysis.value[run.run_id]?.curve?.equity_curve.at(-1)
                    ?.equity,
                ).replace(/^\+/, '')
              : '—',
            'Final point of exact Equity Replay, in account units. Unavailable replay leaves this missing.',
          ),
  },
  {
    title: 'Trades',
    key: 'trades',
    group: 'Performance',
    width: 115,
    render: (run) =>
      countCell(
        run,
        'trade_count',
        'Saved count of Closed Trades. Zero is different from a missing result.',
      ),
  },
  {
    title: 'Long trades',
    key: 'long-count',
    group: 'Long / short',
    width: 135,
    render: (run) =>
      countCell(run, 'long_trade_count', 'Saved count of long Closed Trades.'),
  },
  {
    title: 'Long win rate',
    key: 'long-win',
    group: 'Long / short',
    width: 150,
    render: (run) =>
      cell(
        run.status === 'succeeded' ? displayWinRate(run, 'long') : '—',
        'Profitable long Closed Trades divided by long Closed Trades, in percent; No trades if count is zero.',
      ),
  },
  {
    title: 'Long PnL',
    key: 'long-pnl',
    group: 'Long / short',
    width: 140,
    render: (run) => directionPnl(run, 'long'),
  },
  {
    title: 'Short trades',
    key: 'short-count',
    group: 'Long / short',
    width: 140,
    render: (run) =>
      countCell(
        run,
        'short_trade_count',
        'Saved count of short Closed Trades.',
      ),
  },
  {
    title: 'Short win rate',
    key: 'short-win',
    group: 'Long / short',
    width: 155,
    render: (run) =>
      cell(
        run.status === 'succeeded' ? displayWinRate(run, 'short') : '—',
        'Profitable short Closed Trades divided by short Closed Trades, in percent; No trades if count is zero.',
      ),
  },
  {
    title: 'Short PnL',
    key: 'short-pnl',
    group: 'Long / short',
    width: 140,
    render: (run) => directionPnl(run, 'short'),
  },
]);
const columnGroups = computed(() =>
  ['Run settings', 'Performance', 'Long / short'].map((title) => {
    const columns = optionalColumns.value.filter(
      (column) => column.group === title,
    );
    const enabledCount = columns.filter((column) =>
      columnSettings.value.visibleKeys.includes(column.key),
    ).length;
    return {
      title,
      columns,
      enabled: enabledCount === columns.length,
      indeterminate: enabledCount > 0 && enabledCount < columns.length,
    };
  }),
);
const analysisActionsWidth = computed(() =>
  currentRows.value.some((run) => ['queued', 'running'].includes(run.status))
    ? 92
    : 68,
);
const selectableComparisonIds = computed(() =>
  visibleAnalysisRows.value
    .filter((run) => run.status === 'succeeded')
    .map((run) => run.run_id),
);
const selectedComparisonCount = computed(
  () =>
    selectableComparisonIds.value.filter((id) =>
      selectedComparisonIds.value.includes(id),
    ).length,
);
const comparisonColumns = computed<DataTableColumns<BacktestRun>>(() => [
  {
    title: () =>
      h(NCheckbox, {
        checked:
          selectableComparisonIds.value.length > 0 &&
          selectedComparisonCount.value ===
            selectableComparisonIds.value.length,
        indeterminate:
          selectedComparisonCount.value > 0 &&
          selectedComparisonCount.value < selectableComparisonIds.value.length,
        disabled: selectableComparisonIds.value.length === 0,
        'data-testid': 'comparison-select-all',
        'aria-label': 'Select all successful runs on this page for comparison',
        onClick: (event: MouseEvent) => event.stopPropagation(),
        onKeydown: (event: KeyboardEvent) => event.stopPropagation(),
        'onUpdate:checked': (checked: boolean) =>
          setComparison(
            checked
              ? [
                  ...new Set([
                    ...selectedComparisonIds.value,
                    ...selectableComparisonIds.value,
                  ]),
                ]
              : selectedComparisonIds.value.filter(
                  (id) => !selectableComparisonIds.value.includes(id),
                ),
          ),
      }),
    key: 'compare',
    width: 40,
    align: 'center',
    fixed: 'left',
    render: (run) =>
      h(BaseCheckbox, {
        checked: selectedComparisonIds.value.includes(run.run_id),
        disabled: run.status !== 'succeeded',
        'data-testid': `comparison-select-${run.run_id}`,
        'aria-label': `Compare ${comparisonRunLabel(run)}`,
        onClick: (event: MouseEvent) => event.stopPropagation(),
        onKeydown: (event: KeyboardEvent) => event.stopPropagation(),
        'onUpdate:checked': () => toggleComparison(run),
      }),
  },
  {
    title: 'Run',
    key: 'ordinal',
    width: 64,
    fixed: 'left',
    render: (run) =>
      h('span', { class: 'run-identity' }, [
        cell(comparisonRunLabel(run), run.run_id),
        h('small', run.run_id.slice(0, 8)),
      ]),
    sorter: (a, b) => compareRuns(a, b, 'ordinal'),
    sortOrder:
      comparisonSortKey.value === 'ordinal'
        ? comparisonSortOrder.value
        : (false as const),
  },
  ...optionalColumns.value
    .filter((column) => columnSettings.value.visibleKeys.includes(column.key))
    .map((column) => ({
      ...column,
      ...(comparisonSortKeys.includes(column.key as ComparisonSortKey)
        ? {
            sorter: (a: BacktestRun, b: BacktestRun) =>
              compareRuns(a, b, column.key as ComparisonSortKey),
            sortOrder:
              comparisonSortKey.value === column.key
                ? comparisonSortOrder.value
                : (false as const),
          }
        : {}),
    })),
  {
    title: 'Actions',
    key: 'actions',
    width: analysisActionsWidth.value,
    fixed: 'right',
    render: analysisRunActions,
  },
]);
const comparisonSortKeys: string[] = [
  'ordinal',
  'status',
  'market',
  'timeframe',
  'capital',
  'return',
  'drawdown',
];
const comparisonScrollWidth = computed(
  () =>
    104 +
    analysisActionsWidth.value +
    optionalColumns.value
      .filter((column) => columnSettings.value.visibleKeys.includes(column.key))
      .reduce((width, column) => width + column.width, 0),
);

function updateComparisonSort(sorter: {
  columnKey: string | number;
  order: 'ascend' | 'descend' | false;
}) {
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
  return {
    'data-testid': `workspace-member-${run.run_id}`,
    'aria-selected': selectedRunId.value === run.run_id,
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

function formatTimestamp(timestamp: number | null | undefined): string {
  return timestamp == null ? '—' : new Date(timestamp).toISOString();
}
</script>

<style scoped>
.workspace {
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
  min-height: 100%;
  box-sizing: border-box;
  max-width: 1800px;
  margin: 0 auto;
  padding: 24px 30px 48px;
  color: #dce4ed;
}
.workspace :deep(*) {
  font-family: inherit;
}
.workspace-header,
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.workspace-header {
  min-height: 36px;
  margin-bottom: 20px;
}
.section-heading p {
  margin: 6px 0 0;
  color: #8f9dab;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.workspace-header > .n-button {
  flex-shrink: 0;
  margin-left: auto;
}
.analysis-breadcrumb {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  color: #8291a2;
  font-size: 12px;
}
.analysis-breadcrumb .n-button {
  color: #9aafbf;
}
.table-panel {
  border: 1px solid var(--surface-border);
  border-radius: 12px;
  background: var(--surface-panel);
  padding: 22px;
  overflow: hidden;
}
.section-heading h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.current-backtest {
  margin-top: 24px;
}
.run-heading h2 {
  margin: 0 0 12px;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
  overflow-wrap: anywhere;
}
.strategy-name {
  text-transform: capitalize;
}
.analysis-context {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  color: #9aafbf;
  font-size: 12px;
}
.comparison-controls {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  margin: 22px 0 16px;
}
.column-count {
  color: #94a3b8;
  align-self: center;
}
.column-popover {
  display: grid;
  gap: 18px;
  width: 100%;
  padding: 4px;
  box-sizing: border-box;
}
.column-popover-footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--surface-border);
  padding-top: 16px;
}
.column-group + .column-group {
  border-top: 1px solid var(--surface-border);
  padding-top: 16px;
}
.column-group-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.column-group h3 {
  margin: 0;
  color: #9aafbf;
  font-size: 12px;
  font-weight: 600;
}
.column-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
  margin-top: 10px;
}
@media (max-width: 480px) {
  .column-options {
    grid-template-columns: 1fr;
  }
}
.curve-status {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  padding: 0;
  font-size: 12px;
  color: #9aafbf;
}
.request-details {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: var(--surface-inset);
}
.request-details summary {
  cursor: pointer;
  color: #b7c8d6;
}
.curve-inspection {
  width: 100%;
  margin-top: 24px;
}
.request-details dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 8px 20px;
  font-size: 12px;
}
.request-details dt {
  color: #8f9dab;
}
.request-details dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.run-error {
  color: #f1b1a8;
  padding: 12px 16px;
  border-radius: 6px;
  background: #35272b;
}
:deep(.run-identity) {
  min-width: 0;
  font-weight: 500;
}
:deep(.run-status-icon) {
  display: inline-flex;
  vertical-align: middle;
}
:deep(.run-identity small) {
  display: block;
  color: #8190a0;
  font-size: 10px;
  font-family: monospace;
  margin-top: 3px;
}
:deep(.row-actions) {
  display: flex;
  align-items: center;
  gap: 4px;
}
:deep(.run-chart-action) {
  display: inline-flex;
  align-items: center;
}
:deep(.run-log-action) {
  display: inline-flex;
  align-items: center;
}
:deep(.unavailable-log-icon) {
  position: relative;
}
:deep(.unavailable-log-icon::after) {
  content: '';
  position: absolute;
  top: 50%;
  left: -2px;
  width: 20px;
  height: 1.5px;
  background: currentColor;
  transform: rotate(-45deg);
  pointer-events: none;
}
:deep(.negative-metric) {
  color: #f0aaa2;
}
:deep(.positive-metric) {
  color: #7dd5b4;
}
:deep(.n-data-table-tr) {
  cursor: pointer;
}
@media (max-width: 700px) {
  .workspace-header {
    flex-wrap: wrap;
  }
  .workspace {
    padding: 16px 6px 32px;
  }
  .table-panel {
    padding: 14px;
  }
  .section-heading {
    align-items: flex-start;
  }
}
</style>
