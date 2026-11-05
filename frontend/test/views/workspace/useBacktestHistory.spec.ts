import { shallowRef } from 'vue';
import { describe, expect, it } from 'vitest';
import type { Backtest } from '@/types/backtesterContracts';
import { useBacktestHistory } from '@/views/workspace/useBacktestHistory';
import { backtest } from '../backtestWorkspaceFixtures';

describe('Backtest history', () => {
  it('combines name search with configuration, state, and outcome filters', () => {
    const successful = {
      ...backtest('baseline', 1),
      name: 'Research baseline',
    };
    const failed = {
      ...backtest('research-multiple', 3),
      name: 'Research grid',
      has_failed_members: true,
    };
    const model = useBacktestHistory(
      shallowRef<Backtest[]>([successful, failed]),
    );
    model.search.value = ' RESEARCH ';
    expect(model.filteredHistory.value).toHaveLength(2);
    model.failedFilter.value = 'with_failed';
    expect(
      model.filteredHistory.value.map((row) => row.backtest.backtest_id),
    ).toEqual(['research-multiple']);
    model.statusFilter.value = 'running';
    expect(model.filteredHistory.value).toHaveLength(0);
    model.statusFilter.value = 'completed';
    model.marketFilter.value = 'FX:EURUSD';
    model.strategyFilter.value = 'sma';
    model.timeframeFilter.value = 'M15';
    expect(model.filteredHistory.value).toHaveLength(1);
    model.search.value = 'research-multiple-submission';
    expect(model.filteredHistory.value).toHaveLength(1);
    model.search.value = 'Research EURUSD';
    expect(model.filteredHistory.value).toHaveLength(0);
  });

  it('counts lifecycle and failed outcomes independently of Run count', () => {
    const history = shallowRef<Backtest[]>([
      { ...backtest('one', 1), has_failed_members: true },
      { ...backtest('many', 3), status: 'paused' as const },
    ]);
    const model = useBacktestHistory(history);
    expect(model.activeHistoryCount.value).toBe(1);
    expect(model.completedHistoryCount.value).toBe(1);
    expect(model.failedHistoryCount.value).toBe(1);
    history.value = [];
    expect(model.historyRows.value).toHaveLength(0);
  });
});
