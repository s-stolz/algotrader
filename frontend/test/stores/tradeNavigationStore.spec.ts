import { createPinia, setActivePinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getBacktestRun,
  fetchBacktestClosedTrades,
  fetchBacktestFills,
} from '@/api/backtesterClient';
import { useTradeNavigationStore } from '@/stores/tradeNavigationStore';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import { useMarketsStore } from '@/stores/marketsStore';
import { useExecutionLogStore } from '@/stores/executionLogStore';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { backtestRun } from '../api/backtesterClient.fixtures';
import { deferred } from '../executionLogFixtures';

vi.mock('@/api/backtesterClient', () => ({
  getBacktestRun: vi.fn(),
  fetchBacktestClosedTrades: vi.fn(),
  fetchBacktestFills: vi.fn(),
}));
beforeEach(() => {
  localStorage.clear();
  setActivePinia(createPinia());
  vi.resetAllMocks();
  useMarketsStore().all = [
    {
      symbol_id: 1,
      symbol: 'EURUSD',
      exchange: 'FX',
      market_type: 'forex',
      min_move: 0.0001,
      timezone: 'UTC',
    },
  ];
  vi.mocked(getBacktestRun).mockResolvedValue(backtestRun());
  vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([]);
  vi.mocked(fetchBacktestFills).mockResolvedValue([]);
});
async function routerFixture() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/backtests', component: { template: '<div />' } },
      { path: '/other', component: { template: '<div />' } },
    ],
  });
  await router.push('/backtests');
  return router;
}
describe('trade chart navigation', () => {
  it('synchronizes the run and routes to Chart without changing the trade log', async () => {
    const router = await routerFixture();
    const log = useExecutionLogStore();
    log.isOpen = true;
    log.page = 3;
    const navigation = useTradeNavigationStore();
    await navigation.open('run-123', 123_000, router);
    expect(router.currentRoute.value.path).toBe('/');
    expect(useBacktestOverlayStore().selectedRunId).toBe('run-123');
    expect(useCurrentTimeframeStore().value).toBe('M15');
    expect(navigation.destination).toMatchObject({
      runId: 'run-123',
      timestampMs: 123_000,
    });
    expect(log.isOpen).toBe(true);
    expect(log.page).toBe(3);
  });
  it('reuses the selected run and replaces a pending destination', async () => {
    const router = await routerFixture();
    const navigation = useTradeNavigationStore();
    const old = deferred<ReturnType<typeof backtestRun>>();
    vi.mocked(getBacktestRun).mockReturnValueOnce(old.promise);
    const first = navigation.open('old-run', 100, router);
    await vi.waitFor(() =>
      expect(getBacktestRun).toHaveBeenCalledWith('old-run'),
    );
    await navigation.open('run-123', 200, router);
    old.resolve(backtestRun({ run_id: 'old-run' }));
    await first;
    expect(navigation.destination?.timestampMs).toBe(200);
    expect(useBacktestOverlayStore().selectedRunId).toBe('run-123');
    vi.mocked(getBacktestRun).mockClear();
    await navigation.open('run-123', 300, router);
    expect(getBacktestRun).not.toHaveBeenCalled();
    expect(navigation.destination?.timestampMs).toBe(300);
  });
  it('skips run reads superseded while the client module is loading', async () => {
    const router = await routerFixture();
    const navigation = useTradeNavigationStore();
    const first = navigation.open('old-run', 100, router);
    await navigation.open('run-123', 200, router);
    await first;
    expect(getBacktestRun).toHaveBeenCalledOnce();
    expect(getBacktestRun).toHaveBeenCalledWith('run-123');
    expect(navigation.destination?.timestampMs).toBe(200);
  });
  it('does not switch the chart when the user leaves during artifact loading', async () => {
    const router = await routerFixture();
    const fills = deferred<[]>();
    vi.mocked(fetchBacktestFills).mockReturnValue(fills.promise);
    const navigation = useTradeNavigationStore();
    const work = navigation.open('run-123', 100, router);
    await vi.waitFor(() => expect(fetchBacktestFills).toHaveBeenCalled());
    await router.push('/other');
    fills.resolve([]);
    await work;
    expect(router.currentRoute.value.path).toBe('/other');
    expect(navigation.destination).toBeNull();
    expect(useBacktestOverlayStore().selectedRunId).toBeNull();
  });
  it('does not overwrite a manual timeframe change during run loading', async () => {
    const router = await routerFixture();
    const pending = deferred<ReturnType<typeof backtestRun>>();
    vi.mocked(getBacktestRun).mockReturnValueOnce(pending.promise);
    const navigation = useTradeNavigationStore();
    const work = navigation.open('run-123', 100, router);
    await vi.waitFor(() =>
      expect(getBacktestRun).toHaveBeenCalledWith('run-123'),
    );
    useCurrentTimeframeStore().setCurrentTimeframe({
      label: 'H4',
      value: 'H4',
    });
    pending.resolve(backtestRun());
    await work;
    expect(navigation.destination).toBeNull();
    expect(useCurrentTimeframeStore().value).toBe('H4');
  });
});
