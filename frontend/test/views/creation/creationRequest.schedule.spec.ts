import { describe, expect, it } from 'vitest';
import {
  buildBacktestRequest,
  initialDraft,
} from '@/views/creation/creationRequest';
import type {
  StrategyCatalogEntry,
  BacktestSelectionsDraft,
} from '@/types/backtesterContracts';

describe('shared execution schedule in selections creation', () => {
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
  };
  function request() {
    const draft = initialDraft();
    draft.strategy = {
      strategy_id: 'test',
      strategy_version: 1,
      parameters: {},
    };
    draft.execution.max_entries_per_day = 1;
    draft.execution.daily_schedule = {
      entry_start_minute_utc: 60,
      last_entry_minute_utc: 120,
      exit_minute_utc: 180,
    };
    return draft;
  }
  function build(draft: ReturnType<typeof request>) {
    return buildBacktestRequest(
      draft,
      selections,
      strategy,
      [],
      () => {
        throw new Error('No parameter axes');
      },
      () => [],
    );
  }
  it('retains the schedule as a shared control without adding a parameter axis', () => {
    const draft = request();
    const preview = build(draft);
    expect(preview.execution.daily_schedule).toEqual(
      draft.execution.daily_schedule,
    );
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
    draft.execution.daily_schedule!.exit_minute_utc = 119;
    expect(() => build(draft)).toThrow('exit must be at or after last entry');
  });
});
