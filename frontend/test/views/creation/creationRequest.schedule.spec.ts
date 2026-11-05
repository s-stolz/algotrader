import { describe, expect, it } from 'vitest';
import { initialScheduleDraft } from '@/types/backtest/schedule';
import {
  buildBacktestRequest,
  initialDraft,
} from '@/views/creation/creationRequest';
import type {
  StrategyCatalogEntry,
  BacktestSelectionsDraft,
} from '@/types/backtesterContracts';

describe('schedule alternatives in selections creation', () => {
  const schedule = {
    entry_start_minute_utc: 60,
    last_entry_minute_utc: 120,
    exit_minute_utc: 180,
  };
  const strategy: StrategyCatalogEntry = {
    strategy_id: 'test',
    strategy_version: 1,
    display_name: 'Test',
    parameters: [],
  };
  const selections: BacktestSelectionsDraft = {
    marketIds: [1, 2],
    timeframes: ['M5'],
    allowedDirections: ['long_and_short'],
    parameters: {},
    dailySchedule: initialScheduleDraft(schedule),
  };
  function request() {
    const draft = initialDraft();
    draft.strategy = {
      strategy_id: 'test',
      strategy_version: 1,
      parameters: {},
    };
    draft.execution.max_entries_per_day = 1;
    return draft;
  }
  function build(draft: ReturnType<typeof request>, selection = selections) {
    return buildBacktestRequest(
      draft,
      selection,
      strategy,
      [],
      () => {
        throw new Error('No parameter axes');
      },
      () => [],
    );
  }
  it('serializes a single alternative separately from strategy parameters', () => {
    const draft = request();
    const preview = build(draft);
    expect(preview.daily_schedules).toEqual([schedule]);
    expect(preview.execution).not.toHaveProperty('daily_schedule');
    expect(preview.execution.max_entries_per_day).toBe(1);
    expect(preview.parameter_axes).toEqual({});
  });
  it('rejects an invalid daily limit before requesting a preview', () => {
    const draft = request();
    draft.execution.max_entries_per_day = 0;
    expect(() => build(draft)).toThrow('positive whole number');
  });
  it('rejects invalid scheduling before requesting a preview', () => {
    const draft = request();
    const dailySchedule = initialScheduleDraft({
      ...schedule,
      exit_minute_utc: 119,
    });
    expect(() => build(draft, { ...selections, dailySchedule })).toThrow(
      'exit must be at or after last entry',
    );
  });
  it('serializes paired alternatives and retains disabled draft values', () => {
    const draft = request();
    const dailySchedule = initialScheduleDraft(schedule);
    dailySchedule.candidates.push({
      entry_start_minute_utc: 360,
      last_entry_minute_utc: 600,
      exit_minute_utc: 960,
    });
    const selection = { ...selections, dailySchedule };
    const preview = build(draft, selection);
    expect(preview.daily_schedules).toEqual(dailySchedule.candidates);
    expect(preview.execution).not.toHaveProperty('daily_schedule');
    dailySchedule.enabled = false;
    expect(build(draft, selection)).not.toHaveProperty('daily_schedules');
    expect(build(draft, selection).execution).not.toHaveProperty(
      'daily_schedule',
    );
    expect(dailySchedule.candidates).toHaveLength(2);
    dailySchedule.enabled = true;
    dailySchedule.candidates[1].exit_minute_utc = null;
    expect(() => build(draft, selection)).toThrow('Enter all three times');
    dailySchedule.candidates[1] = { ...dailySchedule.candidates[0] };
    expect(() => build(draft, selection)).toThrow('already exists');
    dailySchedule.candidates = [];
    expect(() => build(draft, selection)).toThrow('Add at least one schedule');
  });
});
