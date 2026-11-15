import {
  backtest,
  member,
} from '../../../components/Backtest/backtestOverviewFixtures';
import type { BacktestRun } from '@/types/backtesterContracts';
export function savedHeatmap() {
  const accepted = structuredClone(backtest);
  const runs: BacktestRun[] = [member(0), member(1), member(2)];
  accepted.status = 'completed';
  accepted.completed_at_ms = 1_780_000_002_000;
  accepted.accepted_definition.shared_request.end_ms = 1_714_608_000_000;
  accepted.excluded_count = 9;
  accepted.executed_count = 3;
  accepted.strategy_metadata.parameters = [
    { name: 'fast', type: 'int', nullable: true, required: true },
    { name: 'slow', type: 'float', nullable: false, required: true },
    { name: 'choice', type: 'str', nullable: false, required: true },
  ];
  accepted.accepted_definition.normalized_selections.parameters = {
    fast: { mode: 'values', values: [10, null, 1] },
    slow: { mode: 'values', values: [20, 70] },
    choice: { mode: 'values', values: ['1', 'two'] },
  };
  accepted.raw_count = 12;
  accepted.member_count = accepted.total_count = accepted.settled_count = 3;
  accepted.outcome_counts = {
    queued: 0,
    running: 0,
    cancelling: 0,
    succeeded: 3,
    failed: 0,
    cancelled: 0,
  };
  runs.forEach((run, index) => {
    run.status = 'succeeded';
    run.request.strategy.parameters = {
      fast: index === 0 ? 10 : index === 1 ? 1 : null,
      slow: index === 2 ? 70 : 20,
      choice: index === 2 ? 'two' : '1',
    };
    run.metrics = {
      profit_factor: index === 0 ? 'infinity' : index === 1 ? 0 : null,
      total_return_pct: [-10.12345, 0, 1000][index],
      max_drawdown_pct: -index,
      ending_equity: 10000 + index,
    };
  });
  return { accepted, runs };
}
