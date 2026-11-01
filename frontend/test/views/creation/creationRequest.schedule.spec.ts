import { describe, expect, it } from 'vitest';
import {
  buildSweepRequest,
  initialDraft,
} from '@/views/creation/creationRequest';
import type {
  StrategyCatalogEntry,
  SweepDraftState,
} from '@/types/backtesterContracts';

describe('shared execution schedule in sweep creation', () => {
  const strategy: StrategyCatalogEntry = {
    strategy_id: 'test',
    strategy_version: 1,
    display_name: 'Test',
    parameters: [],
  };
  const sweep: SweepDraftState = {
    isSweep: true,
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
    draft.execution.daily_schedule = {
      entry_start_minute_utc: 60,
      last_entry_minute_utc: 120,
      exit_minute_utc: 180,
    };
    return draft;
  }
  function build(draft: ReturnType<typeof request>) {
    return buildSweepRequest(
      draft,
      sweep,
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
    expect(preview.parameter_axes).toEqual({});
  });
  it('rejects invalid scheduling before requesting a preview', () => {
    const draft = request();
    draft.execution.daily_schedule!.exit_minute_utc = 119;
    expect(() => build(draft)).toThrow('exit must be at or after last entry');
  });
});
