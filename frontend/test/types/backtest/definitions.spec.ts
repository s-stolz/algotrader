import { describe, expect, it } from 'vitest';
import { isBacktestPreview } from '@/types/backtest/definitions';
import { isBacktest } from '@/types/backtest/backtests';
import {
  backtest,
  member,
} from '../../components/Backtest/backtestOverviewFixtures';

const schedule = {
  entry_start_minute_utc: 0,
  last_entry_minute_utc: 720,
  exit_minute_utc: 1020,
};
function preview() {
  return {
    max_backtest_candidate_count: 1000,
    raw_count: 1,
    ready_count: 1,
    excluded_count: 0,
    normalized_selections: {
      ...backtest.accepted_definition.normalized_selections,
      daily_schedules: [schedule],
    },
    candidates: [
      {
        candidate_ordinal: 0,
        run_ordinal: 0,
        status: 'ready',
        market: { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' },
        timeframe: 'M1',
        parameters: {},
        allowed_directions: 'long_only',
        daily_schedule: schedule,
        request: member(0).request,
      },
    ],
  };
}
describe('daily schedule alternatives in transport', () => {
  it('validates preview selections and candidate schedules including excluded rows', () => {
    expect(isBacktestPreview(preview())).toBe(true);
    for (const invalid of [[], [null], [{ ...schedule, exit_minute_utc: 1 }]]) {
      const value = preview();
      const selections = {
        ...value.normalized_selections,
        daily_schedules: invalid,
      };
      expect(
        isBacktestPreview({ ...value, normalized_selections: selections }),
      ).toBe(false);
    }
    const value = preview();
    value.candidates.push({
      ...value.candidates[0],
      candidate_ordinal: 1,
      status: 'excluded',
    });
    const excluded = {
      ...value.candidates[1],
      request: undefined,
      run_ordinal: undefined,
      issues: [
        { code: 'constraint', fields: ['x'], message: 'Invalid combination' },
      ],
    };
    const mixed = {
      ...value,
      raw_count: 2,
      excluded_count: 1,
      candidates: [value.candidates[0], excluded],
    };
    expect(isBacktestPreview(mixed)).toBe(true);
    expect(
      isBacktestPreview({
        ...mixed,
        candidates: [
          value.candidates[0],
          {
            ...excluded,
            daily_schedule: { ...schedule, entry_start_minute_utc: -1 },
          },
        ],
      }),
    ).toBe(false);
  });
  it('accepts legacy saved definitions and rejects malformed saved alternatives', () => {
    expect(isBacktest(backtest)).toBe(true);
    const saved = structuredClone(backtest);
    saved.accepted_definition.normalized_selections.daily_schedules = [
      schedule,
    ];
    expect(isBacktest(saved)).toBe(true);
    saved.accepted_definition.normalized_selections.daily_schedules = [];
    expect(isBacktest(saved)).toBe(false);
  });
});
