import type { BacktestSelectionsDraft } from '@/types/backtesterContracts';
import { dailyEntryLimitIssue } from '@/types/backtest/entryLimit';
import { scheduleDraftIssues } from '@/types/backtest/schedule';
import { TIMEFRAME_CODES } from '@/types/contracts';
import { experimentNameIssue } from '../creationParameters';
import type { DraftRequest } from '../creationRequest';

export function setupIssues(
  draft: DraftRequest,
  selections: BacktestSelectionsDraft,
  strategyNeedsReview: boolean,
  missingMarkets: string[],
): Record<string, string> {
  const issues: Record<string, string> = {};
  const nameIssue = experimentNameIssue(draft.name);
  if (nameIssue) issues.name = nameIssue;
  if (strategyNeedsReview)
    issues.strategy = 'Review the current Strategy Version.';
  if (!selections.marketIds.length || missingMarkets.length)
    issues.market = 'Select an available Market.';
  if (
    !selections.timeframes.length ||
    selections.timeframes.some(
      (value) => !(TIMEFRAME_CODES as readonly string[]).includes(value),
    )
  )
    issues.timeframe = 'Select at least one supported Timeframe.';
  if (
    !selections.allowedDirections.length ||
    selections.allowedDirections.some(
      (value) => !['long_and_short', 'long_only', 'short_only'].includes(value),
    )
  )
    issues.directions = 'Select at least one direction option.';
  if (
    !Number.isFinite(draft.start_ms) ||
    !Number.isFinite(draft.end_ms) ||
    draft.start_ms <= 0 ||
    draft.end_ms <= 0
  )
    issues.dates = 'Enter valid start and end dates.';
  else if (draft.end_ms <= draft.start_ms)
    issues.dates = 'End date must be after start date.';
  if (!Number.isFinite(draft.initial_capital) || draft.initial_capital <= 0)
    issues.capital = 'Initial capital must be greater than zero.';
  const sizing = draft.execution.sizing;
  if (sizing) {
    if (!Number.isFinite(sizing.leverage) || sizing.leverage < 1)
      issues.sizing = 'Leverage must be at least 1.';
    if (
      sizing.mode !== 'strategy' &&
      (sizing.value === null ||
        !Number.isFinite(sizing.value) ||
        sizing.value <= 0)
    )
      issues.sizing = 'Enter a positive sizing amount.';
    if (
      ['risk', 'equity_risk'].includes(sizing.mode) &&
      draft.execution.stop_loss?.mode === 'none'
    )
      issues.sizing = 'Risk sizing requires an initial stop.';
  }
  for (const key of ['stop_loss', 'take_profit'] as const) {
    const exit = draft.execution[key];
    if (
      exit &&
      !['none', 'strategy'].includes(exit.mode) &&
      (exit.value === null || !Number.isFinite(exit.value) || exit.value <= 0)
    )
      issues[key] = 'Enter a positive protective distance.';
  }
  const entryIssue = dailyEntryLimitIssue(draft.execution.max_entries_per_day);
  if (entryIssue) issues.entryLimit = entryIssue;
  Object.assign(issues, scheduleDraftIssues(selections.dailySchedule));
  for (const key of ['slippage_bps', 'commission_bps'] as const) {
    const value = draft.execution[key];
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0)
      issues[key] = 'Enter zero or a positive cost.';
  }
  if (!['vectorized', 'event_driven'].includes(draft.engine))
    issues.engine = 'Select an engine.';
  if (!['skip', 'expire', 'error'].includes(draft.execution.gap_policy))
    issues.gap_policy = 'Select a gap policy.';
  if (
    !['conservative', 'stop_first', 'take_profit_first', 'error'].includes(
      draft.execution.intrabar_exit_policy,
    )
  )
    issues.intrabar_exit_policy = 'Select an exit policy.';
  if (draft.execution.execution_mode === 'orders') {
    const { spread, max_position_quantity } = draft.execution;
    if (typeof spread !== 'number' || !Number.isFinite(spread) || spread < 0)
      issues.spread = 'Enter zero or a positive spread in price units.';
    if (
      max_position_quantity != null &&
      (!Number.isFinite(max_position_quantity) || max_position_quantity <= 0)
    )
      issues.max_position_quantity =
        'Enter a positive quantity or leave empty.';
  }
  return issues;
}
