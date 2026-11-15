import type { BacktestRun, Backtest } from '@/types/backtesterContracts';

export type HistorySortKey =
  | 'name'
  | 'strategy'
  | 'market'
  | 'timeframe'
  | 'start'
  | 'end'
  | 'status'
  | 'submitted'
  | 'duration';

export function runName(run: BacktestRun): string {
  return `Run #${run.run_ordinal + 1}`;
}

export function backtestName(backtest: Backtest): string {
  return backtest.name ?? 'Unnamed backtest';
}

export function strategyVersion(run: BacktestRun): string {
  const version = run.request.strategy.strategy_version;
  return version === undefined ? 'Version unavailable' : `v${version}`;
}

export function runMarket(run: BacktestRun): string {
  if (run.request.symbols.length === 0) return 'No Market';
  const symbols = run.request.symbols.join(', ');
  return run.request.exchange ? `${run.request.exchange}:${symbols}` : symbols;
}

export function formatUtcDate(timestampMs: number | null | undefined): string {
  return timestampMs == null
    ? '—'
    : new Date(timestampMs).toISOString().slice(0, 10);
}

export function formatSigned(
  value: number | null | undefined,
  suffix = '',
): string {
  if (value == null) return '—';
  if (suffix === '%') {
    const magnitude = formatMagnitude(value, suffix);
    return `${value > 0 ? '+' : value < 0 ? '-' : ''}${magnitude}`;
  }
  const rounded = Number(value.toFixed(2));
  const display = rounded === 0 ? value : rounded;
  return `${value > 0 ? '+' : ''}${display}${suffix}`;
}

export function formatMagnitude(
  value: number | null | undefined,
  suffix = '',
): string {
  if (value == null) return '—';
  const magnitude = Math.abs(value);
  if (suffix === '%') {
    const rounded =
      magnitude > 0 && magnitude < 0.001
        ? Number(magnitude.toPrecision(2))
        : Number(magnitude.toFixed(3));
    return `${rounded}${suffix}`;
  }
  const rounded = Number(magnitude.toFixed(2));
  return `${rounded === 0 ? magnitude : rounded}${suffix}`;
}

export function savedMetric(run: BacktestRun, key: string): number | null {
  const value = run.metrics?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function displayWinRate(
  run: BacktestRun,
  direction: 'long' | 'short',
): string {
  const count = savedMetric(run, `${direction}_trade_count`);
  if (count === 0) return 'No trades';
  const rate = savedMetric(run, `${direction}_win_rate_pct`);
  return rate === null ? '—' : `${Number(rate.toFixed(2))}%`;
}

export function timeframeDuration(value: string): number | null {
  const match = /^(M|H|D|W)(\d+)$/.exec(value.toUpperCase());
  if (!match) return null;
  const unit = { M: 1, H: 60, D: 1440, W: 10080 }[
    match[1] as 'M' | 'H' | 'D' | 'W'
  ];
  return unit * Number(match[2]);
}

export function equityUnavailableReason(
  reason: string | null | undefined,
): string {
  switch (reason) {
    case 'replay_metadata_missing':
      return 'Replay metadata is missing for this older successful run';
    case 'fingerprint_mismatch':
      return 'Candle data changed since this run completed';
    case 'unsupported_replay_shape':
      return 'Saved execution data cannot be replayed exactly';
    default:
      return 'Unknown replay reason';
  }
}
