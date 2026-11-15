import { isRecord } from '../transportValues';

export interface DailyTradingSchedule {
  entry_start_minute_utc: number;
  last_entry_minute_utc: number;
  exit_minute_utc: number;
}

export type DailyScheduleInput = {
  [Key in keyof DailyTradingSchedule]: number | null;
};

export interface DailyScheduleDraft {
  enabled: boolean;
  candidates: DailyScheduleInput[];
}

export function initialScheduleDraft(
  legacy?: DailyTradingSchedule | null,
  alternatives?: DailyTradingSchedule[],
): DailyScheduleDraft {
  return {
    enabled: !!legacy || !!alternatives?.length,
    candidates: (
      alternatives ??
      (legacy
        ? [legacy]
        : [
            {
              entry_start_minute_utc: 0,
              last_entry_minute_utc: 720,
              exit_minute_utc: 1020,
            },
          ])
    ).map((schedule) => ({ ...schedule })),
  };
}

export function scheduleDraftIssues(
  draft: DailyScheduleDraft,
): Record<string, string> {
  if (!draft.enabled) return {};
  if (!draft.candidates.length)
    return { schedule: 'Add at least one schedule.' };
  const issues: Record<string, string> = {};
  draft.candidates.forEach((candidate, index) => {
    const issue = Object.values(candidate).some((value) => value === null)
      ? 'Enter all three times.'
      : dailyScheduleIssue(candidate);
    const duplicate = draft.candidates.some(
      (other, otherIndex) =>
        otherIndex !== index &&
        other.entry_start_minute_utc === candidate.entry_start_minute_utc &&
        other.last_entry_minute_utc === candidate.last_entry_minute_utc &&
        other.exit_minute_utc === candidate.exit_minute_utc,
    );
    if (issue || duplicate)
      issues[`schedule-${index}`] =
        issue ??
        'This schedule already exists. Change or remove the duplicate.';
  });
  return issues;
}

export function isDailyScheduleList(
  value: unknown,
): value is DailyTradingSchedule[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every(isDailyTradingSchedule)
  );
}

export function scheduleLabel(value?: DailyTradingSchedule | null): string {
  return value
    ? [
        value.entry_start_minute_utc,
        value.last_entry_minute_utc,
        value.exit_minute_utc,
      ]
        .map(formatScheduleMinute)
        .join(' / ')
    : 'Off';
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
