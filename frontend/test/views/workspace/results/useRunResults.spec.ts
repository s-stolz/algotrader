import { effectScope, ref, nextTick } from 'vue';
import { flushPromises } from '@vue/test-utils';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchBacktestClosedTrades } from '@/api/backtesterClient';
import { useRunResults } from '@/views/workspace/results/useRunResults';
import { resultRun, resultTrade } from './resultFixtures';
import type { BacktestClosedTrade } from '@/types/backtesterContracts';
vi.mock('@/api/backtesterClient', () => ({
  fetchBacktestClosedTrades: vi.fn(),
}));
afterEach(() => vi.resetAllMocks());
describe('saved trade result loading', () => {
  it.each([0, 2.5, 'infinity', null] as const)(
    'uses saved %s even when trades disagree',
    async (value) => {
      vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([resultTrade(99)]);
      const run = resultRun();
      run.metrics = { profit_factor: value };
      const scope = effectScope();
      const results = scope.run(() => useRunResults(ref([run])))!;
      await flushPromises();
      expect(results.states.value.run.result?.metrics['profit-factor']).toBe(
        value === 'infinity' ? Infinity : value,
      );
      expect(results.states.value.run.result?.metrics['net-profit']).toBe(99);
      scope.stop();
    },
  );
  it('limits concurrency, loads unselected runs, and ignores old Backtest responses', async () => {
    const pending: ((value: BacktestClosedTrade[]) => void)[] = [];
    vi.mocked(fetchBacktestClosedTrades).mockImplementation(
      () => new Promise((resolve) => pending.push(resolve)),
    );
    const scope = effectScope();
    const runs = ref(
      Array.from({ length: 8 }, (_, i) => resultRun(`old-${i}`)),
    );
    const results = scope.run(() => useRunResults(runs))!;
    expect(fetchBacktestClosedTrades).toHaveBeenCalledTimes(4);
    runs.value = [resultRun('new')];
    await nextTick();
    expect(fetchBacktestClosedTrades).toHaveBeenCalledTimes(4);
    pending[0]([resultTrade(999)]);
    await flushPromises();
    pending[4]([resultTrade(5)]);
    await flushPromises();
    expect(Object.keys(results.states.value)).toEqual(['new']);
    expect(results.states.value.new.result?.metrics['net-profit']).toBe(5);
    scope.stop();
  });
  it('retains ready results, exposes failures, and retries only failed reads', async () => {
    vi.mocked(fetchBacktestClosedTrades).mockImplementation(async (id) => {
      if (id === 'bad') throw new Error('offline');
      return [resultTrade(7)];
    });
    const scope = effectScope();
    const results = scope.run(() =>
      useRunResults(ref([resultRun('good'), resultRun('bad')])),
    )!;
    await flushPromises();
    expect(results.states.value.bad).toMatchObject({
      status: 'error',
      error: 'offline',
    });
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([]);
    results.retry();
    await flushPromises();
    expect(fetchBacktestClosedTrades).toHaveBeenCalledTimes(3);
    expect(results.states.value.good.result?.metrics['net-profit']).toBe(7);
    expect(results.states.value.bad.result?.metrics['net-profit']).toBe(0);
    scope.stop();
  });
  it('ignores responses while stopped and resumes unfinished reads', async () => {
    let resolve!: (trades: BacktestClosedTrade[]) => void;
    vi.mocked(fetchBacktestClosedTrades).mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const scope = effectScope();
    const results = scope.run(() => useRunResults(ref([resultRun()])))!;
    results.stop();
    resolve([resultTrade(999)]);
    await flushPromises();
    expect(results.states.value.run.result).toBeUndefined();
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([resultTrade(3)]);
    results.start();
    await flushPromises();
    expect(results.states.value.run.result?.metrics['net-profit']).toBe(3);
    scope.stop();
  });
});
