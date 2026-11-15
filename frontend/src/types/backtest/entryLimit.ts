export function dailyEntryLimitIssue(value: unknown): string | null {
  return value == null ||
    (typeof value === 'number' && Number.isInteger(value) && value > 0)
    ? null
    : 'Daily entry limit must be a positive whole number or empty for unlimited.';
}
