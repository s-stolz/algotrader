import type { StoreIndicator } from '@/stores/indicatorsStore';
import type { ChartSeriesInfo, ManagedSeriesApi } from '../ChartManager';
import { buildRangeBoxes, rangeStyle } from './model';
import { OpeningRangePrimitive } from './primitive';

export class OpeningRangeOverlays {
  private readonly overlays = new Map<
    string,
    {
      series: ManagedSeriesApi;
      primitive: OpeningRangePrimitive;
    }
  >();

  constructor(private readonly series: Map<string, ChartSeriesInfo>) {}

  update(indicator: StoreIndicator): void {
    const series = this.series.get('ohlc')?.series;
    if (!series) return;
    const boxes = buildRangeBoxes(indicator.data);
    const style = rangeStyle(indicator.styles.range_high);
    const existing = this.overlays.get(indicator._id);
    if (existing?.series === series) {
      existing.primitive.setData(boxes, style);
      return;
    }
    this.remove(indicator._id);
    const primitive = new OpeningRangePrimitive(boxes, style);
    series.attachPrimitive(primitive);
    this.overlays.set(indicator._id, { series, primitive });
  }

  remove(id: string): void {
    const overlay = this.overlays.get(id);
    if (!overlay) return;
    overlay.series.detachPrimitive(overlay.primitive);
    this.overlays.delete(id);
  }
}
