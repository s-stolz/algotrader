import type { ChartSeriesInfo } from './ChartManager';
import type { ChartMeasurementOverlayModel } from './measurementOverlay';
import { MeasurementOverlayPrimitive } from './measurementOverlayPrimitive';

export function setMeasurementOverlayPrimitive(
  series: Map<string, ChartSeriesInfo>,
  primitives: Map<string, MeasurementOverlayPrimitive>,
  key: string,
  model: ChartMeasurementOverlayModel,
): boolean {
  const seriesInfo = series.get(key);
  if (!seriesInfo) {
    return false;
  }

  try {
    const primitive = primitives.get(key);
    if (primitive) {
      primitive.setModel(model);
      return true;
    }

    const nextPrimitive = new MeasurementOverlayPrimitive(model);
    seriesInfo.series.attachPrimitive(nextPrimitive);
    primitives.set(key, nextPrimitive);
    return true;
  } catch (error) {
    console.error(`Failed to set measurement overlay for series '${key}':`, error);
    return false;
  }
}

export function clearMeasurementOverlayPrimitive(
  series: Map<string, ChartSeriesInfo>,
  primitives: Map<string, MeasurementOverlayPrimitive>,
  key: string,
): boolean {
  const primitive = primitives.get(key);
  const seriesInfo = series.get(key);

  if (!primitive || !seriesInfo) {
    return false;
  }

  try {
    seriesInfo.series.detachPrimitive(primitive);
    primitives.delete(key);
    return true;
  } catch (error) {
    console.error(`Failed to clear measurement overlay for series '${key}':`, error);
    return false;
  }
}
