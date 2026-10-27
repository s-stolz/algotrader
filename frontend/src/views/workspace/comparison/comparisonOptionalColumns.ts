import { h } from 'vue';
import { NSkeleton } from 'naive-ui';
import type { BacktestRun } from '@/types/backtesterContracts';
import {
  displayWinRate,
  formatSigned,
  formatUtcDate,
  runMarket,
  strategyVersion,
} from '../../backtestWorkspaceRuns';
import {
  cell,
  metricCell,
  countCell,
  directionPnl,
  runStatusCell,
} from './comparisonCells';
import type { BacktestWorkspace } from '../useBacktestWorkspace';
export type ComparisonColumn = {
  title: string;
  key: string;
  width: number;
  align?: 'center';
  group: 'Run settings' | 'Performance' | 'Long / short';
  render: (run: BacktestRun) => ReturnType<typeof h>;
};
export function createOptionalColumns(
  currentRows: BacktestWorkspace['inspection']['currentRows'],
  analysis: BacktestWorkspace['inspection']['analysis'],
): ComparisonColumn[] {
  const parameterKeys = [
    ...new Set(
      currentRows.value.flatMap((run) =>
        Object.keys(run.request.strategy.parameters),
      ),
    ),
  ].sort();
  return [
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
    ...parameterKeys.map((name) => ({
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
          'Saved signed percentage: (ending equity / first recorded equity − 1) ' +
            '× 100. First recorded equity follows the first Candle executions and ' +
            'fees; it can differ from Initial capital.',
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
          'Positive magnitude of the saved largest peak-to-trough ' +
            'recorded equity loss, in percent.',
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
        analysis.value[run.run_id]?.loading &&
        !analysis.value[run.run_id]?.curve
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
              'Final point of exact Equity Replay, in account units. Unavailable ' +
                'replay leaves this missing.',
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
        countCell(
          run,
          'long_trade_count',
          'Saved count of long Closed Trades.',
        ),
    },
    {
      title: 'Long win rate',
      key: 'long-win',
      group: 'Long / short',
      width: 150,
      render: (run) =>
        cell(
          run.status === 'succeeded' ? displayWinRate(run, 'long') : '—',
          'Profitable long Closed Trades divided by long Closed Trades, in ' +
            'percent; No trades if count is zero.',
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
          'Profitable short Closed Trades divided by short Closed Trades, in ' +
            'percent; No trades if count is zero.',
        ),
    },
    {
      title: 'Short PnL',
      key: 'short-pnl',
      group: 'Long / short',
      width: 140,
      render: (run) => directionPnl(run, 'short'),
    },
  ];
}
