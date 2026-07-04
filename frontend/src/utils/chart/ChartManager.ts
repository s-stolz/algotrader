import {
  AreaSeries,
  BarSeries,
  BaselineSeries,
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  type AreaData,
  type BarData,
  type BaselineData,
  type CandlestickData,
  type ChartOptions,
  type DeepPartial,
  type HistogramData,
  type HorzScaleOptions,
  type IChartApi,
  type IPaneApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type LineData,
  type LogicalRange,
  type LogicalRangeChangeEventHandler,
  type MouseEventHandler,
  type SeriesMarker,
  type SeriesDefinition,
  type SeriesPartialOptionsMap,
  type SeriesType,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';

import {
  ProtectiveLinesPrimitive,
  type ChartProtectiveLineSegment,
} from './protectiveLinesPrimitive';

export type ChartSeriesType =
  | 'line'
  | 'area'
  | 'bar'
  | 'baseline'
  | 'candlestick'
  | 'histogram';

export interface ChartOhlcPoint {
  timestamp_ms?: number;
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface ChartValuePoint {
  time: number;
  value: number;
  color?: string;
}

export type ChartDataPoint = ChartOhlcPoint | ChartValuePoint;
export type ChartSeriesOptions = SeriesPartialOptionsMap[SeriesType];
export type ManagedSeriesApi = ISeriesApi<SeriesType, Time>;
export type ChartSeriesMarker = SeriesMarker<Time>;
export type ChartCrosshairMoveHandler = MouseEventHandler<Time>;
export type ChartVisibleRangeHandler = LogicalRangeChangeEventHandler;
export type ChartLogicalRange = LogicalRange;

type LightweightChartPoint =
  | AreaData<UTCTimestamp>
  | BarData<UTCTimestamp>
  | BaselineData<UTCTimestamp>
  | CandlestickData<UTCTimestamp>
  | HistogramData<UTCTimestamp>
  | LineData<UTCTimestamp>;

type ManagedSeriesData = Parameters<ManagedSeriesApi['setData']>[0];
type ManagedSeriesPoint = ManagedSeriesData[number];

export interface ChartSeriesInfo {
  series: ManagedSeriesApi;
  type: ChartSeriesType;
  data: ChartDataPoint[];
  options: ChartSeriesOptions;
}

const SERIES_TYPES: Record<ChartSeriesType, SeriesDefinition<SeriesType>> = {
  line: LineSeries,
  area: AreaSeries,
  bar: BarSeries,
  baseline: BaselineSeries,
  candlestick: CandlestickSeries,
  histogram: HistogramSeries,
};

function toLightweightPoint(point: ChartDataPoint): ManagedSeriesPoint {
  return {
    ...point,
    time: point.time as UTCTimestamp,
  } as LightweightChartPoint as ManagedSeriesPoint;
}

function toLightweightData(data: readonly ChartDataPoint[]): ManagedSeriesData {
  return data.map((point) => toLightweightPoint(point)) as ManagedSeriesData;
}

export class ChartManager {
  public chart: IChartApi | null = null;
  public readonly series = new Map<string, ChartSeriesInfo>();
  public container: HTMLElement | null = null;
  public readonly loadedBars = 500;
  public readonly initialVisibleCandles = 50;

  private readonly markerPlugins = new Map<string, ISeriesMarkersPluginApi<Time>>();
  private readonly protectiveLinePrimitives = new Map<string, ProtectiveLinesPrimitive>();
  private readonly defaultOptions: DeepPartial<ChartOptions>;
  private readonly timeScaleOptions: DeepPartial<HorzScaleOptions>;
  private crosshairMoveHandler: ChartCrosshairMoveHandler | null = null;
  private visibleLogicalRangeHandler: ChartVisibleRangeHandler | null = null;

  constructor(options: DeepPartial<ChartOptions> = {}) {
    this.defaultOptions = {
      layout: {
        textColor: '#d1d4dc',
        background: { type: ColorType.Solid, color: 'transparent' },
        panes: {
          separatorColor: 'rgba(96,96,96,0.3)',
        },
      },
      grid: {
        vertLines: { color: 'transparent' },
        horzLines: { color: 'transparent' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      autoSize: true,
      ...options,
    };

    this.timeScaleOptions = {
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 5,
    };
  }

  init(containerElement: HTMLElement): boolean {
    this.container = containerElement;

    try {
      this.chart = createChart(containerElement, this.defaultOptions);
      this.chart.timeScale().applyOptions(this.timeScaleOptions);
      return true;
    } catch (error) {
      console.error('Failed to initialize chart:', error);
      this.chart = null;
      return false;
    }
  }

  addSeries(
    key: string,
    type: ChartSeriesType,
    data: readonly ChartDataPoint[],
    seriesOptions: ChartSeriesOptions = {},
    paneIndex = 0,
  ): ManagedSeriesApi | null {
    if (!this.chart) {
      console.error('Chart not initialized');
      return null;
    }

    if (this.series.has(key)) {
      const existingSeriesInfo = this.series.get(key);
      if (!existingSeriesInfo) {
        return null;
      }

      existingSeriesInfo.series.setData(toLightweightData(data));
      existingSeriesInfo.data = [...data];

      if (JSON.stringify(existingSeriesInfo.options) !== JSON.stringify(seriesOptions)) {
        existingSeriesInfo.series.applyOptions(seriesOptions);
        existingSeriesInfo.options = { ...seriesOptions };
      }

      return existingSeriesInfo.series;
    }

    const newSeries = this.createSeries(type, seriesOptions, paneIndex);

    if (newSeries) {
      newSeries.setData(toLightweightData(data));
      this.series.set(key, {
        series: newSeries,
        type,
        data: [...data],
        options: { ...seriesOptions },
      });
    }

    return newSeries;
  }

  setSeriesData(key: string, data: readonly ChartDataPoint[]): boolean {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      return false;
    }

    try {
      seriesInfo.series.setData(toLightweightData(data));
      seriesInfo.data = [...data];
      return true;
    } catch (error) {
      console.error(`Failed to set data for series '${key}':`, error);
      return false;
    }
  }

  updateCandle(key: string, candle: ChartOhlcPoint): boolean {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      console.warn(`Series '${key}' not found`);
      return false;
    }

    try {
      const last = seriesInfo.data[seriesInfo.data.length - 1];

      if (!last) {
        seriesInfo.series.update(toLightweightPoint(candle));
        seriesInfo.data.push(candle);
        return true;
      }

      if (last.time === candle.time) {
        seriesInfo.series.update(toLightweightPoint(candle));
        seriesInfo.data[seriesInfo.data.length - 1] = candle;
        return true;
      }

      if (last.time < candle.time) {
        seriesInfo.series.update(toLightweightPoint(candle));
        seriesInfo.data.push(candle);
        return true;
      }
    } catch (error) {
      console.error(`Failed to update candle for series '${key}':`, error);
    }

    return false;
  }

  updateSeriesPoint(key: string, point: ChartValuePoint): boolean {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      return false;
    }

    try {
      const last = seriesInfo.data[seriesInfo.data.length - 1];

      if (!last) {
        seriesInfo.series.update(toLightweightPoint(point));
        seriesInfo.data.push(point);
        return true;
      }

      if (last.time === point.time && 'value' in last) {
        if (last.value === point.value) {
          return false;
        }
        seriesInfo.series.update(toLightweightPoint(point));
        seriesInfo.data[seriesInfo.data.length - 1] = point;
        return true;
      }

      if (last.time < point.time) {
        seriesInfo.series.update(toLightweightPoint(point));
        seriesInfo.data.push(point);
        return true;
      }
    } catch (error) {
      console.error(`Failed to update point for series '${key}':`, error);
    }

    return false;
  }

  createSeries(
    type: ChartSeriesType,
    seriesOptions: ChartSeriesOptions = {},
    paneIndex = 0,
  ): ManagedSeriesApi | null {
    if (!this.chart) {
      console.error('Chart not initialized');
      return null;
    }

    const seriesDefinition = SERIES_TYPES[type];
    if (!seriesDefinition) {
      console.error('Invalid series type:', type);
      return null;
    }

    try {
      return this.chart.addSeries(seriesDefinition, seriesOptions, paneIndex) as ManagedSeriesApi;
    } catch (error) {
      console.error('Failed to create series:', error);
      return null;
    }
  }

  removeSeries(key: string): boolean {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo || !this.chart) {
      return false;
    }

    try {
      this.clearSeriesMarkers(key);
      this.clearSeriesProtectiveLines(key);
      this.chart.removeSeries(seriesInfo.series);
      this.series.delete(key);
      return true;
    } catch (error) {
      console.error(`Failed to remove series '${key}':`, error);
      return false;
    }
  }

  setSeriesMarkers(key: string, markers: readonly ChartSeriesMarker[]): boolean {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      return false;
    }

    try {
      const nextMarkers = [...markers];
      const markerPlugin = this.markerPlugins.get(key);

      if (markerPlugin) {
        markerPlugin.setMarkers(nextMarkers);
        return true;
      }

      this.markerPlugins.set(key, createSeriesMarkers(seriesInfo.series, nextMarkers));
      return true;
    } catch (error) {
      console.error(`Failed to set markers for series '${key}':`, error);
      return false;
    }
  }

  clearSeriesMarkers(key: string): boolean {
    const markerPlugin = this.markerPlugins.get(key);
    if (!markerPlugin) {
      return false;
    }

    try {
      markerPlugin.detach();
      this.markerPlugins.delete(key);
      return true;
    } catch (error) {
      console.error(`Failed to clear markers for series '${key}':`, error);
      return false;
    }
  }

  setSeriesProtectiveLines(
    key: string,
    segments: readonly ChartProtectiveLineSegment[],
  ): boolean {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      return false;
    }

    try {
      const nextSegments = [...segments];

      if (nextSegments.length === 0) {
        this.clearSeriesProtectiveLines(key);
        return true;
      }

      const primitive = this.protectiveLinePrimitives.get(key);
      if (primitive) {
        primitive.setSegments(nextSegments);
        return true;
      }

      const nextPrimitive = new ProtectiveLinesPrimitive(nextSegments);
      seriesInfo.series.attachPrimitive(nextPrimitive);
      this.protectiveLinePrimitives.set(key, nextPrimitive);
      return true;
    } catch (error) {
      console.error(`Failed to set protective lines for series '${key}':`, error);
      return false;
    }
  }

  clearSeriesProtectiveLines(key: string): boolean {
    const primitive = this.protectiveLinePrimitives.get(key);
    const seriesInfo = this.series.get(key);

    if (!primitive || !seriesInfo) {
      return false;
    }

    try {
      seriesInfo.series.detachPrimitive(primitive);
      this.protectiveLinePrimitives.delete(key);
      return true;
    } catch (error) {
      console.error(`Failed to clear protective lines for series '${key}':`, error);
      return false;
    }
  }

  scrollToRealTime(): void {
    if (!this.chart) return;

    const ohlcSeriesInfo = this.series.get('ohlc');
    const candleCount = ohlcSeriesInfo?.data?.length || 0;

    if (candleCount > 0) {
      const to = candleCount - 1;
      const from = Math.max(0, to - this.initialVisibleCandles + 1);
      this.chart.timeScale().setVisibleLogicalRange({ from, to });
    }

    this.chart.timeScale().scrollToRealTime();
  }

  updateSeriesOptions(key: string, newOptions: ChartSeriesOptions): boolean {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      return false;
    }

    try {
      seriesInfo.series.applyOptions(newOptions);
      seriesInfo.options = { ...seriesInfo.options, ...newOptions };
      return true;
    } catch (error) {
      console.error(`Failed to update options for series '${key}':`, error);
      return false;
    }
  }

  async getPaneHtmlElement(paneIndex = 0): Promise<HTMLElement | null> {
    if (!this.chart || !this.isValidPaneIndex(paneIndex)) {
      return null;
    }

    const pane = this.chart.panes()[paneIndex];
    return this.waitForPaneHtmlElement(pane);
  }

  isValidPaneIndex(paneIndex: number): boolean {
    if (!this.chart) {
      return false;
    }

    const panes = this.chart.panes();
    const isValid = paneIndex >= 0 && paneIndex < panes.length;

    if (!isValid) {
      console.error(`Invalid pane index: ${paneIndex}. Available panes: ${panes.length}`);
    }

    return isValid;
  }

  async waitForPaneHtmlElement(
    pane: IPaneApi<Time>,
    maxAttempts = 10,
    delay = 100,
  ): Promise<HTMLElement | null> {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const element = this.tryGetHtmlElement(pane);
      if (element) {
        return element;
      }

      if (attempt < maxAttempts - 1) {
        await new Promise((resolve) => {
          setTimeout(resolve, delay);
        });
      }
    }

    console.warn('Pane HTML element not available after maximum attempts');
    return null;
  }

  tryGetHtmlElement(pane: IPaneApi<Time> | null | undefined): HTMLElement | null {
    try {
      return pane?.getHTMLElement?.() || null;
    } catch {
      return null;
    }
  }

  subscribeCrosshairMove(callback: ChartCrosshairMoveHandler): void {
    if (!this.chart) {
      return;
    }

    this.unsubscribeCrosshairMove();
    this.crosshairMoveHandler = callback;
    this.chart.subscribeCrosshairMove(callback);
  }

  unsubscribeCrosshairMove(callback: ChartCrosshairMoveHandler | null = null): void {
    if (!this.chart) {
      this.crosshairMoveHandler = null;
      return;
    }

    const handler = callback || this.crosshairMoveHandler;
    if (!handler) {
      return;
    }

    this.chart.unsubscribeCrosshairMove(handler);

    if (!callback || callback === this.crosshairMoveHandler) {
      this.crosshairMoveHandler = null;
    }
  }

  subscribeVisibleLogicalRangeChange(callback: ChartVisibleRangeHandler): void {
    if (!this.chart) {
      return;
    }

    this.unsubscribeVisibleLogicalRangeChange();
    this.visibleLogicalRangeHandler = callback;
    this.chart.timeScale().subscribeVisibleLogicalRangeChange(callback);
  }

  unsubscribeVisibleLogicalRangeChange(callback: ChartVisibleRangeHandler | null = null): void {
    if (!this.chart) {
      this.visibleLogicalRangeHandler = null;
      return;
    }

    const handler = callback || this.visibleLogicalRangeHandler;
    if (!handler) {
      return;
    }

    this.chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler);

    if (!callback || callback === this.visibleLogicalRangeHandler) {
      this.visibleLogicalRangeHandler = null;
    }
  }

  destroy(): void {
    if (this.chart) {
      this.unsubscribeCrosshairMove();
      this.unsubscribeVisibleLogicalRangeChange();

      for (const key of Array.from(this.series.keys())) {
        this.removeSeries(key);
      }

      this.chart.remove();
      this.chart = null;
      this.container = null;
    }

    for (const key of Array.from(this.markerPlugins.keys())) {
      this.clearSeriesMarkers(key);
    }

    for (const key of Array.from(this.protectiveLinePrimitives.keys())) {
      this.clearSeriesProtectiveLines(key);
    }

    this.series.clear();
  }
}

export type { ChartProtectiveLineSegment };
