import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { marketPricePrecision } from './priceFormatting';
import { isChartSeriesType } from './seriesTypes';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { IndicatorDataPoint, JsonObject } from '@/types/contracts';
import { OpeningRangeOverlays } from './openingRange/lifecycle';
import {
  colorIndicatorPoint,
  resolveIndicatorPlotStyle,
} from './indicatorPlotStyle';

import type {
  ChartSeriesInfo,
  ChartSeriesOptions,
  ChartSeriesType,
  ChartValuePoint,
  ManagedSeriesApi,
} from './ChartManager';

export interface IndicatorChartManager {
  readonly series: Map<string, ChartSeriesInfo>;
  addSeries(
    key: string,
    type: ChartSeriesType,
    data: readonly ChartValuePoint[],
    seriesOptions?: ChartSeriesOptions,
    paneIndex?: number,
  ): ManagedSeriesApi | null;
  updateSeriesOptions(key: string, newOptions: ChartSeriesOptions): boolean;
  updateSeriesPoint(key: string, point: ChartValuePoint): boolean;
  setSeriesData(key: string, data: readonly ChartValuePoint[]): boolean;
  removeSeries(key: string): boolean;
  getPaneHtmlElement(paneIndex?: number): Promise<HTMLElement | null>;
}

type IndicatorsStore = ReturnType<typeof useIndicatorsStore>;

function toChartSeriesOptions(
  options: JsonObject | undefined,
): ChartSeriesOptions {
  const chartOptions = { ...options };
  delete chartOptions.negativeColor;
  return chartOptions as ChartSeriesOptions;
}

export class IndicatorManager {
  public readonly indicatorsStore: IndicatorsStore;
  private readonly chartManager: IndicatorChartManager;
  private readonly ranges: OpeningRangeOverlays;

  constructor(chartManager: IndicatorChartManager) {
    this.indicatorsStore = useIndicatorsStore();
    this.chartManager = chartManager;
    this.ranges = new OpeningRangeOverlays(chartManager.series);
  }

  async addIndicatorSeries(id: string): Promise<void> {
    const indicator = this.indicatorsStore.getById(id);
    if (!indicator) {
      return;
    }

    const { info, data, paneIndex } = indicator;
    if (info.indicator_id === 'opening_range') {
      this.ranges.update(indicator);
      return;
    }

    for (const [outputKey, outputInfo] of Object.entries(info.outputs)) {
      if (outputKey === 'timestamp') {
        continue;
      }

      if (!isChartSeriesType(outputInfo.type)) {
        continue;
      }

      const style = resolveIndicatorPlotStyle(indicator, outputKey);
      const transformedData = this.transformIndicatorData(
        data,
        outputKey,
        outputInfo.type,
        style,
      );

      const seriesOptions: ChartSeriesOptions = {
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
        ...toChartSeriesOptions(style),
        ...this.priceOptions(paneIndex),
      };
      const seriesKey = `${id}_${outputKey}`;
      if (this.chartManager.series.has(seriesKey)) continue;

      const series = this.chartManager.addSeries(
        seriesKey,
        outputInfo.type,
        transformedData,
        seriesOptions,
        paneIndex,
      );
      if (outputInfo.type === 'histogram') series?.setSeriesOrder(0);
    }
    await this.updateMissingPaneHtmlElements();
  }

  private priceOptions(paneIndex: number | undefined): ChartSeriesOptions {
    const minMove = useCurrentMarketStore().min_move;
    if (
      paneIndex !== 0 ||
      !minMove ||
      !Number.isFinite(minMove) ||
      minMove <= 0
    )
      return {};
    return {
      priceFormat: {
        type: 'price',
        minMove,
        precision: marketPricePrecision(minMove),
      },
    };
  }

  transformIndicatorData(
    data: readonly IndicatorDataPoint[],
    outputKey: string,
    outputType?: string,
    style?: JsonObject,
  ): ChartValuePoint[] {
    const points: ChartValuePoint[] = [];

    for (const item of data) {
      const time = Math.floor(Number(item.timestamp_ms) / 1000);
      const value = item[outputKey];

      if (
        !Number.isFinite(time) ||
        typeof value !== 'number' ||
        !Number.isFinite(value)
      ) {
        continue;
      }

      points.push(colorIndicatorPoint({ time, value }, outputType, style));
    }

    return points;
  }

  updateIndicatorStyles(
    id: string,
    outputKey: string,
    newStyles: ChartSeriesOptions & { negativeColor?: string },
  ): boolean {
    const indicator = this.indicatorsStore.getById(id);
    if (indicator) indicator.styles[outputKey] = { ...newStyles } as JsonObject;
    if (indicator?.info.indicator_id === 'opening_range') {
      this.ranges.update(indicator);
      return true;
    }
    const seriesKey = `${id}_${outputKey}`;
    const style = indicator
      ? resolveIndicatorPlotStyle(indicator, outputKey)
      : (newStyles as JsonObject);
    const series = this.chartManager.series.get(seriesKey);
    if (series?.type === 'histogram') {
      this.chartManager.setSeriesData(
        seriesKey,
        series.data
          .filter((point): point is ChartValuePoint => 'value' in point)
          .map((point) => colorIndicatorPoint(point, series.type, style)),
      );
    }
    return this.chartManager.updateSeriesOptions(seriesKey, {
      ...toChartSeriesOptions(style),
      ...this.priceOptions(indicator?.paneIndex),
    });
  }

  removeIndicatorSeriesAndData(id: string): void {
    this.removeIndicatorSeries(id);
    this.indicatorsStore.removeIndicator(id);
  }

  refreshIndicatorSeries(id: string): void {
    const indicator = this.indicatorsStore.getById(id);

    if (!indicator) return;

    const { info, data } = indicator;
    if (info.indicator_id === 'opening_range') {
      this.ranges.update(indicator);
      return;
    }

    for (const outputKey of Object.keys(info.outputs)) {
      if (outputKey === 'timestamp') continue;

      const seriesKey = `${id}_${outputKey}`;
      const seriesInfo = this.chartManager.series.get(seriesKey);

      if (!seriesInfo) {
        void this.addIndicatorSeries(id);
        continue;
      }

      if (indicator.paneIndex === 0) {
        this.chartManager.updateSeriesOptions(seriesKey, this.priceOptions(0));
      }
      const transformed = this.transformIndicatorData(
        data,
        outputKey,
        info.outputs[outputKey]?.type,
        resolveIndicatorPlotStyle(indicator, outputKey),
      );
      this.chartManager.setSeriesData(seriesKey, transformed);
    }
  }

  updateIndicatorSeriesPoint(
    id: string,
    point: IndicatorDataPoint | null,
  ): void {
    const indicator = this.indicatorsStore.getById(id);
    if (!indicator || !point) {
      return;
    }

    const time = Math.floor(Number(point.timestamp_ms) / 1000);
    if (!Number.isFinite(time)) {
      return;
    }

    for (const outputKey of Object.keys(indicator.info.outputs)) {
      if (outputKey === 'timestamp') {
        continue;
      }

      const value = point[outputKey];
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        continue;
      }

      const seriesKey = `${id}_${outputKey}`;
      this.chartManager.updateSeriesPoint(
        seriesKey,
        colorIndicatorPoint(
          { time, value },
          indicator.info.outputs[outputKey]?.type,
          resolveIndicatorPlotStyle(indicator, outputKey),
        ),
      );
    }
  }

  removeIndicatorSeries(id: string): void {
    this.ranges.remove(id);
    const indicator = this.indicatorsStore.getById(id);
    if (!indicator) return;

    for (const indicatorOutput of Object.keys(indicator.info.outputs)) {
      if (indicatorOutput === 'timestamp') {
        continue;
      }

      const seriesKey = `${id}_${indicatorOutput}`;
      this.chartManager.removeSeries(seriesKey);
    }
  }

  async updateMissingPaneHtmlElements(): Promise<void> {
    for (const indicator of this.indicatorsStore.all) {
      const hasSeries = Object.keys(indicator.info.outputs).some((output) =>
        this.chartManager.series.has(`${indicator._id}_${output}`),
      );
      const hasRangePane =
        indicator.info.indicator_id === 'opening_range' &&
        this.chartManager.series.has('ohlc');
      if (indicator.paneHtmlElement === null && (hasSeries || hasRangePane)) {
        const paneHtmlElement = await this.chartManager.getPaneHtmlElement(
          indicator.paneIndex,
        );
        if (this.indicatorsStore.getById(indicator._id) === indicator) {
          this.indicatorsStore.updateIndicatorPaneElement(
            indicator._id,
            paneHtmlElement,
          );
        }
      }
    }
  }

  destroy(): void {
    const allIndicatorIds = Array.from(this.indicatorsStore.indicators.keys());

    for (const id of allIndicatorIds) {
      this.removeIndicatorSeries(id);
      this.indicatorsStore.updateIndicatorPaneElement(id, null);
    }

    void this.indicatorsStore.unsubscribeAllLive();
  }
}
