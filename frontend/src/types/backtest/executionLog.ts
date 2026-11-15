import { isBacktestClosedTrade, type BacktestClosedTrade } from './results';
import {
  isRecord,
  isNonEmptyString,
  isNullableNumber,
} from '../transportValues';

export const EXECUTION_LOG_PAGE_SIZE = 10;

export interface UnexecutedOrder {
  order_id: string;
  outcome: string;
  side: 'buy' | 'sell' | null;
  planned_price: number | null;
  planned_quantity: number | null;
}
export type ExecutionLogItem =
  | { kind: 'trade'; timestamp_ms: number; trade: BacktestClosedTrade }
  | { kind: 'unexecuted_order'; timestamp_ms: number; order: UnexecutedOrder };
export interface ExecutionLogPage {
  run_id: string;
  page: number;
  page_size: number;
  total: number;
  items: ExecutionLogItem[];
}
function integer(value: unknown, minimum: number): value is number {
  return Number.isSafeInteger(value) && (value as number) >= minimum;
}
function isItem(value: unknown): value is ExecutionLogItem {
  if (
    !isRecord(value) ||
    !integer(value.timestamp_ms, 0) ||
    value.timestamp_ms > 8.64e15
  )
    return false;
  if (value.kind === 'trade')
    return (
      isBacktestClosedTrade(value.trade) &&
      value.timestamp_ms === value.trade.exit_timestamp_ms
    );
  if (value.kind !== 'unexecuted_order' || !isRecord(value.order)) return false;
  const order = value.order;
  return (
    isNonEmptyString(order.order_id) &&
    isNonEmptyString(order.outcome) &&
    (order.side === null || order.side === 'buy' || order.side === 'sell') &&
    isNullableNumber(order.planned_price) &&
    isNullableNumber(order.planned_quantity)
  );
}
export function executionLogItemKey(item: ExecutionLogItem): string {
  return item.kind === 'trade'
    ? `trade-${item.trade.sequence}`
    : `order-${item.order.order_id}`;
}
export function isExecutionLogPage(value: unknown): value is ExecutionLogPage {
  if (
    !isRecord(value) ||
    !isNonEmptyString(value.run_id) ||
    !integer(value.page, 1) ||
    !integer(value.page_size, 1) ||
    value.page_size > 100 ||
    !integer(value.total, 0) ||
    !Array.isArray(value.items) ||
    !value.items.every(isItem)
  )
    return false;
  const expected = Math.max(
    0,
    Math.min(value.page_size, value.total - (value.page - 1) * value.page_size),
  );
  return (
    value.items.length === expected &&
    new Set(value.items.map(executionLogItemKey)).size === value.items.length &&
    value.items.every(
      (item, index, items) =>
        index === 0 || item.timestamp_ms <= items[index - 1].timestamp_ms,
    )
  );
}
