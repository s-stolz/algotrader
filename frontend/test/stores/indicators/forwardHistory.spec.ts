import { seedBrokerMarket } from '../../fixtures/brokerMarket';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { requestIndicator } from '@/api/indicatorClient';
import { wsService } from '@/utils/websocketService';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { extendIndicatorHistory } from '@/stores/indicators/forwardHistory';
import type { IndicatorInfo, IndicatorResponse } from '@/types/contracts';
import {
  chartCandle,
  deferred,
} from '../../components/Chart/chartSession.fixtures';

vi.mock('@/api/indicatorClient', () => ({ requestIndicator: vi.fn() }));
vi.mock('@/utils/websocketService', () => ({ wsService: { send: vi.fn() } }));
const info: IndicatorInfo = {
  id: 1,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: true,
  inputs: [],
  outputs: { sma: { type: 'line' } },
  parameters: {},
};
const response: IndicatorResponse = {
  data: {
    indicator_info: info,
    indicator_data: [{ timestamp_ms: 600_000, sma: 2 }],
  },
};
const key = { symbol: 'EURUSD', exchange: 'FX', timeframe: 'M5' };
beforeEach(() => {
  setActivePinia(createPinia());
  seedBrokerMarket();
  vi.resetAllMocks();
});

describe('forward indicator history', () => {
  it('merges bounded forward batches without losing earlier history', async () => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, [{ timestamp_ms: 300_000, sma: 1 }], 1);
    vi.mocked(requestIndicator).mockResolvedValue(response);
    const signal = new AbortController().signal;
    await extendIndicatorHistory(store, key, [chartCandle(600_000)], signal);
    expect(requestIndicator).toHaveBeenCalledWith(
      1,
      {
        ...key,
        startMs: 600_000,
        endMs: 900_000,
      },
      { parameters: {} },
      signal,
    );
    expect(store.getById(id)?.data).toEqual([
      { timestamp_ms: 300_000, sma: 1 },
      { timestamp_ms: 600_000, sma: 2 },
    ]);
  });
  it('rejects late results after cancellation or parameter generation changes', async () => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, [], 1);
    const pending = deferred<IndicatorResponse>();
    vi.mocked(requestIndicator).mockReturnValue(pending.promise);
    const controller = new AbortController();
    const work = extendIndicatorHistory(
      store,
      key,
      [chartCandle(600_000)],
      controller.signal,
    );
    await Promise.resolve();
    controller.abort();
    pending.resolve(response);
    await work;
    expect(store.getById(id)?.data).toEqual([]);
  });
  it('ignores live values while historical and accepts them after returning live', () => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, [], 1);
    void store.subscribeIndicatorLive(id, {
      ...key,
      indicatorId: 1,
      parameters: {},
    });
    store.historicalMode = true;
    expect(
      store.handleLiveUpdate({
        type: 'indicatorUpdate',
        market_id: 1,
        clientIndicatorId: id,
        timestamp_ms: 600_000,
        values: { sma: 3 },
      }),
    ).toBeNull();
    expect(store.getById(id)?.data).toEqual([]);
    store.updateIndicatorData(id, [{ timestamp_ms: 600_000, sma: 2 }]);
    store.historicalMode = false;
    store.handleLiveUpdate({
      type: 'indicatorUpdate',
      market_id: 1,
      clientIndicatorId: id,
      timestamp_ms: 600_000,
      values: { sma: 3 },
    });
    expect(store.getById(id)?.data).toEqual([
      { timestamp_ms: 600_000, sma: 3 },
    ]);
  });
  it('does not erase replacement live subscriptions during old-session cleanup', async () => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, [], 1);
    await store.subscribeIndicatorLive(id, {
      ...key,
      indicatorId: 1,
      parameters: {},
    });
    const pending = deferred<void>();
    vi.mocked(wsService.send).mockReturnValueOnce(pending.promise);
    const cleanup = store.unsubscribeAllLive();
    await store.subscribeIndicatorLive(id, {
      ...key,
      timeframe: 'H1',
      indicatorId: 1,
      parameters: {},
    });
    pending.resolve();
    await cleanup;
    expect(store.liveSubscriptions.get(id)?.timeframe).toBe('H1');
  });
});
