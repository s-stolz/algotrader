import { isFiniteNumber, isRecord } from '../transportValues';

const numericFields = [
  'equity',
  'requested_budget',
  'entry_price',
  'stop_price',
  'requested_quantity',
  'quantity',
  'planned_risk',
  'fill_price',
  'risk_at_fill',
  'risk_difference',
] as const;
const textFields = ['mode', 'reason'] as const;

export type SavedOrderEvent = {
  index: number;
  timestamp_ms: number;
  order_id: string;
  outcome: string;
} & Partial<Record<(typeof numericFields)[number], number | null>> &
  Partial<Record<(typeof textFields)[number], string | null>>;

export function readOrderEvents(diagnostics: unknown): {
  events: SavedOrderEvent[];
  invalidEventCount: number;
} {
  const raw = isRecord(diagnostics) ? diagnostics.order_events : undefined;
  if (raw === undefined || raw === null)
    return { events: [], invalidEventCount: 0 };
  if (!Array.isArray(raw)) return { events: [], invalidEventCount: 1 };
  const events: SavedOrderEvent[] = [];
  let invalidEventCount = 0;
  raw.forEach((value, index) => {
    const event = readOrderEvent(value, index);
    if (event) events.push(event);
    else invalidEventCount++;
  });
  return { events, invalidEventCount };
}

function readOrderEvent(value: unknown, index: number): SavedOrderEvent | null {
  if (
    !isRecord(value) ||
    !isFiniteNumber(value.timestamp_ms) ||
    !Number.isInteger(value.timestamp_ms) ||
    Math.abs(value.timestamp_ms) > 8.64e15 ||
    typeof value.order_id !== 'string' ||
    typeof value.outcome !== 'string' ||
    !value.outcome.trim()
  )
    return null;
  const event: SavedOrderEvent = {
    index,
    timestamp_ms: value.timestamp_ms,
    order_id: value.order_id,
    outcome: value.outcome,
  };
  for (const key of numericFields) {
    const field = value[key];
    if (field === undefined) continue;
    if (field !== null && !isFiniteNumber(field)) return null;
    event[key] = field;
  }
  for (const key of textFields) {
    const field = value[key];
    if (field === undefined) continue;
    if (field !== null && typeof field !== 'string') return null;
    event[key] = field;
  }
  return event;
}
