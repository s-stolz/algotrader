import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, expect, it, vi } from 'vitest';
import { requestIndicator } from '@/api/indicatorClient';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { useMarketsStore } from '@/stores/marketsStore';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { wsService } from '@/utils/websocketService';
import { seedBrokerMarket } from '../fixtures/brokerMarket';

vi.mock('@/api/indicatorClient', () => ({ requestIndicator: vi.fn() }));
vi.mock('@/utils/websocketService', () => ({ wsService: { send: vi.fn() } }));
beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  vi.mocked(requestIndicator).mockResolvedValue({
    data: {
      indicator_info: {
        id: 1,
        indicator_id: 'sma',
        name: 'SMA',
        overlay: true,
        supports_live: true,
        inputs: [],
        outputs: { sma: { type: 'line' } },
        parameters: {},
      },
      indicator_data: [{ timestamp_ms: 60000, sma: 1 }],
    },
  });
});

it('keeps Custom indicator history without acquiring or accepting broker updates', async () => {
  const broker = seedBrokerMarket();
  const custom = {
    ...broker,
    symbol_id: 2,
    exchange: 'CSV',
    source_type: 'custom' as const,
  };
  useMarketsStore().all.push(custom);
  useCurrentMarketStore().setMarket(custom);
  const store = useIndicatorsStore();
  const id = await store.requestIndicator(null, 1, {
    symbol: 'EURUSD',
    exchange: 'CSV',
    timeframe: 'M1',
  });
  expect(requestIndicator).toHaveBeenCalled();
  expect(wsService.send).not.toHaveBeenCalled();
  expect(store.getById(id!)?.data).toEqual([{ timestamp_ms: 60000, sma: 1 }]);
  expect(
    store.handleLiveUpdate({
      type: 'indicatorUpdate',
      market_id: 1,
      clientIndicatorId: id!,
      timestamp_ms: 120000,
      values: { sma: 9 },
    }),
  ).toBeNull();
  expect(store.getById(id!)?.data).toEqual([{ timestamp_ms: 60000, sma: 1 }]);
});

it('requires the subscribed market and stops accepting messages after switching to Custom', async () => {
  const broker = seedBrokerMarket();
  const store = useIndicatorsStore();
  const id = await store.requestIndicator(null, 1, {
    symbol: 'EURUSD',
    exchange: 'FX',
    timeframe: 'M1',
  });
  const message = {
    type: 'indicatorUpdate' as const,
    market_id: 1,
    clientIndicatorId: id!,
    timestamp_ms: 120000,
    values: { sma: 9 },
  };
  expect(store.handleLiveUpdate({ ...message, market_id: 2 })).toBeNull();
  expect(store.handleLiveUpdate(message)).toEqual({
    timestamp_ms: 120000,
    sma: 9,
  });
  useCurrentMarketStore().setMarket({
    ...broker,
    symbol_id: 2,
    exchange: 'CSV',
    source_type: 'custom',
  });
  expect(
    store.handleLiveUpdate({ ...message, timestamp_ms: 180000 }),
  ).toBeNull();
});
