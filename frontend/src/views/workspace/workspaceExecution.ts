import type { BacktestRun } from '@/types/backtesterContracts';
import { BACKTEST_RESULT_SCHEMA_VERSION } from '@/types/backtesterContracts';
export function executionLogAvailable(run: BacktestRun): boolean {
  return (
    run.status === 'succeeded' &&
    run.result_schema_version === BACKTEST_RESULT_SCHEMA_VERSION
  );
}

export function executionLogUnavailableReason(run: BacktestRun): string {
  if (run.status !== 'succeeded')
    return `This ${run.status} run has no completed execution log.`;
  return 'A completed execution log is unavailable for this result schema.';
}
