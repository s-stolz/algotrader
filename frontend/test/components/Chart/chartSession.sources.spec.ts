import { describe, expect, it, vi } from 'vitest';
import { createChartSession } from '@/components/Chart/chartSession';
import { candleUpdate, createFakeAdapter } from './chartSession.fixtures';

describe('market source chart isolation', () => {
  it('loads custom history without live subscriptions or broker updates', async () => {
    const { adapter, handlers } = createFakeAdapter();
    const session = createChartSession(adapter);
    const receive = vi.fn();
    await session.setSession(
      {
        market_id: 2,
        source_type: 'custom',
        symbol: 'EURUSD',
        exchange: 'CSV',
        timeframe: 'M5',
      },
      receive,
    );
    expect(adapter.fetchCandles).toHaveBeenCalled();
    expect(adapter.requestIndicators).toHaveBeenCalled();
    expect(adapter.subscribeCandles).not.toHaveBeenCalled();
    for (const handler of handlers) handler(candleUpdate(600000));
    expect(receive).not.toHaveBeenCalled();
    await session.stop();
    expect(adapter.unsubscribeCandles).not.toHaveBeenCalled();
  });

  it('rejects another market with the same symbol and accepts the bound market', async () => {
    const { adapter, handlers } = createFakeAdapter();
    const session = createChartSession(adapter);
    const receive = vi.fn();
    await session.setSession(
      {
        market_id: 7,
        source_type: 'broker',
        symbol: 'EURUSD',
        exchange: 'BROKER',
        timeframe: 'M5',
      },
      receive,
    );
    for (const handler of handlers) handler(candleUpdate(600000));
    expect(receive).not.toHaveBeenCalled();
    for (const handler of handlers)
      handler({ ...candleUpdate(600000), market_id: 7 });
    expect(receive).toHaveBeenCalledOnce();
    await session.stop();
  });
});
