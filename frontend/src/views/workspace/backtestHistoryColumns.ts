import { h } from 'vue';
import { designTokens } from '@/design/tokens';
import { NButton, NIcon, NTag, type DataTableColumns } from 'naive-ui';
import {
  CopyOutline,
  TrashOutline,
  StopCircleOutline,
} from '@vicons/ionicons5';
import type { BacktestRun } from '@/types/backtesterContracts';
import {
  runName,
  batchName,
  strategyVersion,
  runMarket,
  formatUtcDate,
  type HistorySortKey,
} from '../backtestWorkspaceRuns';
import {
  rowKey,
  batchMarkets,
  batchTimeframes,
  compareHistoryEntries,
  type HistoryEntry,
} from './backtestHistoryRows';
import type { BacktestWorkspace } from './useBacktestWorkspace';
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

function historyRunCell(run: BacktestRun) {
  return h('span', { class: 'run-identity' }, [
    cell(runName(run), run.run_id),
    h('small', run.run_id.slice(0, 8)),
  ]);
}

function historyColumn(
  title: string,
  key: HistorySortKey | 'progress',
  render: (entry: HistoryEntry) => ReturnType<typeof h>,
): DataTableColumns<HistoryEntry>[number] {
  return {
    title,
    key,
    width:
      (
        {
          name: 235,
          type: 145,
          strategy: 190,
          market: 175,
          timeframe: 110,
          start: 125,
          end: 125,
          status: 120,
          progress: 125,
        } as Record<string, number>
      )[key] ?? 120,
    fixed: key === 'name' ? 'left' : undefined,
    sorter: (left, right) => compareHistoryEntries(left, right, key),
    ellipsis: { tooltip: true },
    render,
  };
}

export function createHistoryColumns(
  actions: BacktestWorkspace['historyActions'],
): DataTableColumns<HistoryEntry> {
  const { createFrom } = actions;
  const {
    cancellingRunIds,
    deletingRunIds,
    deletingBatchIds,
    cancelRun,
    deleteRun,
    deleteBatch,
  } = actions;
  const historyColumns: DataTableColumns<HistoryEntry> = [
    historyColumn('Name', 'name', (entry) =>
      entry.kind === 'run'
        ? historyRunCell(entry.run)
        : h('span', { class: 'run-identity' }, [
            cell(batchName(entry.batch), entry.batch.batch_id),
            h('small', entry.batch.batch_id.slice(0, 8)),
          ]),
    ),
    historyColumn('Type', 'type', (entry) =>
      cell(entry.kind === 'run' ? 'Standalone' : 'Parameter Sweep'),
    ),
    historyColumn('Strategy / version', 'strategy', (entry) =>
      cell(
        entry.kind === 'run'
          ? `${entry.run.request.strategy.strategy_id} · ${strategyVersion(entry.run)}`
          : `${entry.batch.strategy_id} · v${entry.batch.strategy_version}`,
      ),
    ),
    historyColumn('Market', 'market', (entry) =>
      cell(
        entry.kind === 'run'
          ? runMarket(entry.run)
          : batchMarkets(entry.batch).join(', '),
      ),
    ),
    historyColumn('Timeframe', 'timeframe', (entry) =>
      cell(
        entry.kind === 'run'
          ? entry.run.request.timeframe
          : batchTimeframes(entry.batch).join(', '),
      ),
    ),
    historyColumn('Start date', 'start', (entry) =>
      cell(
        formatUtcDate(
          entry.kind === 'run'
            ? entry.run.request.start_ms
            : Number(entry.batch.accepted_definition.shared_request.start_ms),
        ),
      ),
    ),
    historyColumn('End date', 'end', (entry) =>
      cell(
        formatUtcDate(
          entry.kind === 'run'
            ? entry.run.request.end_ms
            : Number(entry.batch.accepted_definition.shared_request.end_ms),
        ),
      ),
    ),
    historyColumn('Status', 'status', (entry) => {
      const status =
        entry.kind === 'run' ? entry.run.status : entry.batch.status;
      return h(
        NTag,
        {
          size: 'small',
          type:
            status === 'succeeded' || status === 'completed'
              ? 'success'
              : status === 'failed'
                ? 'error'
                : 'info',
          title:
            status === 'cancelling'
              ? 'Execution is being stopped; capacity stays held until exit is confirmed.'
              : undefined,
        },
        { default: () => status },
      );
    }),
    historyColumn('Settled', 'progress', (entry) =>
      cell(
        entry.kind === 'run'
          ? '—'
          : `${entry.batch.settled_count} / ${entry.batch.total_count}` +
              (entry.batch.has_failed_members
                ? ` · ${entry.batch.outcome_counts.failed} failed`
                : ''),
      ),
    ),
    {
      title: 'Actions',
      key: 'actions',
      width:
        3 * Number.parseInt(designTokens.control.small) +
        2 * Number.parseInt(designTokens.space.xs) +
        2 * Number.parseInt(designTokens.space.lg),
      fixed: 'right',
      render: (entry) =>
        h(
          'div',
          {
            class: 'row-actions',
            onKeydown: (event: KeyboardEvent) => event.stopPropagation(),
          },
          [
            h(
              NButton,
              {
                quaternary: true,
                circle: true,
                size: 'small',
                'data-testid': `workspace-create-from-${rowKey(entry)}`,
                'aria-label': `Create from this ${entry.kind} ${rowKey(entry)}`,
                title: 'Create from this',
                onClick: (event: MouseEvent) => {
                  event.stopPropagation();
                  createFrom(entry);
                },
              },
              { icon: () => h(NIcon, { component: CopyOutline }) },
            ),
            ...(entry.kind === 'run' &&
            ['queued', 'running'].includes(entry.run.status)
              ? [
                  h(
                    NButton,
                    {
                      quaternary: true,
                      circle: true,
                      size: 'small',
                      'data-testid': `workspace-cancel-${entry.run.run_id}`,
                      'aria-label': 'Cancel run',
                      title: 'Cancel run',
                      disabled:
                        !['queued', 'running'].includes(entry.run.status) ||
                        cancellingRunIds.value.has(entry.run.run_id),
                      onClick: (event: MouseEvent) => {
                        event.stopPropagation();
                        void cancelRun(entry.run);
                      },
                    },
                    { icon: () => h(NIcon, { component: StopCircleOutline }) },
                  ),
                ]
              : []),
            h(
              NButton,
              {
                quaternary: true,
                circle: true,
                size: 'small',
                type: 'error',
                'data-testid':
                  entry.kind === 'run'
                    ? `workspace-delete-${entry.run.run_id}`
                    : `workspace-delete-batch-${entry.batch.batch_id}`,
                'aria-label': `Delete ${entry.kind}`,
                title: `Delete ${entry.kind}`,
                disabled:
                  entry.kind === 'run'
                    ? !['succeeded', 'failed', 'cancelled'].includes(
                        entry.run.status,
                      ) || deletingRunIds.value.has(entry.run.run_id)
                    : !['completed', 'cancelled'].includes(
                        entry.batch.status,
                      ) || deletingBatchIds.value.has(entry.batch.batch_id),
                onClick: (event: MouseEvent) => {
                  event.stopPropagation();
                  if (entry.kind === 'run') void deleteRun(entry.run);
                  else void deleteBatch(entry.batch);
                },
              },
              { icon: () => h(NIcon, { component: TrashOutline }) },
            ),
          ],
        ),
    },
  ];

  return historyColumns;
}
