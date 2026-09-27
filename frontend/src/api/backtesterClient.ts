import {
  type BacktestClosedTrade,
  type BacktestFill,
  type BacktestRun,
  type EquityReplayResponse,
  type BacktestRunListQuery,
  isBacktestClosedTradeArray,
  isBacktestFillArray,
  isBacktestRun,
  isBacktestRunArray,
  isEquityReplayResponse,
  isStrategyCatalog,
  type BacktestRequestPayload,
  type StrategyCatalogEntry,
  type SweepPreview,
  type SweepPreviewRequest,
  isSweepPreview,
} from '@/types/backtesterContracts';

import { parseJsonResponse, withQuery } from './http';

const BACKTESTS_BASE_URL = '/api/backtester/backtests';

export class BacktestSubmissionError extends Error {
  constructor(public readonly code: string, public readonly fields: string[], message: string) {
    super(message);
  }
}

export async function fetchStrategyCatalog(): Promise<StrategyCatalogEntry[]> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/strategies`), 'Failed to fetch strategy catalog',
  );
  if (!isStrategyCatalog(payload)) throw new Error('Invalid strategy catalog response');
  return payload;
}

export async function fetchSweepCapabilities(): Promise<{ max_sweep_candidate_count: number }> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/capabilities`), 'Failed to fetch sweep capabilities',
  );
  if (typeof payload !== 'object' || payload === null ||
      !('max_sweep_candidate_count' in payload) ||
      !Number.isInteger(payload.max_sweep_candidate_count) ||
      (payload.max_sweep_candidate_count as number) <= 0) {
    throw new Error('Invalid sweep capabilities response');
  }
  return payload as { max_sweep_candidate_count: number };
}

export async function previewParameterSweep(request: SweepPreviewRequest): Promise<SweepPreview> {
  const response = await fetch(`${BACKTESTS_BASE_URL}/sweeps/preview`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    if (typeof payload === 'object' && payload !== null && 'detail' in payload &&
        typeof payload.detail === 'object' && payload.detail !== null &&
        'code' in payload.detail && typeof payload.detail.code === 'string') {
      const detail = payload.detail;
      const code = detail.code as string;
      throw new BacktestSubmissionError(code,
        'fields' in detail && Array.isArray(detail.fields) ?
          detail.fields.filter((field): field is string => typeof field === 'string') : [],
        'message' in detail && typeof detail.message === 'string' ? detail.message : code);
    }
    throw new Error(`Sweep preview failed: ${response.statusText || response.status}`);
  }
  if (!isSweepPreview(payload)) throw new Error('Invalid sweep preview response');
  return payload;
}

export async function submitBacktestRun(request: BacktestRequestPayload): Promise<string> {
  const response = await fetch(BACKTESTS_BASE_URL, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
      const detail = payload.detail;
      if (typeof detail === 'object' && detail !== null && 'code' in detail &&
        typeof detail.code === 'string') {
        const fields = 'fields' in detail && Array.isArray(detail.fields)
          ? detail.fields.filter((field): field is string => typeof field === 'string') : [];
        throw new BacktestSubmissionError(detail.code, fields,
          'message' in detail && typeof detail.message === 'string' ? detail.message : detail.code);
      }
    }
    throw new Error(`Backtest submission failed: ${response.statusText || response.status}`);
  }
  if (response.status !== 202 || typeof payload !== 'object' || payload === null ||
    !('run_id' in payload) || typeof payload.run_id !== 'string' ||
    !('status' in payload) || payload.status !== 'queued') {
    throw new Error('Invalid backtest submission response');
  }
  return payload.run_id;
}

export async function listBacktestRuns(
  query: BacktestRunListQuery = {},
): Promise<BacktestRun[]> {
  const payload = await parseJsonResponse(
    await fetch(withQuery(BACKTESTS_BASE_URL, {
      status: query.status,
      symbol: query.symbol,
      timeframe: query.timeframe,
      strategy: query.strategy,
      engine: query.engine,
      submitted_from_ms: query.submittedFromMs,
      submitted_to_ms: query.submittedToMs,
    })),
    'Failed to fetch backtest runs',
  );

  if (!isBacktestRunArray(payload)) {
    throw new Error('Invalid backtest runs response');
  }

  return payload;
}

export async function getBacktestRun(runId: string): Promise<BacktestRun> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/${encodeURIComponent(runId)}`),
    'Failed to fetch backtest run',
  );

  if (!isBacktestRun(payload)) {
    throw new Error('Invalid backtest run response');
  }

  return payload;
}

export async function deleteBacktestRun(runId: string): Promise<void> {
  const response = await fetch(`${BACKTESTS_BASE_URL}/${encodeURIComponent(runId)}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Failed to delete backtest run: ${response.statusText || response.status}`);
  }
}

export async function fetchBacktestClosedTrades(
  runId: string,
): Promise<BacktestClosedTrade[]> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/${encodeURIComponent(runId)}/trades`),
    'Failed to fetch backtest closed trades',
  );

  if (!isBacktestClosedTradeArray(payload)) {
    throw new Error('Invalid backtest closed trades response');
  }

  return payload;
}

export async function fetchBacktestEquityCurve(
  runId: string,
  maxPoints = 2000,
): Promise<EquityReplayResponse> {
  const payload = await parseJsonResponse(
    await fetch(withQuery(`${BACKTESTS_BASE_URL}/${encodeURIComponent(runId)}/equity-curve`, {
      max_points: maxPoints,
    })),
    'Failed to fetch exact Equity Replay',
  );
  if (!isEquityReplayResponse(payload)) throw new Error('Invalid Equity Replay response');
  return payload;
}

export async function fetchBacktestFills(runId: string): Promise<BacktestFill[]> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/${encodeURIComponent(runId)}/fills`),
    'Failed to fetch backtest fills',
  );

  if (!isBacktestFillArray(payload)) {
    throw new Error('Invalid backtest fills response');
  }

  return payload;
}
