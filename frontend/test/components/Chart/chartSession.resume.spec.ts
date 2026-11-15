import { expect, it, vi } from 'vitest';
import { createChartSession } from '@/components/Chart/chartSession';
import {
  chartCandle,
  candleUpdate,
  createFakeAdapter,
} from './chartSession.fixtures';

const key = { symbol: 'EURUSD', exchange: 'FX', timeframe: 'M5' };

async function liveSession() {
  const f = createFakeAdapter();
  const session = createChartSession(f.adapter);
  await session.setSession(key, vi.fn());
  for (const handler of f.handlers) handler(candleUpdate(600_000));
  await session.stop();
  return { ...f, session };
}

it('retains the open candle across repeated same-context resumptions', async () => {
  const f = await liveSession();
  for (let visit = 0; visit < 2; visit++) {
    await f.session.setSession(key, vi.fn());
    expect(f.adapter.renderCandles).toHaveBeenLastCalledWith(
      expect.objectContaining(key),
      [chartCandle(300_000), expect.objectContaining(chartCandle(600_000))],
    );
    await f.session.stop();
  }
});

it('lets closed history supersede the retained live candle', async () => {
  const f = await liveSession();
  vi.mocked(f.adapter.fetchCandles).mockResolvedValue([
    chartCandle(600_000, 1.8),
  ]);
  await f.session.setSession(key, vi.fn());
  expect(f.adapter.renderCandles).toHaveBeenLastCalledWith(
    expect.objectContaining(key),
    [chartCandle(600_000, 1.8)],
  );
  await f.session.stop();
});

it.each([
  { timeframe: 'H1' },
  { symbol: 'GBPUSD' },
  { exchange: 'OTHER' },
  { market_id: 2 },
  { source_type: 'custom' as const },
])('discards the live candle when context changes: %o', async (change) => {
  const f = await liveSession();
  await f.session.setSession({ ...key, ...change }, vi.fn());
  expect(f.adapter.renderCandles).toHaveBeenLastCalledWith(
    expect.objectContaining({ ...key, ...change }),
    [chartCandle(300_000)],
  );
  await f.session.stop();
});
