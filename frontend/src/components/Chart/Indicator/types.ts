import type { StoreIndicator } from '@/stores/indicatorsStore';
import type { ChartSeriesOptions } from '@/utils/chart';

export interface IndicatorStyleUpdatePayload {
  outputKey: string;
  styles: ChartSeriesOptions;
}

export interface IndicatorManagerDependency {
  addIndicatorSeries(id: string): Promise<void>;
  refreshIndicatorSeries(id: string): void;
  removeIndicatorSeriesAndData(id: string): void;
  updateMissingPaneHtmlElements(): Promise<void>;
  updateIndicatorStyles(id: string, outputKey: string, styles: ChartSeriesOptions): boolean;
}

export type IndicatorInstance = StoreIndicator;
