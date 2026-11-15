import { describe, expect, it, vi } from 'vitest';
import {
  TradeHistory,
  type TradeHistoryAdapter,
} from '@/components/Chart/trade-navigation/tradeHistory';
import { chartCandle, candleUpdate, deferred } from '../chartSession.fixtures';
import type { ChartCandle } from '@/types/contracts';

const key = { symbol: 'EURUSD', exchange: 'FX', timeframe: 'M5' };
function fixture() {
  const end = deferred<void>();
  let deliver!: (candles: ChartCandle[]) => Promise<void>;
  const adapter: TradeHistoryAdapter = {
    prepare: vi.fn(),
    fetchBefore: vi.fn(async () =>
      Array.from({ length: 11 }, (_, i) => chartCandle(i * 300_000)),
    ),
    stream: vi.fn(async (_key, _start, _end, _signal, onBatch) => {
      deliver = onBatch;
      await end.promise;
    }),
    append: vi.fn(),
    initializeIndicators: vi.fn(async () => {}),
    extendIndicators: vi.fn(async () => {}),
    finish: vi.fn(),
    cancel: vi.fn(),
    loading: vi.fn(),
  };
  return {
    adapter,
    end,
    deliver: (candles: ChartCandle[]) => deliver(candles),
    history: new TradeHistory(adapter),
  };
}
const future = (start = 10, length = 500) =>
  Array.from({ length }, (_, i) => chartCandle((start + i) * 300_000));

describe('trade history navigation', () => {
  it('renders early and extends history without jumping again', async () => {
    const f = fixture();
    const work = f.history.load(key, 3_000_001);
    await Promise.resolve();
    await f.deliver(future());
    expect(f.adapter.append).toHaveBeenCalledWith(expect.any(Array), 3_000_001);
    expect(vi.mocked(f.adapter.append).mock.calls[0][0]).toHaveLength(510);
    expect(f.adapter.finish).not.toHaveBeenCalled();
    await f.deliver(future(510, 510));
    expect(f.adapter.append).toHaveBeenLastCalledWith(future(510, 510), null);
    f.end.resolve();
    expect(await work).toBe(true);
    expect(f.adapter.loading).toHaveBeenLastCalledWith(false);
  });

  it('holds live candles until candle and indicator history both complete', async () => {
    const f = fixture();
    const indicators = deferred<void>();
    vi.mocked(f.adapter.extendIndicators).mockReturnValue(indicators.promise);
    const work = f.history.load(key, 3_000_001);
    await Promise.resolve();
    await f.deliver(future());
    expect(f.history.receive(candleUpdate(1_000_000_000, 2))).toBe(true);
    f.history.receive(candleUpdate(1_000_000_000, 3));
    f.end.resolve();
    await Promise.resolve();
    expect(f.adapter.finish).not.toHaveBeenCalled();
    indicators.resolve();
    await work;
    expect(f.adapter.finish).toHaveBeenCalledWith([
      candleUpdate(1_000_000_000, 3),
    ]);
    expect(f.history.receive(candleUpdate(1_000_300_000))).toBe(false);
  });

  it('renders short history near the present on completion', async () => {
    const f = fixture();
    const work = f.history.load(key, 3_000_001);
    await Promise.resolve();
    await f.deliver(future(10, 4));
    f.end.resolve();
    await work;
    expect(vi.mocked(f.adapter.append).mock.calls[0][0]).toHaveLength(14);
  });

  it('aborts stale streams when another destination replaces them', async () => {
    const f = fixture();
    const first = f.history.load(key, 3_000_001);
    await Promise.resolve();
    const firstDeliver = f.deliver;
    const oldSignal = vi.mocked(f.adapter.stream).mock.calls[0][3];
    const replacement = f.history.load(key, 6_000_000);
    expect(oldSignal.aborted).toBe(true);
    await expect(firstDeliver(future())).rejects.toThrow();
    f.history.cancel();
    f.end.resolve();
    await Promise.all([first, replacement]);
    expect(f.adapter.append).not.toHaveBeenCalled();
    expect(f.adapter.finish).not.toHaveBeenCalled();
  });

  it('keeps a failed prefix historical instead of attaching live data across a gap', async () => {
    const f = fixture();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(f.adapter.stream).mockRejectedValueOnce(
      new Error('disconnected'),
    );
    expect(await f.history.load(key, 3_000_001)).toBe(false);
    expect(f.history.receive(candleUpdate(1_000_000_000))).toBe(true);
    expect(f.adapter.finish).not.toHaveBeenCalled();
    expect(f.adapter.cancel).toHaveBeenLastCalledWith(true);
    vi.restoreAllMocks();
  });
  it('streams a missing old prefix before installing newer aggregate history', async () => {
    const f = fixture();
    vi.mocked(f.adapter.stream)
      .mockImplementationOnce(async (_key, _start, _end, _signal, onBatch) => {
        await onBatch(future(510, 510));
      })
      .mockImplementationOnce(async (_key, _start, _end, _signal, onBatch) => {
        await onBatch(future());
      });
    expect(await f.history.load(key, 3_000_001)).toBe(true);
    expect(f.adapter.stream).toHaveBeenCalledTimes(2);
    expect(vi.mocked(f.adapter.stream).mock.calls[1].slice(1, 3)).toEqual([
      3_000_000,
      510 * 300_000,
    ]);
    const initial = vi.mocked(f.adapter.append).mock.calls[0][0];
    expect(initial).toHaveLength(510);
    expect(initial[10].timestamp_ms).toBe(3_000_000);
    expect(f.adapter.append).toHaveBeenLastCalledWith(future(510, 510), null);
  });
});
