import { afterEach, describe, expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import {
  setupChartAreaTests,
  setupStores,
  mountChartArea,
  chartAreaMocks,
  latestChartSessionAdapter,
  latestLiveCandleReceiver,
  candle,
  indicatorInfo,
  eurUsdM5Key,
} from './ChartArea.fixtures';

function pendingFont() {
  let resolve!: () => void;
  const ready = new Promise<void>((done) => {
    resolve = done;
  });
  const load = vi.fn(() => ready);
  Object.defineProperty(document, 'fonts', {
    configurable: true,
    value: { check: () => false, load, ready },
  });
  return { resolve, load };
}

describe('ChartArea font readiness', () => {
  setupChartAreaTests();
  afterEach(() => {
    Reflect.deleteProperty(document, 'fonts');
  });

  it('waits for Tektur before rendering the latest stored history and live Candle', async () => {
    const font = pendingFont();
    const { candlesticksStore } = setupStores();
    const wrapper = mountChartArea();
    const adapter = latestChartSessionAdapter();
    adapter.renderCandles(eurUsdM5Key, [candle(300_000)]);
    latestLiveCandleReceiver()({
      type: 'candleUpdate',
      symbol: 'EURUSD',
      timeframe: 'M5',
      ...candle(300_000),
      close: 1.75,
    });
    expect(font.load).toHaveBeenCalledWith('12px Tektur, sans-serif');
    expect(chartAreaMocks.infrastructure.init).not.toHaveBeenCalled();
    expect(
      chartAreaMocks.infrastructure.addCandlestickData,
    ).not.toHaveBeenCalled();
    font.resolve();
    await flushPromises();
    expect(chartAreaMocks.infrastructure.init).toHaveBeenCalledOnce();
    expect(
      chartAreaMocks.infrastructure.addCandlestickData,
    ).toHaveBeenCalledWith(candlesticksStore.data, expect.any(Object));
    expect(candlesticksStore.data[0].close).toBe(1.75);
    wrapper.unmount();
  });

  it('replays merged deferred points before normal live updates', async () => {
    const font = pendingFont();
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    });
    const { indicatorsStore } = setupStores();
    const history = [{ timestamp_ms: 60_000, sma: 1 }];
    const id = indicatorsStore.addIndicator(indicatorInfo, history, 1);
    const wrapper = mountChartArea();
    const deliver = (timestampMs: number, values: Record<string, number>) => {
      for (const handler of chartAreaMocks.indicatorHandlers) {
        handler({
          type: 'indicatorUpdate',
          clientIndicatorId: id,
          timestamp_ms: timestampMs,
          values,
        });
      }
    };
    const flushFrame = () => {
      for (const callback of frames.splice(0)) callback(0);
    };
    deliver(120_000, { sma: 2 });
    flushFrame();
    deliver(120_000, { signal: 4 });
    flushFrame();
    deliver(180_000, { sma: 3 });
    deliver(180_000, { signal: 5 });
    flushFrame();
    deliver(90_000, { sma: 99 });
    flushFrame();
    expect(indicatorsStore.getById(id)?.data).toEqual(history);
    expect(indicatorsStore.getById(id)?.lastLivePoint).toEqual({
      timestamp_ms: 180_000,
      sma: 3,
      signal: 5,
    });
    const update =
      chartAreaMocks.infrastructure.indicatorManager.updateIndicatorSeriesPoint;
    expect(update).not.toHaveBeenCalled();
    font.resolve();
    await flushPromises();
    expect(update.mock.calls).toEqual([
      [id, { timestamp_ms: 120_000, sma: 2, signal: 4 }],
      [id, { timestamp_ms: 180_000, sma: 3, signal: 5 }],
    ]);
    deliver(240_000, { sma: 4 });
    flushFrame();
    expect(update).toHaveBeenLastCalledWith(id, {
      timestamp_ms: 240_000,
      sma: 4,
    });
    expect(update).toHaveBeenCalledTimes(3);
    wrapper.unmount();
  });

  it('discards deferred points from a superseded Indicator history generation', async () => {
    const font = pendingFont();
    const { indicatorsStore } = setupStores();
    const id = indicatorsStore.addIndicator(
      indicatorInfo,
      [{ timestamp_ms: 60_000, sma: 1 }],
      1,
    );
    const wrapper = mountChartArea();
    const deliver = (timestampMs: number) => {
      for (const handler of chartAreaMocks.indicatorHandlers) {
        handler({
          type: 'indicatorUpdate',
          clientIndicatorId: id,
          timestamp_ms: timestampMs,
          values: { sma: 2 },
        });
      }
    };
    deliver(120_000);
    vi.mocked(indicatorsStore.resetHistoryFlags).mockRestore();
    indicatorsStore.resetHistoryFlags();
    indicatorsStore.updateIndicatorData(id, [{ timestamp_ms: 60_000, sma: 9 }]);
    deliver(180_000);
    font.resolve();
    await flushPromises();
    expect(
      chartAreaMocks.infrastructure.indicatorManager.updateIndicatorSeriesPoint
        .mock.calls,
    ).toEqual([[id, { timestamp_ms: 180_000, sma: 2 }]]);
    wrapper.unmount();
  });

  it('does not initialize or attach listeners after unmount while fonts load', async () => {
    const font = pendingFont();
    const { indicatorsStore } = setupStores();
    const id = indicatorsStore.addIndicator(indicatorInfo, [], 1);
    const wrapper = mountChartArea();
    for (const handler of chartAreaMocks.indicatorHandlers) {
      handler({
        type: 'indicatorUpdate',
        clientIndicatorId: id,
        timestamp_ms: 120_000,
        values: { sma: 2 },
      });
    }
    wrapper.unmount();
    font.resolve();
    await flushPromises();
    expect(chartAreaMocks.infrastructure.init).not.toHaveBeenCalled();
    expect(chartAreaMocks.indicatorHandlers.size).toBe(0);
    expect(
      chartAreaMocks.infrastructure.indicatorManager.updateIndicatorSeriesPoint,
    ).not.toHaveBeenCalled();
  });
  it('keeps chart data available if loading the bundled font fails', async () => {
    Object.defineProperty(document, 'fonts', {
      configurable: true,
      value: {
        check: () => false,
        load: () => Promise.reject(new Error('font unavailable')),
      },
    });
    setupStores();
    const wrapper = mountChartArea();
    await flushPromises();
    expect(chartAreaMocks.infrastructure.init).toHaveBeenCalledOnce();
    wrapper.unmount();
  });
});
