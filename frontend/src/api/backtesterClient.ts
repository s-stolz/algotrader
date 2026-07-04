import {
  type BacktestClosedTrade,
  type BacktestRun,
  type BacktestRunListQuery,
  isBacktestClosedTradeArray,
  isBacktestRun,
  isBacktestRunArray,
} from '@/types/backtesterContracts';

import { parseJsonResponse, withQuery } from './http';

const BACKTESTS_BASE_URL = '/api/backtester/backtests';

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
