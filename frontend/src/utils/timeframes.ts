import {
  TIMEFRAME_CODES,
  type TimeframeCode,
  type TimeframeOption,
  isTimeframeCode,
} from '@/types/contracts';

export const TIMEFRAME_OPTIONS: TimeframeOption[] = [
  { label: 'M1', value: 'M1' },
  { label: 'M5', value: 'M5' },
  { label: 'M15', value: 'M15' },
  { label: 'M30', value: 'M30' },
  { label: 'H1', value: 'H1' },
  { label: 'H4', value: 'H4' },
  { label: 'D1', value: 'D1' },
];

export const TIMEFRAME_TO_MINUTES: Record<TimeframeCode, number> = {
  M1: 1,
  M2: 2,
  M3: 3,
  M4: 4,
  M5: 5,
  M10: 10,
  M15: 15,
  M30: 30,
  H1: 60,
  H4: 240,
  H12: 720,
  D1: 1440,
  W1: 10080,
  MN1: 43200,
};

export const MINUTES_TO_TIMEFRAME: Readonly<Record<number, TimeframeCode>> = Object.fromEntries(
  TIMEFRAME_CODES.map((code) => [TIMEFRAME_TO_MINUTES[code], code]),
) as Record<number, TimeframeCode>;

export function normalizeTimeframeCode(timeframe: unknown): TimeframeCode {
  if (typeof timeframe === 'number') {
    return MINUTES_TO_TIMEFRAME[timeframe] ?? 'M1';
  }

  if (typeof timeframe === 'string') {
    const upper = timeframe.toUpperCase();
    if (isTimeframeCode(upper)) {
      return upper;
    }
  }

  return 'M1';
}

export function timeframeToMinutes(timeframe: unknown): number {
  const code = normalizeTimeframeCode(timeframe);
  return TIMEFRAME_TO_MINUTES[code];
}

const timeframeUnits = [
  { code: 'M', label: 'Minutes' },
  { code: 'H', label: 'Hours' },
  { code: 'D', label: 'Days' },
  { code: 'W', label: 'Weeks' },
  { code: 'MN', label: 'Months' },
] as const;

export function groupTimeframeOptions(options: readonly TimeframeOption[]): { label: string; options: TimeframeOption[] }[] {
  return timeframeUnits.map(unit => ({
    label: unit.label,
    // Match the whole unit: MN is months, never minutes. Do not invent options
    // for units unsupported by the caller's market or service.
    options: options
      .filter(option => option.value.replace(/\d+$/, '') === unit.code)
      .sort((left, right) => TIMEFRAME_TO_MINUTES[left.value] - TIMEFRAME_TO_MINUTES[right.value]),
  })).filter(group => group.options.length > 0);
}
