import type {
  BacktestClosedTrade,
  BacktestRun,
} from '@/types/backtesterContracts';
export function resultTrade(
  pnl: number,
  exit = Date.UTC(2025, 0, 15),
): BacktestClosedTrade {
  return {
    sequence: 0,
    trade_id: 'trade',
    symbol: 'EURUSD',
    trade_direction: 'long',
    quantity: 1,
    entry_timestamp_ms: exit - 7200000,
    exit_timestamp_ms: exit,
    entry_price: 100,
    exit_price: 100 + pnl,
    realized_pnl: pnl,
    fees: 2,
    exit_reason: 'signal',
    stop_loss_price: null,
    take_profit_price: null,
  };
}
export function resultRun(
  id = 'run',
  start = Date.UTC(2025, 0),
  end = Date.UTC(2026, 0),
): BacktestRun {
  return {
    run_id: id,
    status: 'succeeded',
    metrics: { profit_factor: null },
    run_ordinal: 0,
    request: { start_ms: start, end_ms: end, initial_capital: 10000 },
  } as BacktestRun;
}
