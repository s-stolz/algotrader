import { computed, h, ref, watch } from 'vue';
import type { DataTableColumns, PaginationProps } from 'naive-ui';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import { designTokens } from '@/design/tokens';
import type { BacktestRun } from '@/types/backtesterContracts';
import { compareRuns, type ComparisonSortKey } from '../../backtestComparison';
import { runName as comparisonRunLabel } from '../../backtestWorkspaceRuns';
import { cell } from './comparisonCells';
import {
  createOptionalColumns,
  type ComparisonColumn,
} from './comparisonOptionalColumns';
import { createComparisonRunActions } from './comparisonRunActions';
import type { BacktestWorkspace } from '../useBacktestWorkspace';
export function useWorkspaceComparison(workspace: BacktestWorkspace) {
  const { selectedBatchId, selectedRun, selectedRunId, selectRun } = workspace;
  const {
    currentRows,
    selectedComparisonIds,
    setComparison,
    toggleComparison,
    analysis,
  } = workspace.inspection;
  const ALL_ANALYSIS_ROWS = Number.MAX_SAFE_INTEGER;
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
  const optionalColumns = computed(() =>
    createOptionalColumns(currentRows, analysis),
  );
  const analysisRunActions = createComparisonRunActions(workspace);
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
  const analysisActionsWidth = computed(() => {
    const count = currentRows.value.some((run) =>
      ['queued', 'running'].includes(run.status),
    )
      ? 3
      : 2;
    return (
      count * Number.parseInt(designTokens.control.small) +
      (count - 1) * Number.parseInt(designTokens.space.xs) +
      2 * Number.parseInt(designTokens.space.md)
    );
  });
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
        h(BaseCheckbox, {
          checked:
            selectableComparisonIds.value.length > 0 &&
            selectedComparisonCount.value ===
              selectableComparisonIds.value.length,
          indeterminate:
            selectedComparisonCount.value > 0 &&
            selectedComparisonCount.value <
              selectableComparisonIds.value.length,
          disabled: selectableComparisonIds.value.length === 0,
          'data-testid': 'comparison-select-all',
          'aria-label':
            'Select all successful runs on this page for comparison',
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
        .filter((column) =>
          columnSettings.value.visibleKeys.includes(column.key),
        )
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
      style: { cursor: 'pointer' },
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

  return {
    columnSettings,
    columnGroups,
    hasDefaultColumns,
    resetColumns,
    setColumn,
    setColumnGroup,
    comparisonColumns,
    comparisonScrollWidth,
    sortedCurrentRows,
    currentRowProps,
    analysisPagination,
    updateComparisonSort,
  };
}
export type WorkspaceComparison = ReturnType<typeof useWorkspaceComparison>;
