import {
  chartAreaMocks,
  setupStores,
  mountChartArea,
  latestChartSession,
  latestChartSessionAdapter,
  candle,
  eurUsdM5Key,
  setupChartAreaTests,
} from './ChartArea.fixtures';
import type { ChartLogicalRange } from '@/utils/chart';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

describe('ChartArea lifecycle', () => {
  setupChartAreaTests();

  it('initializes chart seams and cleans them up on unmount', async () => {
    setupStores();
    const wrapper = mountChartArea();

    await flushPromises();

    expect(chartAreaMocks.createChartSession).toHaveBeenCalledWith(
      expect.any(Object),
    );
    expect(chartAreaMocks.infrastructure.init).toHaveBeenCalledWith(
      expect.any(HTMLElement),
    );
    expect(
      chartAreaMocks.infrastructure.subscribeCrosshairMove,
    ).toHaveBeenCalled();
    expect(
      chartAreaMocks.infrastructure.subscribeVisibleLogicalRangeChange,
    ).toHaveBeenCalled();
    expect(chartAreaMocks.wsOn).toHaveBeenCalledWith(
      'indicatorUpdate',
      expect.any(Function),
    );

    const session = latestChartSession();
    wrapper.unmount();

    expect(session.stop).toHaveBeenCalled();
    expect(chartAreaMocks.infrastructure.cleanup).toHaveBeenCalled();
    expect(chartAreaMocks.wsOff).toHaveBeenCalledWith(
      'indicatorUpdate',
      expect.any(Function),
    );
  });

  it('cancels queued rendering and removes owned listeners and coverage', async () => {
    const { indicatorsStore } = setupStores();
    const coverage = vi.spyOn(indicatorsStore, 'configureHistoryCoverage');
    const pending = new Map<number, FrameRequestCallback>();
    let nextFrameId = 0;
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      pending.set(++nextFrameId, callback);
      return nextFrameId;
    });
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn((id: number) => pending.delete(id)),
    );
    const wrapper = mountChartArea();
    await flushPromises();
    latestChartSessionAdapter().renderCandles(eurUsdM5Key, [candle(300_000)]);
    await flushPromises();
    const container = wrapper.get('.chart-container').element;
    const removeWheel = vi.spyOn(container, 'removeEventListener');
    const pane = chartAreaMocks.mainPaneElement!;
    const removePointer = vi.spyOn(pane, 'removeEventListener');
    const setTimer = vi.spyOn(globalThis, 'setTimeout');
    const clearTimer = vi.spyOn(globalThis, 'clearTimeout');

    chartAreaMocks.crosshairHandler?.({
      time: 300,
      point: { x: 20, y: 30 },
      seriesData: new Map([[chartAreaMocks.ohlcSeries, candle(300_000)]]),
    });
    chartAreaMocks.visibleRangeHandler?.({
      from: 0,
      to: 10,
    } as ChartLogicalRange);
    for (const handler of chartAreaMocks.indicatorHandlers) {
      handler({
        type: 'indicatorUpdate',
        clientIndicatorId: 'indicator-1',
        timestamp_ms: 300_000,
        values: { sma: 1.2 },
      });
    }
    container.dispatchEvent(new WheelEvent('wheel'));
    const wheelTimer = setTimer.mock.results.at(-1)?.value;
    expect(pending.size).toBe(3);

    wrapper.unmount();

    expect(pending.size).toBe(0);
    expect(cancelAnimationFrame).toHaveBeenCalledTimes(3);
    expect(clearTimer).toHaveBeenCalledTimes(1);
    expect(Number(clearTimer.mock.calls[0][0])).toBe(Number(wheelTimer));
    expect(removeWheel).toHaveBeenCalledWith('wheel', expect.any(Function));
    expect(removePointer).toHaveBeenCalledWith(
      'pointerdown',
      expect.any(Function),
      true,
    );
    expect(chartAreaMocks.indicatorHandlers.size).toBe(0);
    expect(coverage).toHaveBeenLastCalledWith(null);
    expect(latestChartSession().stop.mock.invocationCallOrder[0]).toBeLessThan(
      chartAreaMocks.infrastructure.cleanup.mock.invocationCallOrder[0],
    );
  });
});
