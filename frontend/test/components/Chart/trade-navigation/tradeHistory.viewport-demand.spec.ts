import { expect, it, vi } from 'vitest';
import {
  TradeHistory,
  type TradeHistoryAdapter,
} from '@/components/Chart/trade-navigation/tradeHistory';
import { chartCandle, deferred } from '../chartSession.fixtures';

const key = { symbol: 'EURUSD', exchange: 'FX', timeframe: 'M5' };
const batch = (start: number) =>
  Array.from({ length: 500 }, (_, i) => chartCandle((start + i) * 300_000));
const range = (barsBefore: number, barsAfter: number) => ({
  barsBefore,
  barsAfter,
  nowMs: 1000,
});

it.each([
  { direction: 'older', notify: true },
  { direction: 'newer', notify: true },
  { direction: 'older', notify: false },
  { direction: 'newer', notify: false },
])(
  'fills a wide viewport without another gesture: %j',
  async ({ direction, notify }) => {
    let before = 0;
    let after = 460;
    const adapter: TradeHistoryAdapter = {
      getRange: vi.fn(() => range(before, after)),
      prepare: vi.fn(),
      historical: vi.fn(),
      resumeLive: vi.fn(),
      loading: vi.fn(),
      fetchBefore: vi.fn(async (_key, end) => batch(end / 300_000 - 500)),
      fetchAfter: vi.fn(async (_key, start) => batch(start / 300_000)),
      install: vi.fn((_candles, target) => {
        if (target !== null) return;
        if (direction === 'older') before += 500;
        else after += 500;
        if (notify) void history.requestPage(range(before, after));
      }),
      initializeIndicators: vi.fn(async () => {}),
      extendIndicators: vi.fn(async () => {}),
    };
    const history = new TradeHistory(adapter);
    await history.load(key, 3_000_001);
    await history.requestPage(range(before, after));
    if (direction === 'older') before = -900;
    else after = -900;
    await history.requestPage(range(before, after));
    expect(adapter.install).toHaveBeenCalledTimes(3);
    expect(direction === 'older' ? before : after).toBe(100);
    expect(adapter.extendIndicators).toHaveBeenCalledTimes(2);
  },
);

it('retains a viewport request arriving while initial indicators are loading', async () => {
  const pending = deferred<void>();
  let after = 460;
  const adapter: TradeHistoryAdapter = {
    getRange: vi.fn(() => null),
    prepare: vi.fn(),
    historical: vi.fn(),
    resumeLive: vi.fn(),
    loading: vi.fn(),
    fetchBefore: vi.fn(async () => [chartCandle(3_000_000)]),
    fetchAfter: vi.fn(async (_key, start) => batch(start / 300_000)),
    install: vi.fn((_candles, target) => {
      if (target !== null) return;
      after += 500;
      void history.requestPage(range(0, after));
    }),
    initializeIndicators: vi.fn(() => pending.promise),
    extendIndicators: vi.fn(async () => {}),
  };
  const history = new TradeHistory(adapter);
  const loading = history.load(key, 3_000_001);
  await vi.waitFor(() =>
    expect(adapter.initializeIndicators).toHaveBeenCalledOnce(),
  );
  await history.requestPage(range(0, after));
  after = -50;
  await history.requestPage(range(0, after));
  pending.resolve();
  await loading;
  expect(adapter.fetchAfter).toHaveBeenCalledTimes(2);
});

it('stops requesting pages when the user moves away during a pending fetch', async () => {
  const pending = deferred<ReturnType<typeof batch>>();
  const adapter: TradeHistoryAdapter = {
    getRange: vi.fn(() => null),
    prepare: vi.fn(),
    historical: vi.fn(),
    resumeLive: vi.fn(),
    loading: vi.fn(),
    fetchBefore: vi.fn(async () => [chartCandle(3_000_000)]),
    fetchAfter: vi.fn(async (_key, start) => batch(start / 300_000)),
    install: vi.fn(),
    initializeIndicators: vi.fn(async () => {}),
    extendIndicators: vi.fn(async () => {}),
  };
  const history = new TradeHistory(adapter);
  await history.load(key, 3_000_001);
  await history.requestPage(range(0, 460));
  vi.mocked(adapter.fetchAfter).mockReturnValueOnce(pending.promise);
  const page = history.requestPage(range(900, -900));
  await history.requestPage(range(200, 200));
  pending.resolve(batch(510));
  await page;
  expect(adapter.fetchAfter).toHaveBeenCalledTimes(2);
  expect(adapter.fetchBefore).toHaveBeenCalledOnce();
});
