import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  BACKTEST_BATCH_STATUSES,
  type BacktestRequestPayload,
} from '@/types/backtesterContracts';
import {
  BacktestSubmissionError,
  fetchStrategyCatalog,
  fetchSweepCapabilities,
  previewParameterSweep,
  submitBacktestBatch,
  submitBacktestRun,
} from '@/api/backtesterClient';
import { jsonResponse, backtestRun } from './backtesterClient.fixtures';

describe('backtester API client creation', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('validates live strategy metadata and accepted submission responses', async () => {
    const catalog = [
      {
        strategy_id: 'sma_crossover',
        strategy_version: 1,
        display_name: 'SMA crossover',
        parameters: [
          {
            name: 'fast_window',
            type: 'int',
            nullable: false,
            required: false,
            default: 5,
            minimum: 1,
          },
        ],
      },
    ];
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(catalog))
      .mockResolvedValueOnce(
        jsonResponse({ run_id: 'new-run', status: 'queued' }, { status: 202 }),
      );

    await expect(fetchStrategyCatalog()).resolves.toEqual(catalog);
    await expect(
      submitBacktestRun(backtestRun().request as BacktestRequestPayload),
    ).resolves.toBe('new-run');
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/backtester/backtests/strategies',
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/backtester/backtests',
      expect.objectContaining({
        method: 'POST',
      }),
    );
  });

  it('rejects catalog parameters whose runtime type disagrees with metadata', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse([
        {
          strategy_id: 'broken',
          strategy_version: 1,
          display_name: 'Broken',
          parameters: [
            {
              name: 'enabled',
              type: 'bool',
              required: false,
              nullable: false,
              default: 1,
            },
          ],
        },
      ]),
    );

    await expect(fetchStrategyCatalog()).rejects.toThrow(
      'Invalid strategy catalog response',
    );
  });

  it('keeps stale-version and field rejections structured for the creation form', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse(
          {
            detail: {
              code: 'strategy_version_unavailable',
              message: 'Strategy version is unavailable',
            },
          },
          { status: 409 },
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            detail: {
              code: 'invalid_parameter_combination',
              fields: ['fast_window', 'slow_window'],
              message: 'Fast window must be smaller than slow window',
            },
          },
          { status: 422 },
        ),
      );

    await expect(
      submitBacktestRun(backtestRun().request as BacktestRequestPayload),
    ).rejects.toMatchObject({
      code: 'strategy_version_unavailable',
    } satisfies Partial<BacktestSubmissionError>);
    await expect(
      submitBacktestRun(backtestRun().request as BacktestRequestPayload),
    ).rejects.toMatchObject({
      code: 'invalid_parameter_combination',
      fields: ['fast_window', 'slow_window'],
    } satisfies Partial<BacktestSubmissionError>);
  });

  it('validates a complete bounded sweep preview and current capability', async () => {
    const {
      symbols: _symbols,
      timeframe: _timeframe,
      exchange: _exchange,
      strategy: _strategy,
      ...shared
    } = backtestRun().request;
    const request = {
      ...shared,
      strategy: { strategy_id: 'sma_crossover', strategy_version: 1 },
      markets: [1],
      timeframes: ['M1'],
      parameter_axes: { fast_window: { mode: 'constant', value: 5 } },
      allowed_directions: ['long_and_short'],
    } as Parameters<typeof previewParameterSweep>[0];
    const candidate = {
      candidate_ordinal: 0,
      market: { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' },
      timeframe: 'M1',
      parameters: { fast_window: 5 },
      allowed_directions: 'long_and_short',
      status: 'ready',
      member_ordinal: 0,
      request: backtestRun().request,
    };
    const preview = {
      max_sweep_candidate_count: 1000,
      raw_count: 1,
      ready_count: 1,
      excluded_count: 0,
      normalized_selections: {
        markets: [candidate.market],
        timeframes: ['M1'],
        parameters: { fast_window: { mode: 'constant', values: [5] } },
        allowed_directions: ['long_and_short'],
      },
      candidates: [candidate],
    };
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse({
          max_sweep_candidate_count: 1000,
          batch_acceptance_enabled: false,
        }),
      )
      .mockResolvedValueOnce(jsonResponse(preview))
      .mockResolvedValueOnce(jsonResponse({ ...preview, raw_count: 2 }));

    await expect(fetchSweepCapabilities()).resolves.toEqual({
      max_sweep_candidate_count: 1000,
      batch_acceptance_enabled: false,
    });
    await expect(previewParameterSweep(request)).resolves.toEqual(preview);
    await expect(previewParameterSweep(request)).rejects.toThrow(
      'Invalid sweep preview response',
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/backtester/backtests/sweeps/preview',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('accepts the original batch on same-ID retries after lifecycle transitions', async () => {
    const {
      symbols: _symbols,
      timeframe: _timeframe,
      exchange: _exchange,
      strategy: _strategy,
      ...shared
    } = backtestRun().request;
    const request = {
      ...shared,
      strategy: { strategy_id: 'sma_crossover', strategy_version: 1 },
      markets: [1],
      timeframes: ['M1'],
      parameter_axes: { fast_window: { mode: 'constant', value: 5 } },
      allowed_directions: ['long_and_short'],
    } as Parameters<typeof submitBacktestBatch>[0];
    const submissionId = 'same-submission-id';
    const batchId = 'original-batch-id';
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    for (const status of BACKTEST_BATCH_STATUSES) {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({ batch_id: batchId, status }, { status: 202 }),
      );
    }

    for (
      let attempt = 0;
      attempt < BACKTEST_BATCH_STATUSES.length;
      attempt += 1
    ) {
      await expect(submitBacktestBatch(request, submissionId)).resolves.toBe(
        batchId,
      );
    }
    expect(fetchMock).toHaveBeenCalledTimes(BACKTEST_BATCH_STATUSES.length);
    for (const [url, options] of fetchMock.mock.calls) {
      expect(url).toBe('/api/backtester/backtests/batches');
      expect(options).toMatchObject({ method: 'POST' });
      expect(JSON.parse(String(options?.body))).toMatchObject({
        submission_id: submissionId,
      });
    }
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ batch_id: batchId, status: 'unknown' }, { status: 202 }),
    );
    await expect(submitBacktestBatch(request, submissionId)).rejects.toThrow(
      'Invalid batch submission response',
    );
  });
});
