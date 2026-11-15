import type {
  BacktestClosedTrade,
  BacktestRun,
} from '@/types/backtesterContracts';
export const resultMetrics = [
  { key: 'net-profit', title: 'Net realized profit', unit: 'amount' },
  { key: 'win-rate', title: 'Win rate', unit: 'percent' },
  { key: 'profit-factor', title: 'Profit factor', unit: 'ratio' },
  { key: 'expectancy', title: 'Expectancy / trade', unit: 'amount' },
  { key: 'holding-time', title: 'Avg. holding time', unit: 'hours' },
] as const;
export type ResultMetricKey = (typeof resultMetrics)[number]['key'];
export interface RunResults {
  metrics: Record<ResultMetricKey, number | null>;
  months: Record<string, number>;
}
export function summarizeTrades(
  trades: BacktestClosedTrade[],
  profitFactor: number | null,
): RunResults {
  let wins = 0,
    profit = 0,
    loss = 0,
    hours = 0;
  const months: Record<string, number> = {};
  for (const trade of trades) {
    if (trade.realized_pnl > 0) {
      wins++;
      profit += trade.realized_pnl;
    } else loss -= trade.realized_pnl;
    hours += (trade.exit_timestamp_ms - trade.entry_timestamp_ms) / 3600000;
    const date = new Date(trade.exit_timestamp_ms);
    const key = `${date.getUTCFullYear()}-${date.getUTCMonth()}`;
    months[key] = (months[key] ?? 0) + trade.realized_pnl;
  }
  return {
    months,
    metrics: {
      'net-profit': profit - loss,
      'win-rate': trades.length ? (wins / trades.length) * 100 : null,
      'profit-factor': profitFactor,
      expectancy: trades.length ? (profit - loss) / trades.length : null,
      'holding-time': trades.length ? hours / trades.length : null,
    },
  };
}
export function periodProfit(
  run: BacktestRun,
  result: RunResults | undefined,
  year: number,
  month?: number,
): number | null {
  const start = Date.UTC(year, month ?? 0),
    end = Date.UTC(year, month === undefined ? 12 : month + 1);
  if (!result || run.request.start_ms >= end || run.request.end_ms <= start)
    return null;
  if (month !== undefined) return result.months[`${year}-${month}`] ?? 0;
  return Array.from({ length: 12 }, (_, i) =>
    periodProfit(run, result, year, i),
  ).reduce<number>((sum, value) => sum + (value ?? 0), 0);
}
export function formatResult(value: number | null, unit: string): string {
  if (value === null) return '—';
  if (value === Infinity) return '∞';
  const amount = value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (unit === 'percent') return `${amount}%`;
  if (unit === 'hours') return `${amount} h`;
  return unit === 'amount' && value > 0 ? `+${amount}` : amount;
}
export function compareResultValues(
  a: number | null,
  b: number | null,
  order: 'ascend' | 'descend',
) {
  if (a === b) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return (a < b ? -1 : 1) * (order === 'ascend' ? 1 : -1);
}
