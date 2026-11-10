import { parseJsonResponse, withQuery } from './http';
import {
  isExecutionLogPage,
  EXECUTION_LOG_PAGE_SIZE,
  type ExecutionLogPage,
} from '@/types/backtest/executionLog';

export async function fetchExecutionLog(
  runId: string,
  page: number,
  includeUnexecuted: boolean,
  signal?: AbortSignal,
): Promise<ExecutionLogPage> {
  const payload = await parseJsonResponse(
    await fetch(
      withQuery(
        `/api/backtester/backtests/runs/${encodeURIComponent(runId)}/execution-log`,
        {
          page,
          page_size: EXECUTION_LOG_PAGE_SIZE,
          include_unexecuted: String(includeUnexecuted),
        },
      ),
      { signal },
    ),
    'Failed to fetch execution log',
  );
  if (
    !isExecutionLogPage(payload) ||
    payload.run_id !== runId ||
    payload.page !== page ||
    payload.page_size !== EXECUTION_LOG_PAGE_SIZE ||
    (!includeUnexecuted && payload.items.some((item) => item.kind !== 'trade'))
  )
    throw new Error('Invalid execution log response');
  return payload;
}
