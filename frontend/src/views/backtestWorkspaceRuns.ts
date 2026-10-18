import type { BacktestRun, BacktestBatch } from '@/types/backtesterContracts';

export type HistorySortKey = 'name' | 'type' | 'strategy' | 'market' | 'timeframe' |
  'start' | 'end' | 'status' | 'submitted' | 'duration';

export function runName(run: BacktestRun): string {
  return run.batch_id != null ? `Run #${(run.member_ordinal ?? 0) + 1}` :
    run.name ?? 'Unnamed standalone run';
}

export function batchName(batch: BacktestBatch): string {
  return batch.name ?? 'Unnamed parameter sweep';
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
  return timestampMs == null ? '—' : new Date(timestampMs).toISOString().slice(0, 10);
}

export function formatSigned(value: number | null | undefined, suffix = ''): string {
  if (value == null) return '—';
  const rounded = Number(value.toFixed(2));
  const display = rounded === 0 ? value : rounded;
  return `${value > 0 ? '+' : ''}${display}${suffix}`;
}

export function formatMagnitude(value: number | null | undefined, suffix = ''): string {
  if (value == null) return '—';
  const magnitude = Math.abs(value);
  const rounded = Number(magnitude.toFixed(2));
  return `${rounded === 0 ? magnitude : rounded}${suffix}`;
}

export function savedMetric(run: BacktestRun, key: string): number | null {
  const value = run.metrics?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function displayWinRate(run: BacktestRun, direction: 'long' | 'short'): string {
  const count = savedMetric(run, `${direction}_trade_count`);
  if (count === 0) return 'No trades';
  const rate = savedMetric(run, `${direction}_win_rate_pct`);
  return rate === null ? '—' : `${Number(rate.toFixed(2))}%`;
}

export function timeframeDuration(value: string): number | null {
  const match = /^(M|H|D|W)(\d+)$/.exec(value.toUpperCase());
  if (!match) return null;
  const unit = { M: 1, H: 60, D: 1440, W: 10080 }[match[1] as 'M' | 'H' | 'D' | 'W'];
  return unit * Number(match[2]);
}

function compareText(left: string, right: string): number {
  return left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' });
}

function compareValue(left: string | number | null, right: string | number | null): number {
  if (left === null) return right === null ? 0 : -1;
  if (right === null) return 1;
  return typeof left === 'number' && typeof right === 'number'
    ? left - right
    : compareText(String(left), String(right));
}

function sortValue(run: BacktestRun, key: HistorySortKey): string | number | null {
  switch (key) {
    case 'name': return runName(run);
    case 'type': return 'Standalone';
    case 'strategy': return `${run.request.strategy.strategy_id} ${strategyVersion(run)}`;
    case 'market': return runMarket(run);
    case 'timeframe': return timeframeDuration(run.request.timeframe) ?? run.request.timeframe;
    case 'start': return run.request.start_ms;
    case 'end': return run.request.end_ms;
    case 'status': return run.status;
    case 'submitted': return run.submitted_at_ms;
    case 'duration': return run.started_at_ms == null || run.completed_at_ms == null
      ? null : run.completed_at_ms - run.started_at_ms;
  }
}

export function compareHistoryRuns(left: BacktestRun, right: BacktestRun, key: HistorySortKey): number {
  return compareValue(sortValue(left, key), sortValue(right, key)) ||
    compareText(runName(left), runName(right)) || compareText(left.run_id, right.run_id);
}

export function equityUnavailableReason(reason: string | null | undefined): string {
  switch (reason) {
    case 'replay_metadata_missing': return 'Replay metadata is missing for this older successful run';
    case 'fingerprint_mismatch': return 'Candle data changed since this run completed';
    case 'unsupported_replay_shape': return 'Saved execution data cannot be replayed exactly';
    default: return 'Unknown replay reason';
  }
}
