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
    prepare: vi.fn(),
    fetchBefore: vi.fn(async () => [chartCandle(300_000)]),
    stream: vi.fn(async (_key, _start, _end, _signal, onBatch) => {
      await done.promise;
      await onBatch([chartCandle(300_000)]);
    }),
    append: vi.fn(),
    initializeIndicators: vi.fn(async () => {}),
    extendIndicators: vi.fn(async () => {}),
    finish: vi.fn(),
    cancel: vi.fn(),
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
    expect(f.history.append).toHaveBeenCalledWith(
      [chartCandle(300_000)],
      300_001,
    );
  });
  it('stops the stream and prevents late commits on page or context exit', async () => {
    const f = fixture();
    const receive = vi.fn();
    const jump = f.session.setSession(key, receive, 300_001);
    await flushPromises();
    expect(f.adapter.fetchCandles).not.toHaveBeenCalled();
    for (const handler of f.handlers) handler(candleUpdate(900_000));
    expect(receive).not.toHaveBeenCalled();
    const signal = vi.mocked(f.history.stream).mock.calls[0][3];
    await f.session.stop();
    expect(signal.aborted).toBe(true);
    f.done.resolve();
    await jump;
    expect(f.history.append).not.toHaveBeenCalled();
    expect(f.history.finish).not.toHaveBeenCalled();
    expect(f.handlers.size).toBe(0);
  });
  it('recovers from the last historical candle after a reconnect during streaming', async () => {
    const f = fixture();
    const jump = f.session.setSession(key, vi.fn(), 300_001);
    await flushPromises();
    const listeners = vi.mocked(f.adapter.recovery.on).mock.calls;
    const disconnect = listeners
      .filter(([event]) => event === 'disconnected')
      .at(-1)![1];
    const ready = listeners.filter(([event]) => event === 'ready').at(-1)![1];
    disconnect();
    ready();
    f.done.resolve();
    await jump;
    await flushPromises();
    expect(f.adapter.recovery.fetch).toHaveBeenCalledWith(
      expect.objectContaining({
        startMs: 300_000,
      }),
    );
  });
});
