import { describe, expect, it } from 'vitest';
import { initialScheduleDraft } from '@/types/backtest/schedule';
import {
  buildBacktestRequest,
  initialDraft,
} from '@/views/creation/creationRequest';

describe('market increment when copying a backtest', () => {
  it('omits saved market metadata and removed tick-size parameters', () => {
    const draft = initialDraft();
    draft.strategy = {
      strategy_id: 'rsi_range_limit',
      strategy_version: 2,
      parameters: { tick_size: 0.01 },
    };
    draft.market_min_move = 0.25;
    draft.execution.candle_quote = 'bid';
    draft.execution.spread = 0;
    const request = buildBacktestRequest(
      draft,
      {
        marketIds: [2],
        timeframes: ['M1'],
        allowedDirections: ['long_and_short'],
        parameters: {},
        dailySchedule: initialScheduleDraft(),
      },
      {
        strategy_id: 'rsi_range_limit',
        strategy_version: 2,
        display_name: 'RSI Range Limit',
        execution_mode: 'orders',
        parameters: [],
      },
      [],
      () => {
        throw new Error('No manual tick-size parameter expected');
      },
      () => [],
    );
    expect(request.markets).toEqual([2]);
    expect(request).not.toHaveProperty('market_min_move');
    expect(request.parameter_axes).not.toHaveProperty('tick_size');
    expect(request.strategy).toEqual({
      strategy_id: 'rsi_range_limit',
      strategy_version: 2,
    });
  });
});
