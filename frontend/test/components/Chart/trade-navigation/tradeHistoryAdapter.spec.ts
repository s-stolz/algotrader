import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createTradeHistoryAdapter } from '@/components/Chart/trade-navigation/tradeHistoryAdapter';
import { useCandlesticksStore } from '@/stores/candlesticksStore';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { ChartInfrastructure } from '@/utils/chart';
import { chartCandle, candleUpdate } from '../chartSession.fixtures';

beforeEach(() => {
  setActivePinia(createPinia());
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());
describe('trade viewport and history', () => {
  it.each([120, 5])(
    'preserves a %s-bar zoom and respects later panning',
    (width) => {
      const candles = useCandlesticksStore();
      const indicators = useIndicatorsStore();
      const scale = {
        getVisibleLogicalRange: vi.fn(() => ({ from: 20, to: 20 + width })),
        setVisibleLogicalRange: vi.fn(),
        subscribeVisibleLogicalRangeChange: vi.fn(),
        unsubscribeVisibleLogicalRangeChange: vi.fn(),
      };
      const infrastructure = {
        chartManager: { chart: { timeScale: () => scale } },
      };
      const render = vi.fn();
      const adapter = createTradeHistoryAdapter({
        candles,
        indicators,
        infrastructure: infrastructure as unknown as ChartInfrastructure,
        render,
        reset: vi.fn(),
        initializeIndicators: vi.fn(async () => {}),
        loading: vi.fn(),
      });
      candles.replace([chartCandle(1_000_000)]);
      adapter.prepare();
      expect(candles.data).toEqual([]);
      expect(render).toHaveBeenLastCalledWith([]);
      const before = Array.from({ length: 11 }, (_, i) =>
        chartCandle(i * 300_000),
      );
      adapter.append(before, 3_000_001);
      expect(scale.setVisibleLogicalRange).toHaveBeenLastCalledWith({
        from: width < 11 ? 11 - width : 0,
        to: width < 11 ? 11 : width,
      });
      vi.advanceTimersByTime(20);
      scale.getVisibleLogicalRange.mockReturnValue({ from: 3, to: 63 });
      adapter.append([chartCandle(3_300_000)], null);
      expect(scale.setVisibleLogicalRange).toHaveBeenLastCalledWith({
        from: 3,
        to: 63,
      });
      adapter.finish([candleUpdate(3_300_000, 4), candleUpdate(3_600_000, 5)]);
      expect(candles.data).toHaveLength(13);
      expect(candles.data.at(-2)?.close).toBe(4);
      expect(scale.setVisibleLogicalRange).toHaveBeenLastCalledWith({
        from: 3,
        to: 63,
      });
    },
  );
});
