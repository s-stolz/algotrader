import { h } from 'vue';
import { designTokens } from '@/design/tokens';
import { NButton, NIcon, NTag, type DataTableColumns } from 'naive-ui';
import CopyOutline from '@vicons/ionicons5/es/CopyOutline';
import TrashOutline from '@vicons/ionicons5/es/TrashOutline';
import {
  backtestName,
  formatUtcDate,
  type HistorySortKey,
} from '../backtestWorkspaceRuns';
import {
  rowKey,
  backtestMarkets,
  backtestTimeframes,
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
  const { deletingBacktestIds, deleteBacktest } = actions;
  const historyColumns: DataTableColumns<HistoryEntry> = [
    historyColumn('Name', 'name', (entry) =>
      h('span', { class: 'run-identity' }, [
        cell(backtestName(entry.backtest), entry.backtest.backtest_id),
        h('small', entry.backtest.backtest_id.slice(0, 8)),
      ]),
    ),
    historyColumn('Strategy / version', 'strategy', (entry) =>
      cell(
        `${entry.backtest.strategy_id} · v${entry.backtest.strategy_version}`,
      ),
    ),
    historyColumn('Market', 'market', (entry) =>
      cell(backtestMarkets(entry.backtest).join(', ')),
    ),
    historyColumn('Timeframe', 'timeframe', (entry) =>
      cell(backtestTimeframes(entry.backtest).join(', ')),
    ),
    historyColumn('Start date', 'start', (entry) =>
      cell(
        formatUtcDate(
          Number(entry.backtest.accepted_definition.shared_request.start_ms),
        ),
      ),
    ),
    historyColumn('End date', 'end', (entry) =>
      cell(
        formatUtcDate(
          Number(entry.backtest.accepted_definition.shared_request.end_ms),
        ),
      ),
    ),
    historyColumn('Status', 'status', (entry) => {
      const status = entry.backtest.status;
      return h(
        NTag,
        {
          size: 'small',
          type:
            status === 'completed' && !entry.backtest.has_failed_members
              ? 'success'
              : entry.backtest.has_failed_members
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
        `${entry.backtest.settled_count} / ${entry.backtest.total_count}` +
          (entry.backtest.has_failed_members
            ? ` · ${entry.backtest.outcome_counts.failed} failed`
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
                'aria-label': `Create from this Backtest ${rowKey(entry)}`,
                title: 'Create from this',
                onClick: (event: MouseEvent) => {
                  event.stopPropagation();
                  createFrom(entry);
                },
              },
              { icon: () => h(NIcon, { component: CopyOutline }) },
            ),
            h(
              NButton,
              {
                quaternary: true,
                circle: true,
                size: 'small',
                type: 'error',
                'data-testid': `workspace-delete-backtest-${entry.backtest.backtest_id}`,
                'aria-label': `Delete Backtest`,
                title: `Delete Backtest`,
                disabled:
                  !['completed', 'cancelled'].includes(entry.backtest.status) ||
                  deletingBacktestIds.value.has(entry.backtest.backtest_id),
                onClick: (event: MouseEvent) => {
                  event.stopPropagation();
                  void deleteBacktest(entry.backtest);
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
