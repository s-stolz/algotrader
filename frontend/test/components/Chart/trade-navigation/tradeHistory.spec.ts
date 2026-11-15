import { describe, expect, it, vi } from 'vitest';
import {
  TradeHistory,
  type TradeHistoryAdapter,
} from '@/components/Chart/trade-navigation/tradeHistory';
import { chartCandle, candleUpdate, deferred } from '../chartSession.fixtures';
const key = { symbol: 'EURUSD', exchange: 'FX', timeframe: 'M5' };
const batch = (start: number, length = 500) =>
  Array.from({ length }, (_, i) => chartCandle((start + i) * 300_000));
function fixture() {
  const adapter: TradeHistoryAdapter = {
    prepare: vi.fn(),
    historical: vi.fn(),
    loading: vi.fn(),
    fetchBefore: vi.fn(async () => batch(0, 11)),
    fetchAfter: vi.fn(async () => batch(10)),
    install: vi.fn(),
    initializeIndicators: vi.fn(async () => {}),
    extendIndicators: vi.fn(async () => {}),
  };
  return { adapter, history: new TradeHistory(adapter) };
}
const range = (barsBefore: number, barsAfter: number) => ({
  barsBefore,
  barsAfter,
  nowMs: 1000,
});

describe('bounded trade history', () => {
  it('loads ten predecessors and 500 forward bars without fetching through today', async () => {
    const { adapter, history } = fixture();
    expect(await history.load(key, 3_000_001)).toBe(true);
    expect(adapter.fetchBefore).toHaveBeenCalledWith(
      key,
      3_000_002,
      11,
      expect.any(AbortSignal),
    );
    expect(adapter.fetchAfter).toHaveBeenCalledOnce();
    expect(adapter.install).toHaveBeenCalledWith(batch(0, 510), 3_000_001);
    expect(history.receive(candleUpdate(9_000_000_000))).toBe(true);
    expect(adapter.loading).toHaveBeenLastCalledWith(false);
    await history.requestPage(range(0, 460));
    await history.requestPage(range(0, 460));
    expect(adapter.fetchAfter).toHaveBeenCalledOnce();
    expect(adapter.fetchBefore).toHaveBeenCalledOnce();
  });
  it('loads older or newer pages only toward the scrolled edge', async () => {
    const { adapter, history } = fixture();
    await history.load(key, 3_000_001);
    await history.requestPage(range(0, 460));
    vi.mocked(adapter.fetchBefore).mockResolvedValue(batch(-500));
    await history.requestPage(range(-1, 461));
    expect(adapter.fetchBefore).toHaveBeenLastCalledWith(
      key,
      0,
      500,
      expect.any(AbortSignal),
    );
    expect(adapter.extendIndicators).toHaveBeenCalledWith(
      key,
      batch(-500),
      expect.any(AbortSignal),
    );
    vi.mocked(adapter.fetchAfter).mockResolvedValue(batch(510));
    await history.requestPage(range(900, 50));
    expect(adapter.fetchAfter).toHaveBeenLastCalledWith(
      key,
      510 * 300_000,
      expect.any(AbortSignal),
    );
    expect(adapter.install).toHaveBeenLastCalledWith(batch(510), null);
  });
  it('deduplicates pending pages and invalidates them on cancellation', async () => {
    const { adapter, history } = fixture();
    await history.load(key, 3_000_001);
    await history.requestPage(range(0, 460));
    const pending = deferred<ReturnType<typeof batch>>();
    vi.mocked(adapter.fetchAfter).mockReturnValue(pending.promise);
    const page = history.requestPage(range(410, 50));
    await history.requestPage(range(420, 40));
    expect(adapter.fetchAfter).toHaveBeenCalledTimes(2);
    history.cancel();
    pending.resolve(batch(510));
    await page;
    expect(adapter.install).toHaveBeenCalledOnce();
    expect(adapter.historical).toHaveBeenLastCalledWith(false);
  });
  it('rejects replaced initial reads', async () => {
    const { adapter, history } = fixture();
    const pending = deferred<ReturnType<typeof batch>>();
    vi.mocked(adapter.fetchBefore).mockReturnValueOnce(pending.promise);
    const old = history.load(key, 3_000_001);
    await history.load(key, 3_000_002);
    pending.resolve(batch(0, 11));
    expect(await old).toBe(false);
    expect(adapter.install).toHaveBeenCalledOnce();
  });
  it('resumes live updates after a short forward page reaches the present', async () => {
    const { adapter, history } = fixture();
    await history.load(key, 3_000_001);
    await history.requestPage(range(0, 460));
    vi.mocked(adapter.fetchAfter).mockResolvedValue(batch(510, 2));
    await history.requestPage(range(410, 50));
    expect(history.blocksOlderHistory).toBe(false);
    expect(history.receive(candleUpdate(512 * 300_000))).toBe(false);
    expect(adapter.historical).toHaveBeenLastCalledWith(false);
  });
  it('keeps failed history isolated and retries on the next movement', async () => {
    const { adapter, history } = fixture();
    await history.load(key, 3_000_001);
    await history.requestPage(range(0, 460));
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(adapter.fetchAfter).mockRejectedValueOnce(new Error('offline'));
    await history.requestPage(range(410, 50));
    expect(history.blocksOlderHistory).toBe(true);
    vi.mocked(adapter.fetchAfter).mockResolvedValue(batch(510));
    await history.requestPage(range(420, 40));
    expect(adapter.install).toHaveBeenLastCalledWith(batch(510), null);
    log.mockRestore();
  });
});
