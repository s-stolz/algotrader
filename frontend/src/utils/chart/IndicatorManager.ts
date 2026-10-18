import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { IndicatorDataPoint, JsonObject } from '@/types/contracts';

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

const CHART_SERIES_TYPES = new Set<ChartSeriesType>([
  'line',
  'area',
  'bar',
  'baseline',
  'candlestick',
  'histogram',
]);

function isChartSeriesType(value: string | undefined): value is ChartSeriesType {
  return value !== undefined && CHART_SERIES_TYPES.has(value as ChartSeriesType);
}

function toChartSeriesOptions(options: JsonObject | undefined): ChartSeriesOptions {
  return options ? { ...options } as ChartSeriesOptions : {};
}

export class IndicatorManager {
  public readonly indicatorsStore: IndicatorsStore;
  private readonly chartManager: IndicatorChartManager;

  constructor(chartManager: IndicatorChartManager) {
    this.indicatorsStore = useIndicatorsStore();
    this.chartManager = chartManager;
  }

  async addIndicatorSeries(id: string): Promise<void> {
    const indicator = this.indicatorsStore.getById(id);
    if (!indicator) {
      return;
    }

    const { info, data, paneIndex } = indicator;

    if (!data.length) {
      return;
    }

    for (const [outputKey, outputInfo] of Object.entries(info.outputs)) {
      if (outputKey === 'timestamp') {
        continue;
      }

      if (!isChartSeriesType(outputInfo.type)) {
        continue;
      }

      const transformedData = this.transformIndicatorData(data, outputKey);

      if (transformedData.length > 0) {
        const seriesOptions: ChartSeriesOptions = {
          crosshairMarkerVisible: false,
          lastValueVisible: false,
          priceLineVisible: false,
          ...toChartSeriesOptions(outputInfo.plotOptions),
        };
        const seriesKey = `${id}_${outputKey}`;

        this.chartManager.addSeries(
          seriesKey,
          outputInfo.type,
          transformedData,
          seriesOptions,
          paneIndex,
        );
      }
    }
  }

  transformIndicatorData(data: readonly IndicatorDataPoint[], outputKey: string): ChartValuePoint[] {
    const points: ChartValuePoint[] = [];

    for (const item of data) {
      const time = Math.floor(Number(item.timestamp_ms) / 1000);
      const value = item[outputKey];

      if (!Number.isFinite(time) || typeof value !== 'number' || !Number.isFinite(value)) {
        continue;
      }

      points.push({ time, value });
    }

    return points;
  }

  updateIndicatorStyles(id: string, outputKey: string, newStyles: ChartSeriesOptions): boolean {
    const seriesKey = `${id}_${outputKey}`;
    return this.chartManager.updateSeriesOptions(seriesKey, newStyles);
  }

  removeIndicatorSeriesAndData(id: string): void {
    this.removeIndicatorSeries(id);
    this.indicatorsStore.removeIndicator(id);
  }

  refreshIndicatorSeries(id: string): void {
    const indicator = this.indicatorsStore.getById(id);

    if (!indicator) return;

    const { info, data } = indicator;

    for (const outputKey of Object.keys(info.outputs)) {
      if (outputKey === 'timestamp') continue;

      const seriesKey = `${id}_${outputKey}`;
      const seriesInfo = this.chartManager.series.get(seriesKey);

      if (!seriesInfo) continue;

      const transformed = this.transformIndicatorData(data, outputKey);
      this.chartManager.setSeriesData(seriesKey, transformed);
    }
  }

  updateIndicatorSeriesPoint(id: string, point: IndicatorDataPoint | null): void {
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
      this.chartManager.updateSeriesPoint(seriesKey, { time, value });
    }
  }

  removeIndicatorSeries(id: string): void {
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
      if (indicator.paneHtmlElement === null) {
        const paneHtmlElement = await this.chartManager.getPaneHtmlElement(indicator.paneIndex);
        this.indicatorsStore.updateIndicatorPaneElement(indicator._id, paneHtmlElement);
      }
    }
  }

  destroy(): void {
    const allIndicatorIds = Array.from(this.indicatorsStore.indicators.keys());

    for (const id of allIndicatorIds) {
      this.removeIndicatorSeriesAndData(id);
    }

    this.indicatorsStore.clear();
  }
}
