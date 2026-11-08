import { cell } from '../comparison/comparisonCells';
import { resultMetrics, formatResult } from './runResults';
import type { ComparisonColumn } from '../comparison/comparisonOptionalColumns';
import type { BacktestWorkspace } from '../useBacktestWorkspace';
export function createResultColumns(
  results: BacktestWorkspace['inspection']['tradeResults'],
): ComparisonColumn[] {
  return resultMetrics.map((metric) => ({
    title: metric.title,
    key: metric.key,
    group: 'Performance',
    width: 175,
    render: (run) => {
      const state = results.states.value[run.run_id];
      if (run.status !== 'succeeded') return cell('—');
      if (!state || state.status === 'loading')
        return cell('…', 'Loading trade statistics');
      if (state.status === 'error') return cell('—', state.error);
      return cell(
        formatResult(state.result?.metrics[metric.key] ?? null, metric.unit),
      );
    },
  }));
}
