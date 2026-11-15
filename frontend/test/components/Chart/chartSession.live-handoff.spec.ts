import { expect, it, vi } from 'vitest';
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
  const indicators = deferred<void>();
  const recovered = deferred<ReturnType<typeof chartCandle>[]>();
  const history: TradeHistoryAdapter = {
    getRange: () => null,
    prepare: vi.fn(),
    fetchBefore: async () => [chartCandle(300_000)],
    fetchAfter: async () => [chartCandle(300_000)],
    install: vi.fn(),
    initializeIndicators: () => indicators.promise,
    extendIndicators: async () => {},
    historical: vi.fn(),
    resumeLive: vi.fn(),
    loading: vi.fn(),
  };
  base.adapter.tradeHistory = new TradeHistory(history);
  vi.mocked(base.adapter.recovery.fetch).mockReturnValue(recovered.promise);
  return {
    ...base,
    indicators,
    recovered,
    session: createChartSession(base.adapter),
    emit: (time: number) => {
      for (const handler of base.handlers) handler(candleUpdate(time, 9));
    },
  };
}

it('reconciles history and preserves ticks around the live handoff', async () => {
  const f = fixture();
  const jump = f.session.setSession(key, vi.fn(), 300_001);
  await flushPromises();
  f.emit(600_000);
  f.emit(900_000);
  f.indicators.resolve();
  await jump;
  expect(f.adapter.recovery.fetch).toHaveBeenCalledWith(
    expect.objectContaining({ ...key, startMs: 300_000 }),
  );
  expect(f.adapter.recovery.recoverIndicators).toHaveBeenCalled();
  f.emit(1_200_000);
  f.recovered.resolve([chartCandle(300_000), chartCandle(600_000)]);
  await flushPromises();
  expect(f.adapter.recovery.merge).toHaveBeenLastCalledWith(
    [chartCandle(300_000), chartCandle(600_000)],
    [
      candleUpdate(600_000, 9),
      candleUpdate(900_000, 9),
      candleUpdate(1_200_000, 9),
    ],
  );
  await f.session.stop();
});

it('keeps a bounded live tail and rejects a late recovery after cancellation', async () => {
  const f = fixture();
  const jump = f.session.setSession(key, vi.fn(), 300_001);
  await flushPromises();
  for (let i = 2; i <= 8; i++) f.emit(i * 300_000);
  f.indicators.resolve();
  await jump;
  expect(f.adapter.recovery.merge).toHaveBeenCalledWith(
    [],
    [
      candleUpdate(1_800_000, 9),
      candleUpdate(2_100_000, 9),
      candleUpdate(2_400_000, 9),
    ],
  );
  await f.session.stop();
  vi.mocked(f.adapter.recovery.merge).mockClear();
  f.recovered.resolve([chartCandle(600_000)]);
  await flushPromises();
  expect(f.adapter.recovery.merge).not.toHaveBeenCalled();
});

it('keeps Custom historical navigation free of live recovery at the present', async () => {
  const f = fixture();
  const receive = vi.fn();
  const jump = f.session.setSession(
    { ...key, market_id: 7, source_type: 'custom' },
    receive,
    300_001,
  );
  await flushPromises();
  f.emit(600_000);
  f.indicators.resolve();
  await jump;
  expect(f.adapter.subscribeCandles).not.toHaveBeenCalled();
  expect(f.adapter.recovery.on).not.toHaveBeenCalled();
  expect(f.adapter.recovery.fetch).not.toHaveBeenCalled();
  expect(f.adapter.recovery.recoverIndicators).not.toHaveBeenCalled();
  expect(f.adapter.recovery.merge).not.toHaveBeenCalled();
  expect(receive).not.toHaveBeenCalled();
  await f.session.stop();
  expect(f.adapter.unsubscribeCandles).not.toHaveBeenCalled();
});
