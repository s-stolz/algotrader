import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { useCandlesticksStore } from '@/stores/candlesticksStore';
import { wsService } from '@/utils/websocketService';
import { createTradeHistoryAdapter } from '@/components/Chart/trade-navigation/tradeHistoryAdapter';
import type { ChartInfrastructure } from '@/utils/chart';
import { seedBrokerMarket } from '../fixtures/brokerMarket';

vi.mock('@/utils/websocketService', () => ({
  wsService: { send: vi.fn(async () => {}) },
}));
beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});
const key = {
  market_id: 7,
  source_type: 'broker' as const,
  symbol: 'BTCUSD',
  timeframe: 'M1',
  exchange: 'IC TRADING',
};
function fixture() {
  seedBrokerMarket({
    symbol_id: key.market_id,
    symbol: key.symbol,
    exchange: key.exchange,
  });
  const indicators = useIndicatorsStore();
  const id = indicators.addIndicator(
    {
      id: 1,
      indicator_id: 'sma',
      name: 'SMA',
      overlay: true,
      inputs: [],
      outputs: { sma: { type: 'line' } },
      parameters: {},
    },
    [],
    1,
  );
  const adapter = createTradeHistoryAdapter({
    candles: useCandlesticksStore(),
    indicators,
    infrastructure: {
      chartManager: { chart: null },
    } as unknown as ChartInfrastructure,
    render: vi.fn(),
    reset: vi.fn(),
    initializeIndicators: async () => {},
    loading: vi.fn(),
  });
  return { indicators, id, adapter };
}

it('does not start a live calculation whose updates would be discarded', async () => {
  const { indicators, id } = fixture();
  indicators.historicalMode = true;
  await indicators.subscribeIndicatorLive(id, {
    ...key,
    indicatorId: 1,
    parameters: {},
  });
  expect(wsService.send).not.toHaveBeenCalled();
  expect(indicators.liveSubscriptions.size).toBe(0);
});

it('pauses existing live calculations and resumes them only at the present', async () => {
  const { indicators, id, adapter } = fixture();
  await indicators.subscribeIndicatorLive(id, {
    ...key,
    indicatorId: 1,
    parameters: {},
  });
  vi.mocked(wsService.send).mockClear();
  adapter.historical(true);
  await flushPromises();
  expect(wsService.send).toHaveBeenCalledWith(
    'unsubscribeIndicator',
    expect.any(Object),
  );
  expect(indicators.liveSubscriptions.size).toBe(0);
  vi.mocked(wsService.send).mockClear();
  adapter.historical(false);
  expect(wsService.send).not.toHaveBeenCalled();
  adapter.resumeLive(key);
  await flushPromises();
  expect(wsService.send).toHaveBeenCalledWith(
    'subscribeIndicator',
    expect.objectContaining({
      market_id: key.market_id,
      symbol: key.symbol,
      timeframe: key.timeframe,
      exchange: key.exchange,
      clientIndicatorId: id,
    }),
  );
});

it.each([
  { ...key, source_type: 'custom' as const, exchange: null },
  { ...key, market_id: 8 },
])(
  'does not resume a different source or Market identity: %j',
  async (resumeKey) => {
    const { indicators, adapter } = fixture();
    adapter.historical(true);
    await flushPromises();
    adapter.historical(false);
    adapter.resumeLive(resumeKey);
    await flushPromises();
    expect(wsService.send).not.toHaveBeenCalled();
    expect(indicators.liveSubscriptions.size).toBe(0);
  },
);
