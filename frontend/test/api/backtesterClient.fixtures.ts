export const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

export function backtestRun(overrides: Record<string, unknown> = {}) {
  return {
    run_id: 'run-123',
    status: 'succeeded',
    submitted_at_ms: 1_780_921_805_123,
    started_at_ms: 1_780_921_900_000,
    completed_at_ms: 1_780_922_100_000,
    request_schema_version: 2,
    request: {
      symbols: ['EURUSD'],
      exchange: 'FX',
      timeframe: 'M15',
      start_ms: 1_714_521_600_000,
      end_ms: 1_714_608_000_000,
      engine: 'event_driven',
      data_granularity: 'bar',
      initial_capital: 10_000,
      strategy: {
        strategy_id: 'sma_crossover',
        parameters: { fast_window: 10, slow_window: 20 },
      },
      execution: {
        signal_timing: 'close',
        fill_timing: 'next_open',
        price_source: 'open',
        allow_partial_fills: false,
        allowed_directions: 'long_and_short',
        trade_accounting_policy: 'average_cost',
        gap_policy: 'skip',
        intrabar_exit_policy: 'conservative',
        commission_bps: 1,
        slippage_bps: 0.5,
      },
      persist_result: true,
      run_metadata: null,
    },
    result_schema_version: 3,
    metrics: {
      total_return_pct: 1.25,
      trade_count: 1,
      long_trade_count: 1,
      short_trade_count: 0,
    },
    diagnostics: { execution_duration_ms: 240_000 },
    ...overrides,
  };
}
