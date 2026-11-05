import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  cancelBacktestRun,
  controlBacktest,
  deleteBacktest,
} from '@/api/backtesterClient';
import { jsonResponse, backtestRun } from './backtesterClient.fixtures';

describe('backtester API client commands', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('accepts durable cancellation progress and validates the returned run', async () => {
    const cancelling = {
      ...backtestRun(),
      status: 'cancelling',
      started_at_ms: 1_780_000_000_001,
      cancel_requested_at_ms: 1_780_000_000_002,
      cancellation_source: 'user',
      cancellation_reason: 'user_requested',
    };
    const cancelled = {
      ...cancelling,
      status: 'cancelled',
      completed_at_ms: 1_780_000_000_003,
    };
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(cancelling))
      .mockResolvedValueOnce(jsonResponse(cancelled))
      .mockResolvedValueOnce(
        jsonResponse({ ...cancelled, status: 'succeeded' }),
      );

    await expect(cancelBacktestRun('run-123')).resolves.toEqual(cancelling);
    await expect(cancelBacktestRun('run-123')).resolves.toEqual(cancelled);
    await expect(cancelBacktestRun('run-123')).rejects.toThrow(
      'Invalid cancelled backtest run response',
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/backtester/backtests/runs/run-123/cancel',
      {
        method: 'POST',
      },
    );
  });

  it('posts stable backtest command identity and validates the revision', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse({
        backtest_id: 'backtest-1',
        status: 'pausing',
        lifecycle_revision: 2,
      }),
    );
    await expect(
      controlBacktest('backtest-1', 'pause', 'command-1'),
    ).resolves.toEqual({
      backtest_id: 'backtest-1',
      status: 'pausing',
      lifecycle_revision: 2,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/backtest-1/pause',
      expect.objectContaining({
        method: 'POST',
        body: '{"command_id":"command-1"}',
      }),
    );
  });

  it('accepts Cancel Backtest only with the matching command identity', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          backtest_id: 'backtest-1',
          command_id: 'cancel-1',
          status: 'cancelling',
          lifecycle_revision: 4,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          backtest_id: 'backtest-1',
          command_id: 'other',
          status: 'cancelled',
          lifecycle_revision: 5,
        }),
      );
    await expect(
      controlBacktest('backtest-1', 'cancel', 'cancel-1'),
    ).resolves.toEqual({
      backtest_id: 'backtest-1',
      command_id: 'cancel-1',
      status: 'cancelling',
      lifecycle_revision: 4,
    });
    await expect(
      controlBacktest('backtest-1', 'cancel', 'cancel-1'),
    ).rejects.toThrow('Invalid Backtest command response');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/backtest-1/cancel',
      expect.objectContaining({
        method: 'POST',
        body: '{"command_id":"cancel-1"}',
      }),
    );
  });

  it('deletes a whole Backtest through the public backtester proxy', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(null, { status: 204 }));
    await expect(deleteBacktest('backtest/123')).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/backtest%2F123',
      {
        method: 'DELETE',
      },
    );
    fetchMock.mockResolvedValueOnce(
      new Response(null, { status: 409, statusText: 'Conflict' }),
    );
    await expect(deleteBacktest('active')).rejects.toThrow(
      'Failed to delete Backtest: Conflict',
    );
  });
});
