import {
  readEquityReplayStream,
  type ReplayStreamOptions,
} from './equityReplayStream';
import {
  BACKTEST_STATUSES,
  normalizeExperimentName,
  type BacktestClosedTrade,
  type BacktestFill,
  type BacktestRun,
  type BacktestRunListQuery,
  type BacktestQueueSnapshot,
  type Backtest,
  type BacktestStatus,
  type BacktestEvent,
  type EquityReplayResponse,
  isBacktestClosedTradeArray,
  isBacktestFillArray,
  isBacktestRun,
  isBacktestRunArray,
  isBacktestQueueSnapshot,
  isBacktest,
  isBacktestArray,
  isBacktestEventArray,
  isEquityReplayResponse,
  isStrategyCatalog,
  type StrategyCatalogEntry,
  type BacktestPreview,
  type BacktestPreviewRequest,
  isBacktestPreview,
} from '@/types/backtesterContracts';

import { parseJsonResponse, withQuery } from './http';

const BACKTESTS_BASE_URL = '/api/backtester/backtests';

export async function fetchBacktestQueue(): Promise<BacktestQueueSnapshot> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/queue`),
    'Failed to fetch Backtest queue',
  );
  if (!isBacktestQueueSnapshot(payload))
    throw new Error('Invalid Backtest queue response');
  return payload;
}

export class BacktestSubmissionError extends Error {
  constructor(
    public readonly code: string,
    public readonly fields: string[],
    message: string,
  ) {
    super(message);
  }
}

export async function fetchStrategyCatalog(): Promise<StrategyCatalogEntry[]> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/strategies`),
    'Failed to fetch strategy catalog',
  );
  if (!isStrategyCatalog(payload))
    throw new Error('Invalid strategy catalog response');
  return payload;
}

export async function fetchBacktestCapabilities(): Promise<{
  max_backtest_candidate_count: number;
}> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/capabilities`),
    'Failed to fetch selections capabilities',
  );
  if (
    typeof payload !== 'object' ||
    payload === null ||
    !('max_backtest_candidate_count' in payload) ||
    !Number.isInteger(payload.max_backtest_candidate_count) ||
    (payload.max_backtest_candidate_count as number) <= 0
  ) {
    throw new Error('Invalid selections capabilities response');
  }
  return payload as {
    max_backtest_candidate_count: number;
  };
}

export async function submitBacktest(
  request: BacktestPreviewRequest,
  submissionId: string,
  name: string | null = null,
): Promise<string> {
  const response = await fetch(`${BACKTESTS_BASE_URL}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...request, submission_id: submissionId, name }),
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    if (
      typeof payload === 'object' &&
      payload !== null &&
      'detail' in payload &&
      typeof payload.detail === 'object' &&
      payload.detail !== null &&
      'code' in payload.detail &&
      typeof payload.detail.code === 'string'
    ) {
      const detail = payload.detail;
      const code = detail.code as string;
      throw new BacktestSubmissionError(
        code,
        'fields' in detail && Array.isArray(detail.fields)
          ? detail.fields.filter(
              (field): field is string => typeof field === 'string',
            )
          : [],
        'message' in detail && typeof detail.message === 'string'
          ? detail.message
          : code,
      );
    }
    throw new Error(
      `Backtest submission failed: ${response.statusText || response.status}`,
    );
  }
  if (
    response.status !== 202 ||
    typeof payload !== 'object' ||
    payload === null ||
    !('backtest_id' in payload) ||
    typeof payload.backtest_id !== 'string' ||
    !('status' in payload) ||
    typeof payload.status !== 'string' ||
    !BACKTEST_STATUSES.includes(payload.status as BacktestStatus)
  ) {
    throw new Error('Invalid backtest submission response');
  }
  return payload.backtest_id;
}

export async function renameExperiment(
  id: string,
  name: string | null,
): Promise<string | null> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/${encodeURIComponent(id)}/name`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: normalizeExperimentName(name) }),
    }),
    'Failed to save experiment name',
  );
  const identity = 'backtest_id';
  if (
    typeof payload !== 'object' ||
    payload === null ||
    !(identity in payload) ||
    (payload as Record<string, unknown>)[identity] !== id ||
    !('name' in payload) ||
    (payload.name !== null && typeof payload.name !== 'string') ||
    normalizeExperimentName(payload.name) !== payload.name
  ) {
    throw new Error('Invalid experiment name response');
  }
  return payload.name;
}

export async function listBacktests(): Promise<Backtest[]> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}`),
    'Failed to fetch Backtestes',
  );
  if (!isBacktestArray(payload))
    throw new Error('Invalid Backtest list response');
  return payload;
}

export async function getBacktest(backtestId: string): Promise<Backtest> {
  const payload = await parseJsonResponse(
    await fetch(`${BACKTESTS_BASE_URL}/${encodeURIComponent(backtestId)}`),
    'Failed to fetch Backtest',
  );
  if (!isBacktest(payload)) throw new Error('Invalid Backtest response');
  return payload;
}

export async function listBacktestMembers(
  backtestId: string,
  includeDiagnostics = true,
): Promise<BacktestRun[]> {
  const payload = await parseJsonResponse(
    await fetch(
      withQuery(
        `${BACKTESTS_BASE_URL}/${encodeURIComponent(backtestId)}/runs`,
        {
          include_diagnostics: includeDiagnostics ? undefined : 'false',
        },
      ),
    ),
    'Failed to fetch Backtest members',
  );
  if (
    !isBacktestRunArray(payload) ||
    payload.some((run) => run.backtest_id !== backtestId)
  ) {
    throw new Error('Invalid Backtest members response');
  }
  return payload;
}

export async function listBacktestEvents(
  backtestId: string,
): Promise<BacktestEvent[]> {
  const payload = await parseJsonResponse(
    await fetch(
      `${BACKTESTS_BASE_URL}/${encodeURIComponent(backtestId)}/events`,
    ),
    'Failed to fetch Backtest events',
  );
  if (
    !isBacktestEventArray(payload) ||
    payload.some((event) => event.backtest_id !== backtestId)
  ) {
    throw new Error('Invalid Backtest events response');
  }
  return payload;
}

export async function controlBacktest(
  backtestId: string,
  command: 'pause' | 'resume' | 'cancel',
  commandId: string,
): Promise<{
  backtest_id: string;
  status: BacktestStatus;
  lifecycle_revision: number;
  command_id?: string;
}> {
  const payload = await parseJsonResponse(
    await fetch(
      `${BACKTESTS_BASE_URL}/${encodeURIComponent(backtestId)}/${command}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command_id: commandId }),
      },
    ),
    `Failed to ${command} Backtest`,
  );
  if (
    typeof payload !== 'object' ||
    payload === null ||
    !('backtest_id' in payload) ||
    payload.backtest_id !== backtestId ||
    !('status' in payload) ||
    typeof payload.status !== 'string' ||
    !BACKTEST_STATUSES.includes(payload.status as BacktestStatus) ||
    !('lifecycle_revision' in payload) ||
    !Number.isInteger(payload.lifecycle_revision) ||
    (command === 'cancel' &&
      (!('command_id' in payload) || payload.command_id !== commandId))
  ) {
    throw new Error('Invalid Backtest command response');
  }
  return payload as {
    backtest_id: string;
    status: BacktestStatus;
    lifecycle_revision: number;
    command_id?: string;
  };
}

export async function previewBacktest(
  request: BacktestPreviewRequest,
): Promise<BacktestPreview> {
  const response = await fetch(`${BACKTESTS_BASE_URL}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    if (
      typeof payload === 'object' &&
      payload !== null &&
      'detail' in payload &&
      typeof payload.detail === 'object' &&
      payload.detail !== null &&
      'code' in payload.detail &&
      typeof payload.detail.code === 'string'
    ) {
      const detail = payload.detail;
      const code = detail.code as string;
      throw new BacktestSubmissionError(
        code,
        'fields' in detail && Array.isArray(detail.fields)
          ? detail.fields.filter(
              (field): field is string => typeof field === 'string',
            )
          : [],
        'message' in detail && typeof detail.message === 'string'
          ? detail.message
          : code,
      );
    }
    throw new Error(
      `Backtest preview failed: ${response.statusText || response.status}`,
    );
  }
  if (!isBacktestPreview(payload))
    throw new Error('Invalid backtest preview response');
  return payload;
}

export async function getBacktestRun(
  runId: string,
  includeDiagnostics = true,
): Promise<BacktestRun> {
  const payload = await parseJsonResponse(
    await fetch(
      withQuery(`${BACKTESTS_BASE_URL}/runs/${encodeURIComponent(runId)}`, {
        include_diagnostics: includeDiagnostics ? undefined : 'false',
      }),
    ),
    'Failed to fetch backtest run',
  );

  if (!isBacktestRun(payload)) {
    throw new Error('Invalid backtest run response');
  }

  return payload;
}

export async function cancelBacktestRun(runId: string): Promise<BacktestRun> {
  const payload = await parseJsonResponse(
    await fetch(
      `${BACKTESTS_BASE_URL}/runs/${encodeURIComponent(runId)}/cancel`,
      {
        method: 'POST',
      },
    ),
    'Failed to cancel backtest run',
  );
  if (
    !isBacktestRun(payload) ||
    !['cancelling', 'cancelled'].includes(payload.status)
  ) {
    throw new Error('Invalid cancelled backtest run response');
  }
  return payload;
}

export async function deleteBacktest(backtestId: string): Promise<void> {
  const response = await fetch(
    `${BACKTESTS_BASE_URL}/${encodeURIComponent(backtestId)}`,
    {
      method: 'DELETE',
    },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to delete Backtest: ${await deletionFailure(response)}`,
    );
  }
}

async function deletionFailure(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof body.detail === 'string'
    )
      return body.detail;
  } catch {
    // A proxy may return an empty body; retain its HTTP status explanation.
  }
  return response.statusText || String(response.status);
}

export async function fetchBacktestClosedTrades(
  runId: string,
): Promise<BacktestClosedTrade[]> {
  const payload = await parseJsonResponse(
    await fetch(
      `${BACKTESTS_BASE_URL}/runs/${encodeURIComponent(runId)}/trades`,
    ),
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
  stream?: ReplayStreamOptions,
): Promise<EquityReplayResponse> {
  if (stream)
    return readEquityReplayStream(
      withQuery(
        `${BACKTESTS_BASE_URL}/runs/${encodeURIComponent(runId)}/equity-curve/stream`,
        { max_points: maxPoints },
      ),
      stream,
    );
  const payload = await parseJsonResponse(
    await fetch(
      withQuery(
        `${BACKTESTS_BASE_URL}/runs/${encodeURIComponent(runId)}/equity-curve`,
        {
          max_points: maxPoints,
        },
      ),
    ),
    'Failed to fetch exact Equity Replay',
  );
  if (!isEquityReplayResponse(payload))
    throw new Error('Invalid Equity Replay response');
  return payload;
}

export async function fetchBacktestFills(
  runId: string,
): Promise<BacktestFill[]> {
  const payload = await parseJsonResponse(
    await fetch(
      `${BACKTESTS_BASE_URL}/runs/${encodeURIComponent(runId)}/fills`,
    ),
    'Failed to fetch backtest fills',
  );

  if (!isBacktestFillArray(payload)) {
    throw new Error('Invalid backtest fills response');
  }

  return payload;
}

export async function listBacktestRuns(
  query: BacktestRunListQuery = {},
  includeDiagnostics = true,
): Promise<BacktestRun[]> {
  const payload = await parseJsonResponse(
    await fetch(
      withQuery(`${BACKTESTS_BASE_URL}/runs`, {
        include_diagnostics: includeDiagnostics ? undefined : 'false',
        status: query.status,
        symbol: query.symbol,
        timeframe: query.timeframe,
        strategy: query.strategy,
        engine: query.engine,
        submitted_from_ms: query.submittedFromMs,
        submitted_to_ms: query.submittedToMs,
        backtest_id: query.backtestId,
      }),
    ),
    'Failed to fetch backtest runs',
  );

  if (!isBacktestRunArray(payload)) {
    throw new Error('Invalid backtest runs response');
  }

  return payload;
}
