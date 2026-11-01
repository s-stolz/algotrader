import { describe, expect, it } from 'vitest';
import { dailyEntryLimitIssue } from '@/types/backtest/entryLimit';
import { isBacktestRequestPayload } from '@/types/backtesterContracts';
import { initialDraft } from '@/views/creation/creationRequest';

describe('daily entry limit transport', () => {
  it('accepts unlimited legacy settings and positive integer limits', () => {
    const draft = initialDraft();
    draft.symbols = ['TEST'];
    draft.strategy.strategy_id = 'test';
    expect(isBacktestRequestPayload(draft)).toBe(true);
    for (const value of [null, undefined, 1, 2]) {
      draft.execution.max_entries_per_day = value;
      expect(dailyEntryLimitIssue(value)).toBeNull();
      expect(isBacktestRequestPayload(draft)).toBe(true);
    }
    for (const value of [0, -1, 1.5, NaN, Infinity, '2', true]) {
      expect(dailyEntryLimitIssue(value)).not.toBeNull();
      expect(
        isBacktestRequestPayload({
          ...draft,
          execution: { ...draft.execution, max_entries_per_day: value },
        }),
      ).toBe(false);
    }
  });
});
