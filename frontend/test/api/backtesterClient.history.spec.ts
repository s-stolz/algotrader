import { afterEach, describe, expect, it, vi } from 'vitest';
import queuedBatchQueue from '../fixtures/queuedBatchQueue.json';
import {
  fetchBacktestClosedTrades,
  fetchBacktestEquityCurve,
  fetchBacktestFills,
  fetchBacktestQueue,
  getBacktestRun,
  listBacktestBatchEvents,
  listBacktestRuns,
} from '@/api/backtesterClient';
import { jsonResponse, backtestRun } from './backtesterClient.fixtures';

describe('backtester API client history', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('lists Backtest Runs through the public backtester proxy', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        jsonResponse([
          backtestRun({ run_id: 'run-newer' }),
          backtestRun({ run_id: 'run-older', status: 'failed' }),
        ]),
      );

    await expect(
      listBacktestRuns({
        status: 'succeeded',
        symbol: 'EURUSD',
        timeframe: 'M15',
        strategy: 'sma_crossover',
        engine: 'event_driven',
        submittedFromMs: 1_780_921_800_000,
        submittedToMs: 1_780_922_100_000,
      }),
    ).resolves.toEqual([
      backtestRun({ run_id: 'run-newer' }),
      backtestRun({ run_id: 'run-older', status: 'failed' }),
    ]);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests?status=succeeded&symbol=EURUSD&timeframe=M15&strategy=sma_crossover&engine=event_driven&submitted_from_ms=1780921800000&submitted_to_ms=1780922100000',
    );
  });

  it(
    'reads one validated queue snapshot without treating invalid data ' +
      'as an empty queue',
    async () => {
      const snapshot = {
        snapshot_at_ms: 1_780_922_100_000,
        active_run: {
          run_id: 'active',
          started_at_ms: 1_780_922_000_000,
          batch_id: null,
          member_ordinal: null,
        },
        last_heartbeat_ms: 1_780_922_099_000,
        availability: 'healthy',
        stale_after_ms: 30_000,
        operational_faults: [],
        queued: [
          {
            entry_type: 'standalone',
            run_id: 'waiting',
            batch_id: null,
            submitted_at_ms: 1_780_921_805_123,
            estimated_position: 1,
            next_member_ordinal: null,
            outcome_counts: null,
          },
          {
            entry_type: 'batch',
            run_id: null,
            batch_id: 'batch-waiting',
            submitted_at_ms: 1_780_921_806_123,
            estimated_position: 2,
            next_member_ordinal: 1,
            outcome_counts: {
              queued: 1,
              running: 0,
              cancelling: 0,
              succeeded: 1,
              failed: 0,
              cancelled: 0,
            },
          },
        ],
      };
      const fetchMock = vi
        .spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(jsonResponse(snapshot))
        .mockResolvedValueOnce(
          jsonResponse({
            ...snapshot,
            queued: [{ ...snapshot.queued[0], estimated_position: 0 }],
          }),
        );
      await expect(fetchBacktestQueue()).resolves.toEqual(snapshot);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        '/api/backtester/backtests/queue',
      );
      await expect(fetchBacktestQueue()).rejects.toThrow(
        'Invalid Backtest queue response',
      );
    },
  );

  it('accepts the same queued-batch response emitted by the public backtester route', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(queuedBatchQueue),
    );
    await expect(fetchBacktestQueue()).resolves.toEqual(queuedBatchQueue);
  });

  it('reads automatic batch events with their recorded prior state', async () => {
    const events = [
      {
        batch_id: 'batch-1',
        revision: 0,
        event_type: 'accepted',
        prior_status: null,
        status: 'queued',
        occurred_at_ms: 1_780_000_000_000,
        trigger_run_id: null,
        reason: null,
      },
      {
        batch_id: 'batch-1',
        revision: 1,
        event_type: 'started',
        prior_status: 'queued',
        status: 'running',
        occurred_at_ms: 1_780_000_001_000,
        trigger_run_id: 'member-0',
        reason: null,
      },
    ];
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(events))
      .mockResolvedValueOnce(
        jsonResponse([events[0], { ...events[1], prior_status: undefined }]),
      );
    await expect(listBacktestBatchEvents('batch-1')).resolves.toEqual(events);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/backtester/backtests/batches/batch-1/events',
    );
    await expect(listBacktestBatchEvents('batch-1')).rejects.toThrow(
      'Invalid Backtest Batch events response',
    );
  });

  it('fetches one Backtest Run by run id through the public backtester proxy', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse(backtestRun({ run_id: 'run-123' })));

    await expect(getBacktestRun('run-123')).resolves.toEqual(
      backtestRun({ run_id: 'run-123' }),
    );
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
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse(trades));

    await expect(fetchBacktestClosedTrades('run-123')).resolves.toEqual(trades);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/run-123/trades',
    );
  });

  it('reads exact replay in milliseconds and rejects malformed curves', async () => {
    const curve = {
      availability: 'exact',
      reason: null,
      source_point_count: 2,
      returned_point_count: 2,
      sampled: false,
      equity_curve: [
        { timestamp_ms: 1_700_000_000_001, equity: 100, drawdown_pct: 0 },
        { timestamp_ms: 1_700_000_060_001, equity: 90, drawdown_pct: -10 },
      ],
    };
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(curve));
    await expect(fetchBacktestEquityCurve('run-123')).resolves.toEqual(curve);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/run-123/equity-curve?max_points=2000',
    );
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        ...curve,
        equity_curve: [curve.equity_curve[1], curve.equity_curve[0]],
      }),
    );
    await expect(fetchBacktestEquityCurve('run-123')).rejects.toThrow(
      'Invalid Equity Replay response',
    );
  });

  it('fetches ordered Fills through the public backtester resource', async () => {
    const fills = [
      {
        sequence: 0,
        timestamp_ms: 1_714_525_200_000,
        symbol: 'EURUSD',
        side: 'buy',
        quantity: 1000,
        price: 1.0715,
        fees: 0.15,
        exit_reason: null,
      },
      {
        sequence: 1,
        timestamp_ms: 1_714_532_400_000,
        symbol: 'EURUSD',
        side: 'sell',
        quantity: 2000,
        price: 1.074,
        fees: 0.3,
        exit_reason: 'signal',
      },
    ];
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse(fills));

    await expect(fetchBacktestFills('run/123')).resolves.toEqual(fills);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/run%2F123/fills',
    );
  });

  it('rejects malformed or unordered execution logs', async () => {
    const fill = {
      sequence: 1,
      timestamp_ms: 1_714_525_200_000,
      symbol: 'EURUSD',
      side: 'sell',
      quantity: 2000,
      price: 1.074,
      fees: 0.3,
      exit_reason: null,
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse([{ ...fill, side: 'short' }]),
    );
    await expect(fetchBacktestFills('run')).rejects.toThrow(
      'Invalid backtest fills response',
    );
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse([fill, { ...fill, sequence: 0 }]),
    );
    await expect(fetchBacktestFills('run')).rejects.toThrow(
      'Invalid backtest fills response',
    );
  });

  it('rejects malformed Backtest Run and closed-trade responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse([{ run_id: 'run-123' }]),
    );
    await expect(listBacktestRuns()).rejects.toThrow(
      'Invalid backtest runs response',
    );

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse({ run_id: 'run-123' }),
    );
    await expect(getBacktestRun('run-123')).rejects.toThrow(
      'Invalid backtest run response',
    );

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse([
        {
          sequence: 0,
          trade_id: 'trade-1',
          symbol: 'EURUSD',
        },
      ]),
    );
    await expect(fetchBacktestClosedTrades('run-123')).rejects.toThrow(
      'Invalid backtest closed trades response',
    );
  });
});
