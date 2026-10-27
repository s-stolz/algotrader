import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  renameExperiment,
  cancelBacktestRun,
  controlBacktestBatch,
  deleteBacktestRun,
  deleteBacktestBatch,
} from '@/api/backtesterClient';
import { jsonResponse, backtestRun } from './backtesterClient.fixtures';

describe('backtester API client commands', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it(
    'sends only normalized names and validates rename identity ' +
      'and authoritative values',
    async () => {
      const fetchMock = vi
        .spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(jsonResponse({ run_id: 'run/a', name: 'Saved' }))
        .mockResolvedValueOnce(jsonResponse({ batch_id: 'batch', name: null }))
        .mockResolvedValueOnce(jsonResponse({ run_id: 'wrong', name: 'Saved' }))
        .mockResolvedValueOnce(
          jsonResponse({ run_id: 'run/a', name: ' untrimmed ' }),
        );
      await expect(renameExperiment('run', 'run/a', ' Saved ')).resolves.toBe(
        'Saved',
      );
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        '/api/backtester/backtests/run%2Fa/name',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: 'Saved' }),
        },
      );
      await expect(renameExperiment('batch', 'batch', '')).resolves.toBeNull();
      await expect(renameExperiment('run', 'run/a', 'Saved')).rejects.toThrow(
        'Invalid experiment name response',
      );
      await expect(renameExperiment('run', 'run/a', 'Saved')).rejects.toThrow(
        'Invalid experiment name response',
      );
      await expect(renameExperiment('run', 'run/a', 'a\nb')).rejects.toThrow(
        'single-line',
      );
      expect(fetchMock).toHaveBeenCalledTimes(4);
    },
  );

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
      '/api/backtester/backtests/run-123/cancel',
      {
        method: 'POST',
      },
    );
  });

  it('posts stable batch command identity and validates the revision', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse({
        batch_id: 'batch-1',
        status: 'pausing',
        lifecycle_revision: 2,
      }),
    );
    await expect(
      controlBacktestBatch('batch-1', 'pause', 'command-1'),
    ).resolves.toEqual({
      batch_id: 'batch-1',
      status: 'pausing',
      lifecycle_revision: 2,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/batches/batch-1/pause',
      expect.objectContaining({
        method: 'POST',
        body: '{"command_id":"command-1"}',
      }),
    );
  });

  it('accepts Cancel Batch only with the matching command identity', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          batch_id: 'batch-1',
          command_id: 'cancel-1',
          status: 'cancelling',
          lifecycle_revision: 4,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          batch_id: 'batch-1',
          command_id: 'other',
          status: 'cancelled',
          lifecycle_revision: 5,
        }),
      );
    await expect(
      controlBacktestBatch('batch-1', 'cancel', 'cancel-1'),
    ).resolves.toEqual({
      batch_id: 'batch-1',
      command_id: 'cancel-1',
      status: 'cancelling',
      lifecycle_revision: 4,
    });
    await expect(
      controlBacktestBatch('batch-1', 'cancel', 'cancel-1'),
    ).rejects.toThrow('Invalid Backtest Batch command response');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/batches/batch-1/cancel',
      expect.objectContaining({
        method: 'POST',
        body: '{"command_id":"cancel-1"}',
      }),
    );
  });

  it('deletes one Backtest Run through the public backtester proxy', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(null, { status: 204 }));

    await expect(deleteBacktestRun('run-123')).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/run-123',
      {
        method: 'DELETE',
      },
    );
  });

  it('surfaces delete failures from the public backtester proxy', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 409, statusText: 'Conflict' }),
    );

    await expect(deleteBacktestRun('run-running')).rejects.toThrow(
      'Failed to delete backtest run: Conflict',
    );
  });

  it('deletes a whole Batch through the public backtester proxy', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(null, { status: 204 }));
    await expect(deleteBacktestBatch('batch/123')).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests/batches/batch%2F123',
      {
        method: 'DELETE',
      },
    );
    fetchMock.mockResolvedValueOnce(
      new Response(null, { status: 409, statusText: 'Conflict' }),
    );
    await expect(deleteBacktestBatch('active')).rejects.toThrow(
      'Failed to delete Backtest Batch: Conflict',
    );
  });
});
