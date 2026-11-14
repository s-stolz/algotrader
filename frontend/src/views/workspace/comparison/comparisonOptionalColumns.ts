import { h } from 'vue';
import type { BacktestRun } from '@/types/backtesterContracts';
import { scheduleLabel } from '@/types/backtest/schedule';
import {
  displayWinRate,
  formatSigned,
  savedMetric,
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
      title: 'Daily schedule (UTC)',
      key: 'daily_schedule',
      group: 'Run settings',
      width: 220,
      render: (run) =>
        cell(
          scheduleLabel(run.request.execution.daily_schedule),
          'Entry start / last entry / exit (UTC).',
        ),
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
        cell(
          formatSigned(
            run.status === 'succeeded'
              ? savedMetric(run, 'ending_equity')
              : null,
          ).replace(/^\+/, ''),
          'Saved final equity at run completion, in account units.',
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
