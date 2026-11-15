import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { flushPromises } from '@vue/test-utils';
import { fetchCandles } from '@/api/candleClient';
import { createChartSession } from '@/components/Chart/chartSession';
import { createChartSessionAdapter } from '@/components/Chart/chartSessionAdapter';
import { useCandlesticksStore } from '@/stores/candlesticksStore';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { wsService } from '@/utils/websocketService';
import { chartCandle, candleUpdate, deferred } from './chartSession.fixtures';

vi.mock('@/api/candleClient', () => ({ fetchCandles: vi.fn() }));
const handlers = new Map<string, Set<(message?: unknown) => void>>();
vi.mock('@/utils/websocketService', () => ({
  wsService: {
    send: vi.fn(async () => {}),
    on: vi.fn((event, handler) => {
      if (!handlers.has(event)) handlers.set(event, new Set());
      handlers.get(event)!.add(handler);
    }),
    off: vi.fn((event, handler) => handlers.get(event)?.delete(handler)),
  },
}));
const key = { symbol: 'EURUSD', exchange: 'FX', timeframe: 'M5' };
const emit = (event: string, message?: unknown) => {
  for (const handler of handlers.get(event) ?? []) handler(message);
};
async function setup() {
  const candles = useCandlesticksStore();
  const render = vi.fn();
  const session = createChartSession(
    createChartSessionAdapter({
      candlesticksStore: candles,
      indicatorsStore: useIndicatorsStore(),
      currentChartSessionKey: () => key,
      renderCandlesticks: render,
      shouldScrollToRealTime: () => false,
    }),
  );
  await session.setSession(key, (message) => candles.updateCandle(message));
  return { candles, session, render };
}
beforeEach(() => {
  setActivePinia(createPinia());
  handlers.clear();
  vi.mocked(fetchCandles)
    .mockReset()
    .mockResolvedValue([chartCandle(300_000)]);
  vi.spyOn(Date, 'now').mockReturnValue(1_500_000);
});
afterEach(() => vi.restoreAllMocks());

it('merges the inclusive gap with older history and fresh live values', async () => {
  const { candles, session, render } = await setup();
  candles.prepend([chartCandle(0)]);
  emit('ready');
  expect(fetchCandles).toHaveBeenCalledTimes(1);
  emit('disconnected');
  const pending = deferred<ReturnType<typeof chartCandle>[]>();
  vi.mocked(fetchCandles).mockReturnValueOnce(pending.promise);
  emit('ready');
  emit('candleUpdate', { ...candleUpdate(1_200_000, 9), high: 10 });
  expect(candles.data.at(-1)?.close).toBe(9);
  pending.resolve([
    chartCandle(300_000, 3),
    chartCandle(600_000),
    chartCandle(900_000),
    chartCandle(1_200_000, 4),
  ]);
  await flushPromises();
  expect(fetchCandles).toHaveBeenLastCalledWith('EURUSD', 'M5', {
    startMs: 300_000,
    endMs: 1_500_000,
    exchange: 'FX',
  });
  expect(candles.data.map((c) => c.timestamp_ms)).toEqual([
    0, 300_000, 600_000, 900_000, 1_200_000,
  ]);
  expect(candles.data[1].close).toBe(3);
  expect(candles.data.at(-1)?.close).toBe(9);
  expect(render).toHaveBeenLastCalledWith(candles.data);
  await session.stop();
  expect([...handlers.values()].every((set) => set.size === 0)).toBe(true);
});

it('retains the failed anchor without timed retries', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
  const { session } = await setup();
  emit('disconnected');
  vi.mocked(fetchCandles).mockRejectedValueOnce(new Error('offline'));
  emit('ready');
  await flushPromises();
  expect(fetchCandles).toHaveBeenCalledTimes(2);
  emit('candleUpdate', candleUpdate(900_000));
  emit('disconnected');
  emit('ready');
  await flushPromises();
  expect(fetchCandles).toHaveBeenCalledTimes(3);
  expect(fetchCandles).toHaveBeenLastCalledWith(
    'EURUSD',
    'M5',
    expect.objectContaining({ startMs: 300_000 }),
  );
  await session.stop();
});

it('ignores superseded recovery and keeps the earliest anchor', async () => {
  const { candles, session } = await setup();
  const pending = deferred<ReturnType<typeof chartCandle>[]>();
  emit('disconnected');
  vi.mocked(fetchCandles).mockReturnValueOnce(pending.promise);
  emit('ready');
  emit('candleUpdate', candleUpdate(900_000));
  emit('disconnected');
  vi.mocked(fetchCandles).mockResolvedValueOnce([chartCandle(300_000, 8)]);
  emit('ready');
  await flushPromises();
  pending.resolve([chartCandle(300_000, 2)]);
  await flushPromises();
  expect(candles.data[0].close).toBe(8);
  expect(fetchCandles).toHaveBeenLastCalledWith(
    'EURUSD',
    'M5',
    expect.objectContaining({ startMs: 300_000 }),
  );
  await session.stop();
});

it.each(['stop', 'switch'] as const)(
  'ignores old recovery on session %s',
  async (action) => {
    const { candles, session } = await setup();
    const pending = deferred<ReturnType<typeof chartCandle>[]>();
    emit('disconnected');
    vi.mocked(fetchCandles).mockReturnValueOnce(pending.promise);
    emit('ready');
    if (action === 'stop') await session.stop();
    else
      await session.setSession({ ...key, timeframe: 'H1' }, (message) =>
        candles.updateCandle(message),
      );
    pending.resolve([chartCandle(600_000, 99)]);
    await flushPromises();
    expect(candles.data.some((c) => c.close === 99)).toBe(false);
    await session.stop();
  },
);

it('recovers once when reconnection happens during initial history loading', async () => {
  const pending = deferred<ReturnType<typeof chartCandle>[]>();
  vi.mocked(fetchCandles).mockReturnValueOnce(pending.promise);
  const initial = setup();
  await flushPromises();
  emit('disconnected');
  emit('ready');
  pending.resolve([chartCandle(300_000)]);
  const { session } = await initial;
  await flushPromises();
  expect(fetchCandles).toHaveBeenCalledTimes(2);
  expect(wsService.on).toHaveBeenCalledWith('ready', expect.any(Function));
  await session.stop();
});
