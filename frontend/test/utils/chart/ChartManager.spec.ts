import { describe, expect, it, beforeEach, vi } from 'vitest';

import {
  ChartManager,
  type ChartMeasurementOverlayModel,
  type ChartProtectiveLineSegment,
  type ChartSeriesMarker,
  type ChartValuePoint,
} from '@/utils/chart/ChartManager';

const chartMocks = vi.hoisted(() => {
  const createSeriesApi = () => ({
    setData: vi.fn(),
    update: vi.fn(),
    applyOptions: vi.fn(),
    barsInLogicalRange: vi.fn(),
    attachPrimitive: vi.fn(),
    detachPrimitive: vi.fn(),
    createPriceLine: vi.fn(),
  });

  const timeScale = {
    applyOptions: vi.fn(),
    setVisibleLogicalRange: vi.fn(),
    scrollToRealTime: vi.fn(),
    subscribeVisibleLogicalRangeChange: vi.fn(),
    unsubscribeVisibleLogicalRangeChange: vi.fn(),
  };

  const pane = {
    getHTMLElement: vi.fn(),
  };

  const chart = {
    addSeries: vi.fn(),
    removeSeries: vi.fn(),
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
    timeScale: vi.fn(() => timeScale),
    panes: vi.fn(() => [pane]),
    remove: vi.fn(),
  };

  return {
    chart,
    createChart: vi.fn(() => chart),
    createSeriesMarkers: vi.fn(),
    createSeriesApi,
    pane,
    timeScale,
  };
});

vi.mock('lightweight-charts', () => ({
  AreaSeries: { type: 'Area', isBuiltIn: true, defaultOptions: {} },
  BarSeries: { type: 'Bar', isBuiltIn: true, defaultOptions: {} },
  BaselineSeries: { type: 'Baseline', isBuiltIn: true, defaultOptions: {} },
  CandlestickSeries: { type: 'Candlestick', isBuiltIn: true, defaultOptions: {} },
  ColorType: { Solid: 'solid' },
  createChart: chartMocks.createChart,
  createSeriesMarkers: chartMocks.createSeriesMarkers,
  CrosshairMode: { Normal: 0 },
  HistogramSeries: { type: 'Histogram', isBuiltIn: true, defaultOptions: {} },
  LineSeries: { type: 'Line', isBuiltIn: true, defaultOptions: {} },
}));

const candle = (time: number) => ({
  time,
  timestamp_ms: time * 1_000,
  open: time,
  high: time + 1,
  low: time - 1,
  close: time + 0.5,
  volume: 100,
});

const markerTime = (time: number): ChartSeriesMarker['time'] => time as ChartSeriesMarker['time'];

describe('ChartManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chartMocks.chart.addSeries.mockReturnValue(chartMocks.createSeriesApi());
    chartMocks.createChart.mockReturnValue(chartMocks.chart);
    chartMocks.createSeriesMarkers.mockImplementation(() => ({
      detach: vi.fn(),
      markers: vi.fn(() => []),
      setMarkers: vi.fn(),
    }));
  });

  it('initializes a chart and applies time-scale options', () => {
    const container = document.createElement('div');
    const manager = new ChartManager();

    expect(manager.init(container)).toBe(true);

    expect(chartMocks.createChart).toHaveBeenCalledWith(
      container,
      expect.objectContaining({ autoSize: true }),
    );
    expect(chartMocks.timeScale.applyOptions).toHaveBeenCalledWith({
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 5,
    });
  });

  it('creates, updates, and removes managed series', () => {
    const manager = new ChartManager();
    manager.init(document.createElement('div'));
    const firstSeries = chartMocks.createSeriesApi();
    chartMocks.chart.addSeries.mockReturnValue(firstSeries);

    manager.addSeries('ohlc', 'candlestick', [candle(1)], { upColor: '#0f0' });
    manager.addSeries('ohlc', 'candlestick', [candle(2)], { upColor: '#f00' });

    expect(chartMocks.chart.addSeries).toHaveBeenCalledTimes(1);
    expect(firstSeries.setData).toHaveBeenNthCalledWith(1, [candle(1)]);
    expect(firstSeries.setData).toHaveBeenNthCalledWith(2, [candle(2)]);
    expect(firstSeries.applyOptions).toHaveBeenCalledWith({ upColor: '#f00' });
    expect(manager.series.get('ohlc')?.data).toEqual([candle(2)]);

    expect(manager.removeSeries('ohlc')).toBe(true);
    expect(chartMocks.chart.removeSeries).toHaveBeenCalledWith(firstSeries);
    expect(manager.series.has('ohlc')).toBe(false);
  });

  it('replaces same-time candles, appends future candles, and ignores older candles', () => {
    const manager = new ChartManager();
    manager.init(document.createElement('div'));
    const series = chartMocks.createSeriesApi();
    chartMocks.chart.addSeries.mockReturnValue(series);

    manager.addSeries('ohlc', 'candlestick', [candle(10)]);

    expect(manager.updateCandle('ohlc', candle(10))).toBe(true);
    expect(manager.updateCandle('ohlc', candle(11))).toBe(true);
    expect(manager.updateCandle('ohlc', candle(9))).toBe(false);

    expect(series.update).toHaveBeenNthCalledWith(1, candle(10));
    expect(series.update).toHaveBeenNthCalledWith(2, candle(11));
    expect(series.update).toHaveBeenCalledTimes(2);
    expect(manager.series.get('ohlc')?.data).toEqual([candle(10), candle(11)]);
  });

  it('creates, updates, and clears series markers for a managed series', () => {
    const manager = new ChartManager();
    manager.init(document.createElement('div'));
    const series = chartMocks.createSeriesApi();
    chartMocks.chart.addSeries.mockReturnValue(series);
    const firstMarkers: ChartSeriesMarker[] = [
      {
        id: 'trade-1:entry',
        time: markerTime(300),
        position: 'belowBar',
        shape: 'arrowUp',
        color: '#16a34a',
        text: 'Buy @ 101.25',
      },
    ];
    const nextMarkers: ChartSeriesMarker[] = [
      ...firstMarkers,
      {
        id: 'trade-1:exit',
        time: markerTime(600),
        position: 'aboveBar',
        shape: 'arrowDown',
        color: '#dc2626',
        text: 'Sell @ 104.5',
      },
    ];

    manager.addSeries('ohlc', 'candlestick', [candle(1)]);

    expect(manager.setSeriesMarkers('ohlc', firstMarkers)).toBe(true);
    const markerPlugin = chartMocks.createSeriesMarkers.mock.results[0]?.value;

    expect(chartMocks.createSeriesMarkers).toHaveBeenCalledWith(series, firstMarkers);

    expect(manager.setSeriesMarkers('ohlc', nextMarkers)).toBe(true);

    expect(markerPlugin.setMarkers).toHaveBeenCalledWith(nextMarkers);

    expect(manager.clearSeriesMarkers('ohlc')).toBe(true);
    expect(markerPlugin.detach).toHaveBeenCalled();
  });

  it('attaches, updates, and clears protective line primitives without price lines', () => {
    const manager = new ChartManager();
    manager.init(document.createElement('div'));
    const series = chartMocks.createSeriesApi();
    chartMocks.chart.addSeries.mockReturnValue(series);
    const firstSegments: ChartProtectiveLineSegment[] = [
      {
        id: 'trade-1:stop-loss',
        startTime: markerTime(300),
        endTime: markerTime(600),
        price: 98.5,
        color: '#dc2626',
      },
    ];
    const nextSegments: ChartProtectiveLineSegment[] = [
      ...firstSegments,
      {
        id: 'trade-1:take-profit',
        startTime: markerTime(300),
        endTime: markerTime(600),
        price: 108.25,
        color: '#2563eb',
      },
    ];

    manager.addSeries('ohlc', 'candlestick', [candle(1)]);

    expect(manager.setSeriesProtectiveLines('ohlc', firstSegments)).toBe(true);
    const primitive = series.attachPrimitive.mock.calls[0]?.[0] as
      | { paneViews?: () => readonly unknown[] }
      | undefined;

    expect(series.attachPrimitive).toHaveBeenCalledTimes(1);
    expect(series.createPriceLine).not.toHaveBeenCalled();
    expect(primitive?.paneViews?.()).toHaveLength(1);

    expect(manager.setSeriesProtectiveLines('ohlc', nextSegments)).toBe(true);

    expect(series.attachPrimitive).toHaveBeenCalledTimes(1);
    expect(series.createPriceLine).not.toHaveBeenCalled();

    expect(manager.clearSeriesProtectiveLines('ohlc')).toBe(true);
    expect(series.detachPrimitive).toHaveBeenCalledWith(primitive);
  });

  it('attaches, updates, and clears a transient measurement overlay without disturbing markers or protective lines', () => {
    const manager = new ChartManager();
    manager.init(document.createElement('div'));
    const series = chartMocks.createSeriesApi();
    chartMocks.chart.addSeries.mockReturnValue(series);
    const markers: ChartSeriesMarker[] = [
      {
        id: 'trade-1:entry',
        time: markerTime(300),
        position: 'belowBar',
        shape: 'arrowUp',
        color: '#16a34a',
      },
    ];
    const protectiveLines: ChartProtectiveLineSegment[] = [
      {
        id: 'trade-1:stop-loss',
        startTime: markerTime(300),
        endTime: markerTime(600),
        price: 98.5,
        color: '#dc2626',
      },
    ];
    const firstOverlay: ChartMeasurementOverlayModel = {
      priceDelta: 10,
      percentDelta: 10,
      candleCount: 4,
      direction: 'positive',
      box: {
        anchorPrice: 100,
        endpointPrice: 110,
        topPrice: 110,
        bottomPrice: 100,
        anchorLogical: 1,
        endpointLogical: 4,
        leftLogical: 1,
        rightLogical: 4,
      },
      label: {
        priceDelta: '+10.00',
        percentDelta: '+10.00%',
        candleCount: '4 candles',
        text: '+10.00 (+10.00%) 4 candles',
      },
    };
    const nextOverlay: ChartMeasurementOverlayModel = {
      ...firstOverlay,
      priceDelta: -5,
      percentDelta: -5,
      candleCount: 2,
      direction: 'negative',
      box: {
        anchorPrice: 100,
        endpointPrice: 95,
        topPrice: 100,
        bottomPrice: 95,
        anchorLogical: 1,
        endpointLogical: 2,
        leftLogical: 1,
        rightLogical: 2,
      },
      label: {
        priceDelta: '-5.00',
        percentDelta: '-5.00%',
        candleCount: '2 candles',
        text: '-5.00 (-5.00%) 2 candles',
      },
    };

    manager.addSeries('ohlc', 'candlestick', [candle(1)]);
    manager.setSeriesMarkers('ohlc', markers);
    manager.setSeriesProtectiveLines('ohlc', protectiveLines);
    const protectivePrimitive = series.attachPrimitive.mock.calls[0]?.[0];

    expect(manager.setSeriesMeasurementOverlay('ohlc', firstOverlay)).toBe(true);
    const measurementPrimitive = series.attachPrimitive.mock.calls[1]?.[0] as
      | { setModel?: (model: ChartMeasurementOverlayModel) => void; paneViews?: () => readonly unknown[] }
      | undefined;

    expect(series.attachPrimitive).toHaveBeenCalledTimes(2);
    expect(measurementPrimitive).not.toBe(protectivePrimitive);
    expect(measurementPrimitive?.paneViews?.()).toHaveLength(1);

    expect(manager.setSeriesMeasurementOverlay('ohlc', nextOverlay)).toBe(true);

    expect(series.attachPrimitive).toHaveBeenCalledTimes(2);
    expect(series.detachPrimitive).not.toHaveBeenCalledWith(protectivePrimitive);
    expect(chartMocks.createSeriesMarkers.mock.results[0]?.value.setMarkers).not.toHaveBeenCalled();

    expect(manager.clearSeriesMeasurementOverlay('ohlc')).toBe(true);
    expect(series.detachPrimitive).toHaveBeenCalledWith(measurementPrimitive);
    expect(series.detachPrimitive).not.toHaveBeenCalledWith(protectivePrimitive);
  });

  it('updates changed series points, skips same-value points, and appends newer points', () => {
    const manager = new ChartManager();
    manager.init(document.createElement('div'));
    const series = chartMocks.createSeriesApi();
    chartMocks.chart.addSeries.mockReturnValue(series);
    const point = (time: number, value: number): ChartValuePoint => ({ time, value });

    manager.addSeries('sma', 'line', [point(10, 1)]);

    expect(manager.updateSeriesPoint('sma', point(10, 1))).toBe(false);
    expect(manager.updateSeriesPoint('sma', point(10, 2))).toBe(true);
    expect(manager.updateSeriesPoint('sma', point(11, 3))).toBe(true);
    expect(manager.updateSeriesPoint('sma', point(9, 4))).toBe(false);

    expect(series.update).toHaveBeenNthCalledWith(1, point(10, 2));
    expect(series.update).toHaveBeenNthCalledWith(2, point(11, 3));
    expect(series.update).toHaveBeenCalledTimes(2);
    expect(manager.series.get('sma')?.data).toEqual([point(10, 2), point(11, 3)]);
  });

  it('subscribes range handlers, scrolls to realtime, and resolves pane elements', async () => {
    const manager = new ChartManager();
    manager.init(document.createElement('div'));
    const series = chartMocks.createSeriesApi();
    const paneElement = document.createElement('div');
    const crosshairHandler = vi.fn();
    const rangeHandler = vi.fn();
    chartMocks.chart.addSeries.mockReturnValue(series);
    chartMocks.pane.getHTMLElement.mockReturnValue(paneElement);

    manager.addSeries('ohlc', 'candlestick', [candle(1), candle(2), candle(3)]);
    manager.subscribeCrosshairMove(crosshairHandler);
    manager.subscribeVisibleLogicalRangeChange(rangeHandler);
    manager.scrollToRealTime();
    const resolvedPane = await manager.getPaneHtmlElement(0);

    expect(chartMocks.chart.subscribeCrosshairMove).toHaveBeenCalledWith(crosshairHandler);
    expect(chartMocks.timeScale.subscribeVisibleLogicalRangeChange).toHaveBeenCalledWith(rangeHandler);
    expect(chartMocks.timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({ from: 0, to: 2 });
    expect(chartMocks.timeScale.scrollToRealTime).toHaveBeenCalled();
    expect(resolvedPane).toBe(paneElement);

    manager.destroy();

    expect(chartMocks.chart.unsubscribeCrosshairMove).toHaveBeenCalledWith(crosshairHandler);
    expect(chartMocks.timeScale.unsubscribeVisibleLogicalRangeChange).toHaveBeenCalledWith(rangeHandler);
    expect(chartMocks.chart.remove).toHaveBeenCalled();
  });
});
