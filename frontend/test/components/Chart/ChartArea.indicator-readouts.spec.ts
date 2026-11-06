import {
  chartAreaMocks,
  candle,
  indicatorInfo,
  eurUsdM5Key,
  setupStores,
  mountChartArea,
  latestChartSessionAdapter,
  latestLiveCandleReceiver,
  setupChartAreaTests,
} from './ChartArea.fixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import Indicator from '@/components/Chart/Indicator/Indicator.vue';

describe('ChartArea indicator readouts', () => {
  setupChartAreaTests();

  it('captures all panes on hover, retains values on leave and resets on navigation', async () => {
    const stores = setupStores();
    const ids = [
      stores.indicatorsStore.addIndicator(indicatorInfo, [], 1),
      stores.indicatorsStore.addIndicator(
        { ...indicatorInfo, overlay: true },
        [],
        1,
        {},
        'run-1',
      ),
    ];
    const plots = ids.map(() => ({
      ...chartAreaMocks.ohlcSeriesInfo,
      series: {
        ...chartAreaMocks.ohlcSeriesInfo.series,
        priceFormatter: () => ({ format: (value: number) => value.toFixed(3) }),
      },
    }));
    vi.spyOn(chartAreaMocks.infrastructure, 'getSeries').mockReturnValue(
      new Map([
        ['ohlc', chartAreaMocks.ohlcSeriesInfo],
        ...ids.map((id, index) => [`${id}_sma`, plots[index]] as const),
      ]),
    );
    let frames: FrameRequestCallback[] = [];
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    });
    const flushFrames = async () => {
      const pending = frames;
      frames = [];
      pending.forEach((callback) => callback(0));
      await flushPromises();
    };
    const wrapper = mountChartArea();
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
    ]);
    await flushFrames();
    const readouts = () =>
      wrapper.findAllComponents(Indicator).map((item) => item.props('readout'));
    expect(readouts()).toEqual([undefined, undefined]);
    const hover = (value: number, paneIndex = 1) => ({
      time: 300,
      point: { x: 1, y: 1 },
      paneIndex,
      seriesData: new Map<object, object>([
        [chartAreaMocks.ohlcSeries, candle(300_000)],
        [plots[0].series, { time: 300, value }],
        [plots[1].series, { time: 300, value: 2 }],
      ]),
    });
    chartAreaMocks.crosshairHandler?.(hover(1));
    chartAreaMocks.crosshairHandler?.(hover(1.25));
    await flushFrames();
    expect(readouts()).toEqual([{ sma: '1.250' }, { sma: '2.000' }]);
    chartAreaMocks.crosshairHandler?.({ ...hover(9), point: { x: -1, y: -1 } });
    chartAreaMocks.crosshairHandler?.({ ...hover(9), seriesData: new Map() });
    latestLiveCandleReceiver()({
      type: 'candleUpdate',
      symbol: 'EURUSD',
      timeframe: 'M5',
      timestamp_ms: 300_000,
      open: 1,
      high: 3,
      low: 1,
      close: 3,
      volume: 1,
    });
    await flushFrames();
    expect(readouts()).toEqual([{ sma: '1.250' }, { sma: '2.000' }]);
    const missing = hover(3, 0);
    missing.seriesData.delete(plots[0].series);
    chartAreaMocks.crosshairHandler?.(missing);
    await flushFrames();
    expect(readouts()).toEqual([{ sma: '—' }, { sma: '2.000' }]);
    chartAreaMocks.crosshairHandler?.(hover(9));
    stores.currentTimeframeStore.value = 'M15';
    await flushPromises();
    await flushFrames();
    expect(readouts().every((value) => value === undefined)).toBe(true);
    chartAreaMocks.crosshairHandler?.(hover(9));
    await flushFrames();
    expect(readouts().every((value) => value === undefined)).toBe(true);
    wrapper.unmount();
  });
});
