import { describe, expect, it } from 'vitest';
import { initialScheduleDraft } from '@/types/backtest/schedule';
import {
  buildBacktestRequest,
  initialDraft,
} from '@/views/creation/creationRequest';

const strategy = {
  execution_mode: 'orders' as const,
  strategy_id: 'limit_reversion',
  strategy_version: 1,
  display_name: 'Limit reversion',
  parameters: [],
};
function draft() {
  const value = initialDraft();
  value.strategy = { ...strategy, parameters: {} };
  Object.assign(value.execution, {
    execution_mode: 'orders',
    candle_quote: 'bid',
    spread: 0.0001,
    max_position_quantity: 2,
    intrabar_execution_policy: 'optimistic',
    intrabar_exit_policy: 'error',
  });
  return value;
}
function build(
  value: ReturnType<typeof draft>,
  mode: 'orders' | 'targets' = 'orders',
) {
  return buildBacktestRequest(
    value,
    {
      marketIds: [1],
      timeframes: ['M10'],
      allowedDirections: ['long_and_short'],
      parameters: {},
      dailySchedule: initialScheduleDraft(),
    },
    { ...strategy, execution_mode: mode },
    [],
    () => {
      throw new Error('Unexpected parameter');
    },
    () => [],
  );
}
describe('order execution creation', () => {
  it('submits explicit order settings and keeps the legacy policy consistent', () => {
    const value = draft();
    value.execution.execution_mode = 'targets';
    expect(build(value).execution).toMatchObject({
      execution_mode: 'orders',
      candle_quote: 'bid',
      spread: 0.0001,
      max_position_quantity: 2,
      intrabar_execution_policy: 'optimistic',
      intrabar_exit_policy: 'take_profit_first',
    });
  });
  it('omits order settings after switching modes without erasing draft values', () => {
    const value = draft();
    value.execution.execution_mode = 'targets';
    const execution = build(value, 'targets').execution;
    for (const key of [
      'spread',
      'candle_quote',
      'max_position_quantity',
      'intrabar_execution_policy',
    ])
      expect(execution).not.toHaveProperty(key);
    expect(value.execution.spread).toBe(0.0001);
  });
  it('requires a quote and valid spread and optional exposure cap', () => {
    const value = draft();
    value.execution.candle_quote = null;
    expect(() => build(value)).toThrow('quote convention');
    value.execution.candle_quote = 'ask';
    value.execution.spread = -1;
    expect(() => build(value)).toThrow('positive spread');
    value.execution.spread = 0;
    value.execution.max_position_quantity = 0;
    expect(() => build(value)).toThrow('positive quantity');
    value.execution.max_position_quantity = null;
    expect(build(value).execution.max_position_quantity).toBeNull();
  });
});
