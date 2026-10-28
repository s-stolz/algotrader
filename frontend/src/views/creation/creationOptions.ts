import type { SelectOption } from 'naive-ui';
import { TIMEFRAME_CODES } from '@/types/contracts';

export const timeframeOptions: SelectOption[] = TIMEFRAME_CODES.map((code) => ({
  label: code,
  value: code,
}));
export const directionOptions: SelectOption[] = [
  { label: 'Long and short', value: 'long_and_short' },
  { label: 'Long only', value: 'long_only' },
  { label: 'Short only', value: 'short_only' },
];
export const engineOptions: SelectOption[] = [
  { label: 'Vectorized', value: 'vectorized' },
  { label: 'Event driven', value: 'event_driven' },
];
export const gapOptions: SelectOption[] = [
  { label: 'Skip', value: 'skip' },
  { label: 'Expire', value: 'expire' },
  { label: 'Error', value: 'error' },
];
export const exitOptions: SelectOption[] = [
  { label: 'Conservative', value: 'conservative' },
  { label: 'Stop first', value: 'stop_first' },
  { label: 'Take profit first', value: 'take_profit_first' },
  { label: 'Error', value: 'error' },
];

export const previewFilterOptions: SelectOption[] = [
  { label: 'All', value: 'all' },
  { label: 'Ready', value: 'ready' },
  { label: 'Excluded', value: 'excluded' },
];
export const runTypeOptions: SelectOption[] = [
  { label: 'Standalone Backtest', value: 'standalone' },
  { label: 'Parameter Sweep', value: 'sweep' },
];
