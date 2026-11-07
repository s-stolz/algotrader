import { computed, ref, type Ref } from 'vue';
import type { SelectOption } from 'naive-ui';
import { BACKTEST_STATUSES, type Backtest } from '@/types/backtesterContracts';
import { backtestName } from '../backtestWorkspaceRuns';
import {
  backtestMarkets,
  backtestTimeframes,
  type HistoryEntry,
} from './backtestHistoryRows';
const statusOptions: SelectOption[] = [
  { label: 'All statuses', value: 'all' },
  ...BACKTEST_STATUSES.map((status) => ({ label: status, value: status })),
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
export function useBacktestHistory(backtests: Ref<Backtest[] | null>) {
  const historyPagination = ref({
    page: 1,
    pageSize: 15,
    onChange: (page: number) => {
      historyPagination.value.page = page;
    },
  });
  const search = ref('');
  const statusFilter = ref('all');
  const marketFilter = ref('all');
  const strategyFilter = ref('all');
  const timeframeFilter = ref('all');
  const failedFilter = ref('all');
  const marketOptions = computed(() =>
    optionsFrom(
      [...(backtests.value ?? []).flatMap(backtestMarkets)],
      'All Markets',
    ),
  );
  const strategyOptions = computed(() =>
    optionsFrom(
      [...(backtests.value ?? []).map((backtest) => backtest.strategy_id)],
      'All Strategies',
    ),
  );
  const timeframeOptions = computed(() =>
    optionsFrom(
      [...(backtests.value ?? []).flatMap(backtestTimeframes)],
      'All Timeframes',
    ),
  );

  const historyRows = computed<HistoryEntry[]>(() => [
    ...(backtests.value ?? []).map((backtest) => ({
      backtest,
    })),
  ]);
  const filteredHistory = computed(() =>
    historyRows.value.filter((entry) => {
      const query = search.value.trim().toLowerCase();
      const backtest = entry.backtest;
      return (
        (statusFilter.value === 'all' ||
          backtest.status === statusFilter.value) &&
        (failedFilter.value === 'all' || backtest.has_failed_members) &&
        (marketFilter.value === 'all' ||
          backtestMarkets(backtest).includes(marketFilter.value)) &&
        (strategyFilter.value === 'all' ||
          backtest.strategy_id === strategyFilter.value) &&
        (timeframeFilter.value === 'all' ||
          backtestTimeframes(backtest).includes(timeframeFilter.value)) &&
        (!query ||
          [
            backtestName(backtest),
            backtest.backtest_id,
            backtest.submission_id,
            backtest.status,
            backtest.strategy_id,
            ...backtestMarkets(backtest),
            ...backtestTimeframes(backtest),
          ].some((value) => value.toLowerCase().includes(query)))
      );
    }),
  );

  return {
    historyPagination,
    search,
    statusFilter,
    marketFilter,
    strategyFilter,
    timeframeFilter,
    failedFilter,
    statusOptions,
    failedOptions,
    marketOptions,
    strategyOptions,
    timeframeOptions,
    historyRows,
    filteredHistory,
  };
}
