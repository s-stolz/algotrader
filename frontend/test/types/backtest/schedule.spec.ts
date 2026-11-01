import { describe, expect, it } from 'vitest';
import {
  dailyScheduleIssue,
  isDailyTradingSchedule,
} from '@/types/backtest/schedule';
import { isBacktestRequestPayload } from '@/types/backtesterContracts';
import { initialDraft } from '@/views/creation/creationRequest';

describe('execution schedule transport', () => {
  const schedule = {
    entry_start_minute_utc: 60,
    last_entry_minute_utc: 120,
    exit_minute_utc: 180,
  };
  it('accepts legacy omitted schedules and validates enabled ones', () => {
    const draft = initialDraft();
    draft.symbols = ['TEST'];
    draft.strategy.strategy_id = 'test';
    expect(isBacktestRequestPayload(draft)).toBe(true);
    draft.execution.daily_schedule = schedule;
    expect(isBacktestRequestPayload(draft)).toBe(true);
    draft.execution.daily_schedule = { ...schedule, exit_minute_utc: 119 };
    expect(isBacktestRequestPayload(draft)).toBe(false);
  });
  it('rejects noninteger times and invalid ordering', () => {
    expect(dailyScheduleIssue(undefined)).toBeNull();
    expect(dailyScheduleIssue(null)).toBeNull();
    for (const value of [
      {},
      { ...schedule, entry_start_minute_utc: 120 },
      { ...schedule, last_entry_minute_utc: 120.5 },
      { ...schedule, exit_minute_utc: 1440 },
    ]) {
      expect(isDailyTradingSchedule(value)).toBe(false);
      expect(dailyScheduleIssue(value)).not.toBeNull();
    }
  });
});
