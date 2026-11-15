import { seedBrokerMarket } from '../fixtures/brokerMarket';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, expect, it, vi } from 'vitest';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { IndicatorInfo } from '@/types/contracts';

vi.mock('@/api/indicatorClient', () => ({ requestIndicator: vi.fn() }));
vi.mock('@/utils/websocketService', () => ({ wsService: { send: vi.fn() } }));

const info: IndicatorInfo = {
  id: 5,
  indicator_id: 'currency_strength',
  name: 'Currency Strength',
  overlay: false,
  supports_live: true,
  inputs: [
    'EURUSD',
    'USDJPY',
    'USDCHF',
    'GBPUSD',
    'AUDUSD',
    'USDCAD',
    'NZDUSD',
  ],
  outputs: { EUR: { type: 'line' } },
  parameters: {},
};

beforeEach(() => {
  setActivePinia(createPinia());
  seedBrokerMarket();
});

it('silently repairs earlier points without rewinding the live tail', () => {
  const store = useIndicatorsStore();
  const id = store.addIndicator(
    info,
    [
      { timestamp_ms: 1000, EUR: 1 },
      { timestamp_ms: 3000, EUR: 3 },
    ],
    5,
  );
  const version = store.getById(id)!.dataVersion;
  void store.subscribeIndicatorLive(id, {
    symbol: 'EURUSD',
    exchange: 'FX',
    timeframe: 'M1',
    indicatorId: 5,
    parameters: {},
  });
  const message = {
    type: 'indicatorUpdate' as const,
    market_id: 1,
    clientIndicatorId: id,
    timestamp_ms: 1000,
    values: { EUR: 1.5 },
    replay: true,
  };
  expect(store.handleLiveUpdate(message)).toBeNull();
  store.handleLiveUpdate({
    ...message,
    timestamp_ms: 2000,
    values: { EUR: 2 },
  });
  expect(store.getById(id)!.data).toEqual([
    { timestamp_ms: 1000, EUR: 1.5 },
    { timestamp_ms: 2000, EUR: 2 },
    { timestamp_ms: 3000, EUR: 3 },
  ]);
  expect(store.getById(id)!.lastLivePoint?.timestamp_ms).toBe(3000);
  expect(store.getById(id)!.dataVersion).toBeGreaterThan(version);
  expect(store.handleLiveUpdate({ ...message, replay: false })).toBeNull();
  expect(
    store.handleLiveUpdate({ ...message, timestamp_ms: 4000, replay: false }),
  ).toEqual({ timestamp_ms: 4000, EUR: 1.5 });
});

it('subscribes currency strength through the existing live flow', async () => {
  const { wsService } = await import('@/utils/websocketService');
  const store = useIndicatorsStore();
  const id = store.addIndicator(info, [], 5);
  await store.subscribeIndicatorLive(id, {
    symbol: 'EURUSD',
    timeframe: 'M1',
    indicatorId: 5,
    exchange: null,
    parameters: {},
  });
  expect(wsService.send).toHaveBeenCalledWith(
    'subscribeIndicator',
    expect.objectContaining({ indicatorId: 5, clientIndicatorId: id }),
  );
});

it('limits replay to loaded history without trimming a newer live tail', () => {
  const store = useIndicatorsStore();
  store.configureHistoryCoverage({
    getLoadedCandleRange: () => ({
      oldestTimestampMs: 1000,
      newestTimestampMs: 2000,
      exclusiveEndMs: 3000,
    }),
  });
  const id = store.addIndicator(
    info,
    [
      { timestamp_ms: 1000, EUR: 1 },
      { timestamp_ms: 2000, EUR: 2 },
    ],
    5,
  );
  void store.subscribeIndicatorLive(id, {
    symbol: 'EURUSD',
    exchange: 'FX',
    timeframe: 'M1',
    indicatorId: 5,
    parameters: {},
  });
  const message = {
    type: 'indicatorUpdate' as const,
    market_id: 1,
    clientIndicatorId: id,
    timestamp_ms: 3000,
    values: { EUR: 3 },
  };
  store.handleLiveUpdate(message);
  store.handleLiveUpdate({ ...message, timestamp_ms: 1000, replay: true });
  store.handleLiveUpdate({ ...message, timestamp_ms: 500, replay: true });
  expect(store.getById(id)!.data).toEqual([
    { timestamp_ms: 1000, EUR: 3 },
    { timestamp_ms: 2000, EUR: 2 },
    { timestamp_ms: 3000, EUR: 3 },
  ]);
  expect(store.getById(id)!.lastLivePoint?.timestamp_ms).toBe(3000);
});
