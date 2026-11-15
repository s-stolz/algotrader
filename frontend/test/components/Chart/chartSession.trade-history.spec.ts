import { describe, expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import { createChartSession } from '@/components/Chart/chartSession';
import {
  TradeHistory,
  type TradeHistoryAdapter,
} from '@/components/Chart/trade-navigation/tradeHistory';
import {
  createFakeAdapter,
  chartCandle,
  candleUpdate,
  deferred,
} from './chartSession.fixtures';

const key = { symbol: 'EURUSD', timeframe: 'M5', exchange: 'FX' };
function fixture() {
  const base = createFakeAdapter();
  const done = deferred<void>();
  const history: TradeHistoryAdapter = {
    getRange: vi.fn(() => null),
    prepare: vi.fn(),
    fetchBefore: vi.fn(async () => [chartCandle(300_000)]),
    fetchAfter: vi.fn(async () => {
      await done.promise;
      return Array.from({ length: 500 }, (_, i) =>
        chartCandle((i + 1) * 300_000),
      );
    }),
    install: vi.fn(),
    initializeIndicators: vi.fn(async () => {}),
    extendIndicators: vi.fn(async () => {}),
    historical: vi.fn(),
    loading: vi.fn(),
  };
  base.adapter.tradeHistory = new TradeHistory(history);
  return { ...base, done, history, session: createChartSession(base.adapter) };
}
describe('chart session trade history ownership', () => {
  it('supersedes a pending latest snapshot and suppresses older-page triggers', async () => {
    const f = fixture();
    const latest = deferred<ReturnType<typeof chartCandle>[]>();
    vi.mocked(f.adapter.fetchCandles).mockReturnValue(latest.promise);
    const initial = f.session.setSession(key, vi.fn());
    await flushPromises();
    const jump = f.session.jumpToTrade(300_001);
    await flushPromises();
    f.session.requestOlderHistory({ barsBefore: 0, nowMs: 1000 });
    expect(f.adapter.fetchOlderCandles).not.toHaveBeenCalled();
    latest.resolve([chartCandle(9_000_000)]);
    await initial;
    expect(f.adapter.renderCandles).not.toHaveBeenCalled();
    f.done.resolve();
    await jump;
    expect(f.history.install).toHaveBeenCalledWith(
      expect.arrayContaining([chartCandle(300_000)]),
      300_001,
    );
  });
  it('cancels the page and prevents late commits on page or context exit', async () => {
    const f = fixture();
    const receive = vi.fn();
    const jump = f.session.setSession(key, receive, 300_001);
    await flushPromises();
    expect(f.adapter.fetchCandles).not.toHaveBeenCalled();
    for (const handler of f.handlers) handler(candleUpdate(900_000));
    expect(receive).not.toHaveBeenCalled();
    const signal = vi.mocked(f.history.fetchAfter).mock.calls[0][2];
    await f.session.stop();
    expect(signal.aborted).toBe(true);
    f.done.resolve();
    await jump;
    expect(f.history.install).not.toHaveBeenCalled();
    expect(f.handlers.size).toBe(0);
  });
  it('does not recover historical windows through today after reconnect', async () => {
    const f = fixture();
    const jump = f.session.setSession(key, vi.fn(), 300_001);
    await flushPromises();
    f.done.resolve();
    await jump;
    expect(f.adapter.recovery.fetch).not.toHaveBeenCalled();
    expect(f.adapter.recovery.on).not.toHaveBeenCalled();
  });
});
