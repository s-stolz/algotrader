import { afterEach, describe, expect, it, vi } from 'vitest';
import { BACKTEST_BATCH_STATUSES, type BacktestRequestPayload } from '@/types/backtesterContracts';
import queuedBatchQueue from '../fixtures/queuedBatchQueue.json';

import {
  BacktestSubmissionError,
  controlBacktestBatch,
  deleteBacktestRun,
  fetchStrategyCatalog,
  fetchSweepCapabilities,
  previewParameterSweep,
  fetchBacktestClosedTrades,
  fetchBacktestEquityCurve,
  fetchBacktestFills,
  fetchBacktestQueue,
  getBacktestRun,
  listBacktestBatchEvents,
  listBacktestRuns,
  submitBacktestBatch,
  submitBacktestRun,
} from '@/api/backtesterClient';

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

describe('backtester API client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('posts stable batch command identity and validates the revision', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse({
      batch_id: 'batch-1', status: 'pausing', lifecycle_revision: 2,
    }));
    await expect(controlBacktestBatch('batch-1', 'pause', 'command-1')).resolves.toEqual({
      batch_id: 'batch-1', status: 'pausing', lifecycle_revision: 2,
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/backtester/backtests/batches/batch-1/pause',
      expect.objectContaining({ method: 'POST', body: '{"command_id":"command-1"}' }));
  });

  it('validates live strategy metadata and accepted submission responses', async () => {
    const catalog = [{
      strategy_id: 'sma_crossover', strategy_version: 1, display_name: 'SMA crossover',
      parameters: [{ name: 'fast_window', type: 'int', nullable: false, required: false,
        default: 5, minimum: 1 }],
    }];
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(catalog))
      .mockResolvedValueOnce(jsonResponse({ run_id: 'new-run', status: 'queued' }, { status: 202 }));

    await expect(fetchStrategyCatalog()).resolves.toEqual(catalog);
    await expect(submitBacktestRun(backtestRun().request as BacktestRequestPayload)).resolves.toBe('new-run');
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/backtester/backtests/strategies');
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/backtester/backtests', expect.objectContaining({
      method: 'POST',
    }));
  });

  it('rejects catalog parameters whose runtime type disagrees with metadata', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse([{
      strategy_id: 'broken', strategy_version: 1, display_name: 'Broken',
      parameters: [{ name: 'enabled', type: 'bool', required: false,
        nullable: false, default: 1 }],
    }]));

    await expect(fetchStrategyCatalog()).rejects.toThrow('Invalid strategy catalog response');
  });

  it('keeps stale-version and field rejections structured for the creation form', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ detail: {
        code: 'strategy_version_unavailable', message: 'Strategy version is unavailable',
      } }, { status: 409 }))
      .mockResolvedValueOnce(jsonResponse({ detail: {
        code: 'invalid_parameter_combination', fields: ['fast_window', 'slow_window'],
        message: 'Fast window must be smaller than slow window',
      } }, { status: 422 }));

    await expect(submitBacktestRun(backtestRun().request as BacktestRequestPayload)).rejects.toMatchObject({
      code: 'strategy_version_unavailable',
    } satisfies Partial<BacktestSubmissionError>);
    await expect(submitBacktestRun(backtestRun().request as BacktestRequestPayload)).rejects.toMatchObject({
      code: 'invalid_parameter_combination', fields: ['fast_window', 'slow_window'],
    } satisfies Partial<BacktestSubmissionError>);
  });

  it('validates a complete bounded sweep preview and current capability', async () => {
    const { symbols: _symbols, timeframe: _timeframe, exchange: _exchange,
      strategy: _strategy, ...shared } = backtestRun().request;
    const request = { ...shared,
      strategy: { strategy_id: 'sma_crossover', strategy_version: 1 },
      markets: [1], timeframes: ['M1'],
      parameter_axes: { fast_window: { mode: 'constant', value: 5 } },
      allowed_directions: ['long_and_short'] } as Parameters<typeof previewParameterSweep>[0];
    const candidate = { candidate_ordinal: 0,
      market: { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }, timeframe: 'M1',
      parameters: { fast_window: 5 }, allowed_directions: 'long_and_short',
      status: 'ready', member_ordinal: 0, request: backtestRun().request };
    const preview = { max_sweep_candidate_count: 1000, raw_count: 1, ready_count: 1,
      excluded_count: 0, normalized_selections: { markets: [candidate.market],
        timeframes: ['M1'], parameters: { fast_window: { mode: 'constant', values: [5] } },
        allowed_directions: ['long_and_short'] }, candidates: [candidate] };
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ max_sweep_candidate_count: 1000,
        batch_acceptance_enabled: false }))
      .mockResolvedValueOnce(jsonResponse(preview))
      .mockResolvedValueOnce(jsonResponse({ ...preview, raw_count: 2 }));

    await expect(fetchSweepCapabilities()).resolves.toEqual({ max_sweep_candidate_count: 1000,
      batch_acceptance_enabled: false });
    await expect(previewParameterSweep(request)).resolves.toEqual(preview);
    await expect(previewParameterSweep(request)).rejects.toThrow('Invalid sweep preview response');
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/backtester/backtests/sweeps/preview',
      expect.objectContaining({ method: 'POST' }));
  });

  it('accepts the original batch on same-ID retries after lifecycle transitions', async () => {
    const { symbols: _symbols, timeframe: _timeframe, exchange: _exchange,
      strategy: _strategy, ...shared } = backtestRun().request;
    const request = {
      ...shared,
      strategy: { strategy_id: 'sma_crossover', strategy_version: 1 },
      markets: [1], timeframes: ['M1'],
      parameter_axes: { fast_window: { mode: 'constant', value: 5 } },
      allowed_directions: ['long_and_short'],
    } as Parameters<typeof submitBacktestBatch>[0];
    const submissionId = 'same-submission-id';
    const batchId = 'original-batch-id';
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    for (const status of BACKTEST_BATCH_STATUSES) {
      fetchMock.mockResolvedValueOnce(jsonResponse({ batch_id: batchId, status }, { status: 202 }));
    }

    for (let attempt = 0; attempt < BACKTEST_BATCH_STATUSES.length; attempt += 1) {
      await expect(submitBacktestBatch(request, submissionId)).resolves.toBe(batchId);
    }
    expect(fetchMock).toHaveBeenCalledTimes(BACKTEST_BATCH_STATUSES.length);
    for (const [url, options] of fetchMock.mock.calls) {
      expect(url).toBe('/api/backtester/backtests/batches');
      expect(options).toMatchObject({ method: 'POST' });
      expect(JSON.parse(String(options?.body))).toMatchObject({ submission_id: submissionId });
    }
    fetchMock.mockResolvedValueOnce(jsonResponse({ batch_id: batchId, status: 'unknown' },
      { status: 202 }));
    await expect(submitBacktestBatch(request, submissionId)).rejects.toThrow(
      'Invalid batch submission response',
    );
  });

  it('lists Backtest Runs through the public backtester proxy', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse([
      backtestRun({ run_id: 'run-newer' }),
      backtestRun({ run_id: 'run-older', status: 'failed' }),
    ]));

    await expect(listBacktestRuns({
      status: 'succeeded',
      symbol: 'EURUSD',
      timeframe: 'M15',
      strategy: 'sma_crossover',
      engine: 'event_driven',
      submittedFromMs: 1_780_921_800_000,
      submittedToMs: 1_780_922_100_000,
    })).resolves.toEqual([
      backtestRun({ run_id: 'run-newer' }),
      backtestRun({ run_id: 'run-older', status: 'failed' }),
    ]);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests?status=succeeded&symbol=EURUSD&timeframe=M15&strategy=sma_crossover&engine=event_driven&submitted_from_ms=1780921800000&submitted_to_ms=1780922100000',
    );
  });

  it('reads one validated queue snapshot without treating invalid data as an empty queue', async () => {
    const snapshot = {
      snapshot_at_ms: 1_780_922_100_000,
      active_run: { run_id: 'active', started_at_ms: 1_780_922_000_000,
        batch_id: null, member_ordinal: null },
      last_heartbeat_ms: 1_780_922_099_000,
      availability: 'healthy', stale_after_ms: 30_000, operational_faults: [],
      queued: [{ entry_type: 'standalone', run_id: 'waiting', batch_id: null,
        submitted_at_ms: 1_780_921_805_123, estimated_position: 1,
        next_member_ordinal: null, outcome_counts: null },
      { entry_type: 'batch', run_id: null, batch_id: 'batch-waiting',
        submitted_at_ms: 1_780_921_806_123, estimated_position: 2,
        next_member_ordinal: 1, outcome_counts: { queued: 1, running: 0,
          cancelling: 0, succeeded: 1, failed: 0, cancelled: 0 } }],
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(snapshot))
      .mockResolvedValueOnce(jsonResponse({ ...snapshot, queued: [
        { ...snapshot.queued[0], estimated_position: 0 },
      ] }));
    await expect(fetchBacktestQueue()).resolves.toEqual(snapshot);
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/backtester/backtests/queue');
    await expect(fetchBacktestQueue()).rejects.toThrow('Invalid Backtest queue response');
  });

  it('accepts the same queued-batch response emitted by the public backtester route', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(queuedBatchQueue));
    await expect(fetchBacktestQueue()).resolves.toEqual(queuedBatchQueue);
  });

  it('reads automatic batch events with their recorded prior state', async () => {
    const events = [{ batch_id: 'batch-1', revision: 0, event_type: 'accepted',
      prior_status: null, status: 'queued', occurred_at_ms: 1_780_000_000_000,
      trigger_run_id: null, reason: null },
    { batch_id: 'batch-1', revision: 1, event_type: 'started',
      prior_status: 'queued', status: 'running', occurred_at_ms: 1_780_000_001_000,
      trigger_run_id: 'member-0', reason: null }];
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(events))
      .mockResolvedValueOnce(jsonResponse([events[0], { ...events[1], prior_status: undefined }]));
    await expect(listBacktestBatchEvents('batch-1')).resolves.toEqual(events);
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/backtester/backtests/batches/batch-1/events');
    await expect(listBacktestBatchEvents('batch-1')).rejects.toThrow('Invalid Backtest Batch events response');
  });

  it('fetches one Backtest Run by run id through the public backtester proxy', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(backtestRun({ run_id: 'run-123' })),
    );

    await expect(getBacktestRun('run-123')).resolves.toEqual(backtestRun({ run_id: 'run-123' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/backtester/backtests/run-123');
  });

  it('fetches result schema version 3 closed trades for a Backtest Run', async () => {
    const trades = [
      {
        sequence: 0,
        trade_id: 'trade-1',
        symbol: 'EURUSD',
        trade_direction: 'short',
        quantity: 1_000,
        entry_timestamp_ms: 1_714_525_200_000,
        entry_price: 1.0715,
        exit_timestamp_ms: 1_714_532_400_000,
        exit_price: 1.074,
        realized_pnl: 2.5,
        fees: 0.3,
        exit_reason: 'signal',
        stop_loss_price: 1.069,
        take_profit_price: 1.075,
      },
    ];
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(trades));

    await expect(fetchBacktestClosedTrades('run-123')).resolves.toEqual(trades);
    expect(fetchMock).toHaveBeenCalledWith('/api/backtester/backtests/run-123/trades');
  });

  it('reads exact replay in milliseconds and rejects malformed curves', async () => {
    const curve = {
      availability: 'exact', reason: null, source_point_count: 2,
      returned_point_count: 2, sampled: false,
      equity_curve: [
        { timestamp_ms: 1_700_000_000_001, equity: 100, drawdown_pct: 0 },
        { timestamp_ms: 1_700_000_060_001, equity: 90, drawdown_pct: -10 },
      ],
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse(curve));
    await expect(fetchBacktestEquityCurve('run-123')).resolves.toEqual(curve);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/run-123/equity-curve?max_points=2000',
    );
    fetchMock.mockResolvedValueOnce(jsonResponse({ ...curve, equity_curve: [
      curve.equity_curve[1], curve.equity_curve[0],
    ] }));
    await expect(fetchBacktestEquityCurve('run-123')).rejects.toThrow(
      'Invalid Equity Replay response',
    );
  });

  it('fetches ordered Fills through the public backtester resource', async () => {
    const fills = [
      { sequence: 0, timestamp_ms: 1_714_525_200_000, symbol: 'EURUSD', side: 'buy',
        quantity: 1000, price: 1.0715, fees: 0.15, exit_reason: null },
      { sequence: 1, timestamp_ms: 1_714_532_400_000, symbol: 'EURUSD', side: 'sell',
        quantity: 2000, price: 1.074, fees: 0.3, exit_reason: 'signal' },
    ];
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(fills));

    await expect(fetchBacktestFills('run/123')).resolves.toEqual(fills);
    expect(fetchMock).toHaveBeenCalledWith('/api/backtester/backtests/run%2F123/fills');
  });

  it('rejects malformed or unordered execution logs', async () => {
    const fill = { sequence: 1, timestamp_ms: 1_714_525_200_000, symbol: 'EURUSD',
      side: 'sell', quantity: 2000, price: 1.074, fees: 0.3, exit_reason: null };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse([{ ...fill, side: 'short' }]));
    await expect(fetchBacktestFills('run')).rejects.toThrow('Invalid backtest fills response');
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse([fill, { ...fill, sequence: 0 }]));
    await expect(fetchBacktestFills('run')).rejects.toThrow('Invalid backtest fills response');
  });

  it('deletes one Backtest Run through the public backtester proxy', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 204 }),
    );

    await expect(deleteBacktestRun('run-123')).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith('/api/backtester/backtests/run-123', {
      method: 'DELETE',
    });
  });

  it('surfaces delete failures from the public backtester proxy', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 409, statusText: 'Conflict' }),
    );

    await expect(deleteBacktestRun('run-running')).rejects.toThrow(
      'Failed to delete backtest run: Conflict',
    );
  });

  it('rejects malformed Backtest Run and closed-trade responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse([{ run_id: 'run-123' }]));
    await expect(listBacktestRuns()).rejects.toThrow('Invalid backtest runs response');

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse({ run_id: 'run-123' }));
    await expect(getBacktestRun('run-123')).rejects.toThrow('Invalid backtest run response');

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse([{
      sequence: 0,
      trade_id: 'trade-1',
      symbol: 'EURUSD',
    }]));
    await expect(fetchBacktestClosedTrades('run-123')).rejects.toThrow(
      'Invalid backtest closed trades response',
    );
  });
});

function backtestRun(overrides: Record<string, unknown> = {}) {
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
    metrics: { total_return_pct: 1.25, trade_count: 1, long_trade_count: 1, short_trade_count: 0 },
    diagnostics: { execution_duration_ms: 240_000 },
    ...overrides,
  };
}
