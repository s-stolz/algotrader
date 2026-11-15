import { createPinia, setActivePinia } from 'pinia';
import { afterEach, expect, it, vi } from 'vitest';
import {
  CandlestickSeries,
  createChart,
  type UTCTimestamp,
} from 'lightweight-charts';
import { createTradeHistoryAdapter } from '@/components/Chart/trade-navigation/tradeHistoryAdapter';
import { useCandlesticksStore } from '@/stores/candlesticksStore';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { ChartInfrastructure } from '@/utils/chart';
import { chartCandle } from '../chartSession.fixtures';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it.each([{ deltaX: -100 }, { deltaX: 100 }, { deltaY: 100 }])(
  'preserves user gestures between background batches: %j',
  async (gesture) => {
    vi.useFakeTimers();
    setActivePinia(createPinia());
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        disconnect() {}
      },
    );
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addListener() {},
      removeListener() {},
    }));
    const context = new Proxy(
      {
        measureText: () => ({ width: 20 }),
      },
      {
        get: (target, key) => Reflect.get(target, key) ?? (() => {}),
      },
    );
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
      context as unknown as CanvasRenderingContext2D,
    );
    const container = document.createElement('div');
    document.body.append(container);
    const chart = createChart(container, {
      width: 800,
      height: 400,
    });
    try {
      const series = chart.addSeries(CandlestickSeries);
      const candles = useCandlesticksStore();
      const adapter = createTradeHistoryAdapter({
        candles,
        indicators: useIndicatorsStore(),
        infrastructure: { chartManager: { chart } } as ChartInfrastructure,
        render: (data) =>
          series.setData(
            data.map((candle) => ({
              ...candle,
              time: candle.time as UTCTimestamp,
            })),
          ),
        reset: vi.fn(),
        initializeIndicators: vi.fn(async () => {}),
        loading: vi.fn(),
      });
      const batch = (start: number) =>
        Array.from({ length: 510 }, (_, i) =>
          chartCandle((start + i + 1) * 300_000),
        );
      adapter.prepare();
      adapter.append(batch(0), 11 * 300_000);
      adapter.append(batch(510), null);
      adapter.append(batch(1020), null);
      vi.advanceTimersByTime(50);
      const range = chart.timeScale().getVisibleLogicalRange()!;
      expect(range.from).toBeCloseTo(0);
      expect(range.to).toBeCloseTo(50);

      chart.timeScale().setVisibleLogicalRange({ from: 100, to: 180 });
      vi.advanceTimersByTime(50);
      adapter.append(batch(1530), null);
      const beforeWheel = chart.timeScale().getVisibleLogicalRange()!;
      container.firstElementChild!.dispatchEvent(
        new WheelEvent('wheel', { ...gesture, clientX: 300, bubbles: true }),
      );
      await Promise.resolve();
      const scrolled = chart.timeScale().getVisibleLogicalRange()!;
      expect(scrolled.from).not.toBeCloseTo(100);
      adapter.append(batch(2040), null);
      adapter.finish([]);
      vi.advanceTimersByTime(50);
      const panned = chart.timeScale().getVisibleLogicalRange()!;
      expect(panned.from).toBeCloseTo(100 + scrolled.from - beforeWheel.from);
      expect(panned.to).toBeCloseTo(180 + scrolled.to - beforeWheel.to);
    } finally {
      chart.remove();
      container.remove();
    }
  },
);
