import { computed, ref, type Ref } from 'vue';
import type { SelectOption } from 'naive-ui';
import {
  BACKTEST_RUN_STATUSES,
  BACKTEST_BATCH_STATUSES,
  type BacktestRun,
  type BacktestBatch,
} from '@/types/backtesterContracts';
import { runMarket, runName, batchName } from '../backtestWorkspaceRuns';
import {
  batchMarkets,
  batchTimeframes,
  type HistoryEntry,
} from './backtestHistoryRows';
const statusOptions: SelectOption[] = [
  { label: 'All statuses', value: 'all' },
  ...[...new Set([...BACKTEST_RUN_STATUSES, ...BACKTEST_BATCH_STATUSES])].map(
    (status) => ({ label: status, value: status }),
  ),
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
  return [
    { label: allLabel, value: 'all' },
    ...[...new Set(values)].sort().map((value) => ({ label: value, value })),
  ];
}
export function useBacktestHistory(
  runs: Ref<BacktestRun[] | null>,
  batches: Ref<BacktestBatch[] | null>,
) {
  const historyPagination = ref({
    page: 1,
    pageSize: 15,
    onChange: (page: number) => {
      historyPagination.value.page = page;
    },
  });
  const search = ref('');
  const statusFilter = ref('all');
  const typeFilter = ref('all');
  const marketFilter = ref('all');
  const strategyFilter = ref('all');
  const timeframeFilter = ref('all');
  const failedFilter = ref('all');
  const marketOptions = computed(() =>
    optionsFrom(
      [
        ...(runs.value ?? []).map(runMarket),
        ...(batches.value ?? []).flatMap(batchMarkets),
      ],
      'All Markets',
    ),
  );
  const strategyOptions = computed(() =>
    optionsFrom(
      [
        ...(runs.value ?? []).map((run) => run.request.strategy.strategy_id),
        ...(batches.value ?? []).map((batch) => batch.strategy_id),
      ],
      'All Strategies',
    ),
  );
  const timeframeOptions = computed(() =>
    optionsFrom(
      [
        ...(runs.value ?? []).map((run) => run.request.timeframe),
        ...(batches.value ?? []).flatMap(batchTimeframes),
      ],
      'All Timeframes',
    ),
  );

  const historyRows = computed<HistoryEntry[]>(() => [
    ...(runs.value ?? [])
      .filter((run) => !run.batch_id)
      .map((run) => ({ kind: 'run' as const, run })),
    ...(batches.value ?? []).map((batch) => ({
      kind: 'batch' as const,
      batch,
    })),
  ]);
  const activeHistoryCount = computed(
    () =>
      historyRows.value.filter((entry) =>
        entry.kind === 'run'
          ? ['queued', 'running', 'cancelling'].includes(entry.run.status)
          : !['completed', 'cancelled'].includes(entry.batch.status),
      ).length,
  );
  const completedHistoryCount = computed(
    () =>
      historyRows.value.filter((entry) =>
        entry.kind === 'run'
          ? entry.run.status === 'succeeded'
          : entry.batch.status === 'completed',
      ).length,
  );
  const failedHistoryCount = computed(
    () =>
      historyRows.value.filter((entry) =>
        entry.kind === 'run'
          ? entry.run.status === 'failed'
          : entry.batch.has_failed_members,
      ).length,
  );
  const filteredHistory = computed(() =>
    historyRows.value.filter((entry) => {
      const query = search.value.trim().toLowerCase();
      if (entry.kind === 'run') {
        const run = entry.run;
        return (
          (statusFilter.value === 'all' || run.status === statusFilter.value) &&
          (typeFilter.value === 'all' || typeFilter.value === 'standalone') &&
          (failedFilter.value === 'all' || run.status === 'failed') &&
          (marketFilter.value === 'all' ||
            runMarket(run) === marketFilter.value) &&
          (strategyFilter.value === 'all' ||
            run.request.strategy.strategy_id === strategyFilter.value) &&
          (timeframeFilter.value === 'all' ||
            run.request.timeframe === timeframeFilter.value) &&
          (!query ||
            [
              runName(run),
              run.run_id,
              run.status,
              runMarket(run),
              run.request.timeframe,
              run.request.strategy.strategy_id,
            ].some((value) => value.toLowerCase().includes(query)))
        );
      }
      const batch = entry.batch;
      return (
        (statusFilter.value === 'all' || batch.status === statusFilter.value) &&
        (typeFilter.value === 'all' || typeFilter.value === 'batch') &&
        (failedFilter.value === 'all' || batch.has_failed_members) &&
        (marketFilter.value === 'all' ||
          batchMarkets(batch).includes(marketFilter.value)) &&
        (strategyFilter.value === 'all' ||
          batch.strategy_id === strategyFilter.value) &&
        (timeframeFilter.value === 'all' ||
          batchTimeframes(batch).includes(timeframeFilter.value)) &&
        (!query ||
          [
            batchName(batch),
            batch.batch_id,
            batch.submission_id,
            batch.status,
            batch.strategy_id,
            ...batchMarkets(batch),
            ...batchTimeframes(batch),
          ].some((value) => value.toLowerCase().includes(query)))
      );
    }),
  );

  return {
    historyPagination,
    search,
    statusFilter,
    typeFilter,
    marketFilter,
    strategyFilter,
    timeframeFilter,
    failedFilter,
    statusOptions,
    typeOptions,
    failedOptions,
    marketOptions,
    strategyOptions,
    timeframeOptions,
    historyRows,
    activeHistoryCount,
    completedHistoryCount,
    failedHistoryCount,
    filteredHistory,
  };
}
