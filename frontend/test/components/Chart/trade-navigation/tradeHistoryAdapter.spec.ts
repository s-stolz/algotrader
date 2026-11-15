import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, expect, it, vi } from 'vitest';
import { createTradeHistoryAdapter } from '@/components/Chart/trade-navigation/tradeHistoryAdapter';
import { useCandlesticksStore } from '@/stores/candlesticksStore';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { fetchCandles } from '@/api/candleClient';
import type { ChartInfrastructure } from '@/utils/chart';
import { chartCandle } from '../chartSession.fixtures';
vi.mock('@/api/candleClient', () => ({ fetchCandles: vi.fn() }));
beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});
function fixture(width = 120) {
  const candles = useCandlesticksStore();
  const indicators = useIndicatorsStore();
  const scale = {
    getVisibleLogicalRange: () => ({ from: 20, to: 20 + width }),
    setVisibleLogicalRange: vi.fn(),
    applyOptions: vi.fn(),
  };
  const adapter = createTradeHistoryAdapter({
    candles,
    indicators,
    infrastructure: {
      chartManager: { chart: { timeScale: () => scale } },
    } as unknown as ChartInfrastructure,
    render: vi.fn(),
    reset: vi.fn(),
    initializeIndicators: vi.fn(async () => {}),
    loading: vi.fn(),
  });
  return { adapter, scale, candles, indicators };
}
it.each([120, 5])(
  'preserves %s-bar zoom and positions the event once',
  (width) => {
    const { adapter, scale } = fixture(width);
    adapter.historical(true);
    adapter.prepare();
    adapter.install(
      Array.from({ length: 11 }, (_, i) => chartCandle(i * 300_000)),
      3_000_001,
    );
    expect(scale.setVisibleLogicalRange).toHaveBeenLastCalledWith({
      from: width < 11 ? 11 - width : 0,
      to: width < 11 ? 11 : width,
    });
    adapter.install([chartCandle(3_300_000)], null);
    expect(scale.setVisibleLogicalRange).toHaveBeenCalledOnce();
    expect(scale.applyOptions).toHaveBeenCalledWith({
      shiftVisibleRangeOnNewBar: false,
    });
    adapter.historical(false);
    expect(scale.applyOptions).toHaveBeenLastCalledWith({
      shiftVisibleRangeOnNewBar: true,
    });
  },
);
it('requests the first 500 newer candles rather than the latest 500', async () => {
  const { adapter } = fixture();
  vi.mocked(fetchCandles).mockResolvedValue([]);
  const signal = new AbortController().signal;
  await adapter.fetchAfter(
    { symbol: 'EURUSD', timeframe: 'M5', exchange: 'FX' },
    300_000,
    signal,
  );
  expect(fetchCandles).toHaveBeenCalledWith(
    'EURUSD',
    'M5',
    {
      exchange: 'FX',
      startMs: 300_000,
      endMs: expect.any(Number),
      limit: 500,
      fromStart: true,
    },
    signal,
  );
});
