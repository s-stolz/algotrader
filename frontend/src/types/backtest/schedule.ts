import { isRecord } from '../transportValues';

export interface DailyTradingSchedule {
  entry_start_minute_utc: number;
  last_entry_minute_utc: number;
  exit_minute_utc: number;
}

export function isDailyTradingSchedule(
  value: unknown,
): value is DailyTradingSchedule {
  if (!isRecord(value)) return false;
  const {
    entry_start_minute_utc: start,
    last_entry_minute_utc: last,
    exit_minute_utc: exit,
  } = value;
  return (
    [start, last, exit].every(
      (minute) => typeof minute === 'number' && Number.isInteger(minute),
    ) &&
    typeof start === 'number' &&
    typeof last === 'number' &&
    typeof exit === 'number' &&
    start >= 0 &&
    start < last &&
    last <= exit &&
    exit < 1440
  );
}

export function dailyScheduleIssue(value: unknown): string | null {
  return value == null || isDailyTradingSchedule(value)
    ? null
    : 'Entry start must precede last entry; exit must be at or after last entry.';
}

export function formatScheduleMinute(minute: number): string {
  const hours = String(Math.floor(minute / 60)).padStart(2, '0');
  const minutes = String(minute % 60).padStart(2, '0');
  return `${hours}:${minutes}`;
}
