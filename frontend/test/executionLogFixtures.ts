import type {
  ExecutionLogItem,
  ExecutionLogPage,
} from '@/types/backtest/executionLog';
export function tradeItem(sequence: number): ExecutionLogItem {
  const time = 1_700_000_000_000 + sequence * 60000;
  return {
    kind: 'trade',
    timestamp_ms: time,
    trade: {
      sequence,
      trade_id: `trade-${sequence}`,
      symbol: 'EURUSD',
      trade_direction: 'long',
      entry_timestamp_ms: time - 60000,
      exit_timestamp_ms: time,
      entry_price: 1.1,
      exit_price: 1.2,
      quantity: 100,
      realized_pnl: 9.5,
      fees: 0.5,
      exit_reason: 'signal',
      stop_loss_price: null,
      take_profit_price: null,
    },
  };
}
export function logPage(
  runId = 'run-123',
  page = 1,
  total = 23,
): ExecutionLogPage {
  return {
    run_id: runId,
    page,
    page_size: 10,
    total,
    items: Array.from(
      { length: Math.max(0, Math.min(10, total - (page - 1) * 10)) },
      (_, i) => tradeItem(total - (page - 1) * 10 - i),
    ),
  };
}
export function orderItem(): ExecutionLogItem {
  return {
    kind: 'unexecuted_order',
    timestamp_ms: 1_800_000_000_000,
    order: {
      order_id: 'private-order-id',
      outcome: 'insufficient_margin',
      side: 'buy',
      planned_price: 1.1,
      planned_quantity: 100,
    },
  };
}
export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
