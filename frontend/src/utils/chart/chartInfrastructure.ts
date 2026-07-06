import type { CandlestickSeriesPartialOptions, ChartOptions, DeepPartial } from 'lightweight-charts';

import type { ChartCandle } from '@/types/contracts';

import {
  ChartManager,
  type ChartCrosshairMoveHandler,
  type ChartLogicalRange,
  type ChartMeasurementOverlayModel,
  type ChartOhlcPoint,
  type ChartProtectiveLineSegment,
  type ChartSeriesMarker,
  type ChartSeriesInfo,
  type ChartVisibleRangeHandler,
  type ManagedSeriesApi,
} from './ChartManager';
import { IndicatorManager } from './IndicatorManager';

export interface ChartInfrastructure {
  readonly chartManager: ChartManager;
  readonly indicatorManager: IndicatorManager;
  chartInitialized: boolean;
  chartError: Error | null;
  init(containerElement: HTMLElement | null): boolean;
  getSeries(): Map<string, ChartSeriesInfo>;
  addCandlestickData(
    data: readonly ChartCandle[],
    seriesOptions?: CandlestickSeriesPartialOptions,
  ): ManagedSeriesApi | null;
  updateCandlestick(candle: ChartOhlcPoint): boolean;
  setMinMove(minMove: number): boolean;
  setCandlestickMarkers(markers: readonly ChartSeriesMarker[]): boolean;
  setCandlestickProtectiveLines(segments: readonly ChartProtectiveLineSegment[]): boolean;
  setCandlestickMeasurementOverlay(model: ChartMeasurementOverlayModel): boolean;
  clearCandlestickMeasurementOverlay(): boolean;
  subscribeCrosshairMove(callback: ChartCrosshairMoveHandler): void;
  unsubscribeCrosshairMove(callback?: ChartCrosshairMoveHandler | null): void;
  subscribeVisibleLogicalRangeChange(callback: ChartVisibleRangeHandler): void;
  unsubscribeVisibleLogicalRangeChange(callback?: ChartVisibleRangeHandler | null): void;
  scrollToRealTime(): void;
  cleanup(): void;
}

class DefaultChartInfrastructure implements ChartInfrastructure {
  public readonly chartManager: ChartManager;
  public readonly indicatorManager: IndicatorManager;
  public chartInitialized = false;
  public chartError: Error | null = null;

  constructor(options: DeepPartial<ChartOptions> = {}) {
    this.chartManager = new ChartManager(options);
    this.indicatorManager = new IndicatorManager(this.chartManager);
  }

  init(containerElement: HTMLElement | null): boolean {
    if (!containerElement) {
      this.chartInitialized = false;
      return false;
    }

    try {
      this.chartInitialized = this.chartManager.init(containerElement);
      this.chartError = null;
      return this.chartInitialized;
    } catch (error) {
      console.error('Failed to initialize chart:', error);
      this.chartError = error instanceof Error ? error : new Error(String(error));
      this.chartInitialized = false;
      return false;
    }
  }

  getSeries(): Map<string, ChartSeriesInfo> {
    return this.chartManager.series;
  }

  addCandlestickData(
    data: readonly ChartCandle[],
    seriesOptions: CandlestickSeriesPartialOptions = {},
  ): ManagedSeriesApi | null {
    const defaultOptions: CandlestickSeriesPartialOptions = {
      priceFormat: {
        type: 'price',
        ...seriesOptions.priceFormat,
      },
      ...seriesOptions,
    };

    return this.chartManager.addSeries('ohlc', 'candlestick', data, defaultOptions);
  }

  updateCandlestick(candle: ChartOhlcPoint): boolean {
    return this.chartManager.updateCandle('ohlc', candle);
  }

  setMinMove(minMove: number): boolean {
    return this.chartManager.updateSeriesOptions('ohlc', {
      priceFormat: {
        type: 'price',
        minMove,
        precision: Math.log10(1 / minMove),
      },
    });
  }

  setCandlestickMarkers(markers: readonly ChartSeriesMarker[]): boolean {
    return this.chartManager.setSeriesMarkers('ohlc', markers);
  }

  setCandlestickProtectiveLines(segments: readonly ChartProtectiveLineSegment[]): boolean {
    return this.chartManager.setSeriesProtectiveLines('ohlc', segments);
  }

  setCandlestickMeasurementOverlay(model: ChartMeasurementOverlayModel): boolean {
    return this.chartManager.setSeriesMeasurementOverlay('ohlc', model);
  }

  clearCandlestickMeasurementOverlay(): boolean {
    return this.chartManager.clearSeriesMeasurementOverlay('ohlc');
  }

  subscribeCrosshairMove(callback: ChartCrosshairMoveHandler): void {
    this.chartManager.subscribeCrosshairMove(callback);
  }

  unsubscribeCrosshairMove(callback: ChartCrosshairMoveHandler | null = null): void {
    this.chartManager.unsubscribeCrosshairMove(callback);
  }

  subscribeVisibleLogicalRangeChange(callback: ChartVisibleRangeHandler): void {
    this.chartManager.subscribeVisibleLogicalRangeChange(callback);
  }

  unsubscribeVisibleLogicalRangeChange(callback: ChartVisibleRangeHandler | null = null): void {
    this.chartManager.unsubscribeVisibleLogicalRangeChange(callback);
  }

  scrollToRealTime(): void {
    this.chartManager.scrollToRealTime();
  }

  cleanup(): void {
    this.indicatorManager.destroy();
    this.chartManager.destroy();
    this.chartInitialized = false;
  }
}

export function createChartInfrastructure(
  options: DeepPartial<ChartOptions> = {},
): ChartInfrastructure {
  return new DefaultChartInfrastructure(options);
}

export type {
  ChartCrosshairMoveHandler,
  ChartLogicalRange,
  ChartMeasurementOverlayModel,
  ChartOhlcPoint,
  ChartProtectiveLineSegment,
  ChartSeriesMarker,
  ChartVisibleRangeHandler,
  ManagedSeriesApi,
};
