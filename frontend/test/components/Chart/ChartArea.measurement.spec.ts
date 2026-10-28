import {
  chartAreaMocks,
  candle,
  eurUsdM5Key,
  setupStores,
  mountChartArea,
  latestChartSessionAdapter,
  stubMainPaneRect,
  setupChartAreaTests,
} from './ChartArea.fixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

describe('ChartArea measurement', () => {
  setupChartAreaTests();

  it('applies the measure cursor state to the candlestick pane container', async () => {
    setupStores();
    const wrapper = mountChartArea({ interactionMode: 'measure' });
    await flushPromises();

    expect(wrapper.find('#lightweight-chart').classes()).toContain(
      'chart-container--measure-mode',
    );

    await wrapper.setProps({ interactionMode: 'pan' });

    expect(wrapper.find('#lightweight-chart').classes()).not.toContain(
      'chart-container--measure-mode',
    );
  });

  it('measures pane drags while updating the crosshair legend', async () => {
    setupStores();
    const wrapper = mountChartArea({ interactionMode: 'measure' });
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
    ]);
    chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay.mockClear();
    chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay.mockClear();
    chartAreaMocks.infrastructure.coordinateToCandlestickPrice.mockImplementation(
      (coordinate) => {
        if (coordinate === 80) return 1.23456;
        if (coordinate === 40) return 1.23671;
        return null;
      },
    );
    chartAreaMocks.infrastructure.coordinateToLogical.mockImplementation(
      (coordinate) => {
        if (coordinate === 20) return 10.4;
        if (coordinate === 140) return 13.6;
        return null;
      },
    );

    const mainPaneElement = stubMainPaneRect();

    mainPaneElement.dispatchEvent(
      new MouseEvent('pointerdown', {
        bubbles: true,
        button: 0,
        buttons: 1,
        cancelable: true,
        clientX: 120,
        clientY: 280,
      }),
    );

    expect(
      chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay,
    ).toHaveBeenCalledWith(
      expect.objectContaining({
        priceDelta: 0,
        percentDelta: 0,
        candleCount: 1,
        direction: 'neutral',
        box: expect.objectContaining({
          anchorPrice: 1.23456,
          endpointPrice: 1.23456,
          anchorLogical: 10,
          endpointLogical: 10,
          leftLogical: 10,
          rightLogical: 10,
        }),
        label: expect.objectContaining({
          text: '0.0000 (0.00%) 1 candle',
        }),
      }),
    );

    window.dispatchEvent(
      new MouseEvent('pointermove', {
        bubbles: true,
        buttons: 1,
        clientX: 240,
        clientY: 240,
      }),
    );

    expect(
      chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay,
    ).toHaveBeenLastCalledWith(
      expect.objectContaining({
        priceDelta: 0.0021499999999998742,
        candleCount: 5,
        direction: 'positive',
        box: expect.objectContaining({
          anchorPrice: 1.23456,
          endpointPrice: 1.23671,
          anchorLogical: 10,
          endpointLogical: 14,
          leftLogical: 10,
          rightLogical: 14,
        }),
        label: expect.objectContaining({
          text: '+0.0021 (+0.17%) 5 candles',
        }),
      }),
    );

    chartAreaMocks.crosshairHandler?.({
      time: 300,
      point: { x: 1, y: 1 },
      seriesData: new Map([
        [
          chartAreaMocks.ohlcSeries,
          {
            open: 1.1,
            high: 1.3,
            low: 1,
            close: 1.2,
          },
        ],
      ]),
    });

    expect(wrapper.find('.legend').text()).toContain('O: 1.1');
    expect(wrapper.find('.legend').text()).toContain('C: 1.2');

    window.dispatchEvent(
      new MouseEvent('pointerup', {
        bubbles: true,
        button: 0,
        buttons: 0,
      }),
    );

    expect(
      chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay,
    ).toHaveBeenCalled();
    expect(wrapper.props('interactionMode')).toBe('measure');
  });

  it('ignores primary pointer holds while Pan mode is active', async () => {
    setupStores();
    mountChartArea({ interactionMode: 'pan' });
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
    ]);
    chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay.mockClear();
    chartAreaMocks.infrastructure.coordinateToCandlestickPrice.mockReturnValue(
      1.23456,
    );
    chartAreaMocks.infrastructure.coordinateToLogical.mockReturnValue(10.4);

    stubMainPaneRect().dispatchEvent(
      new MouseEvent('pointerdown', {
        bubbles: true,
        button: 0,
        buttons: 1,
        cancelable: true,
        clientX: 120,
        clientY: 280,
      }),
    );

    expect(
      chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay,
    ).not.toHaveBeenCalled();
  });

  it('ignores non-primary pointer holds while Measure mode is active', async () => {
    setupStores();
    mountChartArea({ interactionMode: 'measure' });
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
    ]);
    chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay.mockClear();
    chartAreaMocks.infrastructure.coordinateToCandlestickPrice.mockReturnValue(
      1.23456,
    );
    chartAreaMocks.infrastructure.coordinateToLogical.mockReturnValue(10.4);

    stubMainPaneRect().dispatchEvent(
      new MouseEvent('pointerdown', {
        bubbles: true,
        button: 1,
        buttons: 4,
        cancelable: true,
        clientX: 120,
        clientY: 280,
      }),
    );

    expect(
      chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay,
    ).not.toHaveBeenCalled();
  });

  it('ignores mixed-button holds in Measure mode', async () => {
    setupStores();
    mountChartArea({ interactionMode: 'measure' });
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
    ]);
    chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay.mockClear();
    chartAreaMocks.infrastructure.coordinateToCandlestickPrice.mockReturnValue(
      1.23456,
    );
    chartAreaMocks.infrastructure.coordinateToLogical.mockReturnValue(10.4);

    stubMainPaneRect().dispatchEvent(
      new MouseEvent('pointerdown', {
        bubbles: true,
        button: 0,
        buttons: 3,
        cancelable: true,
        clientX: 120,
        clientY: 280,
      }),
    );

    expect(
      chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay,
    ).not.toHaveBeenCalled();
  });

  it('does not start a measurement without candle data', async () => {
    setupStores();
    mountChartArea({ interactionMode: 'measure' });
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, []);
    chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay.mockClear();
    chartAreaMocks.infrastructure.coordinateToCandlestickPrice.mockReturnValue(
      1.23456,
    );
    chartAreaMocks.infrastructure.coordinateToLogical.mockReturnValue(10.4);

    stubMainPaneRect().dispatchEvent(
      new MouseEvent('pointerdown', {
        bubbles: true,
        button: 0,
        buttons: 1,
        cancelable: true,
        clientX: 120,
        clientY: 280,
      }),
    );

    expect(
      chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay,
    ).not.toHaveBeenCalled();
  });

  it('cancels an active measurement when non-primary buttons join the drag', async () => {
    setupStores();
    mountChartArea({ interactionMode: 'measure' });
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
    ]);
    chartAreaMocks.infrastructure.coordinateToCandlestickPrice.mockReturnValue(
      1.23456,
    );
    chartAreaMocks.infrastructure.coordinateToLogical.mockReturnValue(10.4);

    stubMainPaneRect().dispatchEvent(
      new MouseEvent('pointerdown', {
        bubbles: true,
        button: 0,
        buttons: 1,
        cancelable: true,
        clientX: 120,
        clientY: 280,
      }),
    );

    chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay.mockClear();
    chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay.mockClear();

    window.dispatchEvent(
      new MouseEvent('pointermove', {
        bubbles: true,
        buttons: 3,
        clientX: 240,
        clientY: 240,
      }),
    );

    expect(
      chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay,
    ).toHaveBeenCalledTimes(1);
    expect(
      chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay,
    ).not.toHaveBeenCalled();
  });

  it('cancels on Escape, pointer cancel, blur, and mode changes', async () => {
    setupStores();
    const wrapper = mountChartArea({ interactionMode: 'measure' });
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
    ]);
    chartAreaMocks.infrastructure.coordinateToCandlestickPrice.mockReturnValue(
      1.23456,
    );
    chartAreaMocks.infrastructure.coordinateToLogical.mockReturnValue(10.4);

    const mainPaneElement = stubMainPaneRect();
    const startMeasurement = () => {
      chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay.mockClear();
      chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay.mockClear();
      mainPaneElement.dispatchEvent(
        new MouseEvent('pointerdown', {
          bubbles: true,
          button: 0,
          buttons: 1,
          cancelable: true,
          clientX: 120,
          clientY: 280,
        }),
      );
      expect(
        chartAreaMocks.infrastructure.setCandlestickMeasurementOverlay,
      ).toHaveBeenCalled();
    };

    startMeasurement();
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(
      chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay,
    ).toHaveBeenCalledTimes(1);

    startMeasurement();
    window.dispatchEvent(
      new MouseEvent('pointercancel', { bubbles: true, buttons: 0 }),
    );
    expect(
      chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay,
    ).toHaveBeenCalledTimes(1);

    startMeasurement();
    window.dispatchEvent(new Event('blur'));
    expect(
      chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay,
    ).toHaveBeenCalledTimes(1);

    startMeasurement();
    await wrapper.setProps({ interactionMode: 'pan' });
    expect(
      chartAreaMocks.infrastructure.clearCandlestickMeasurementOverlay,
    ).toHaveBeenCalledTimes(1);
  });
});
