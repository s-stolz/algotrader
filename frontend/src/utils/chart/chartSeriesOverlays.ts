import {
  ProtectiveLinesPrimitive,
  type ChartProtectiveLineSegment,
} from './protectiveLinesPrimitive';
import type { ChartMeasurementOverlayModel } from './measurementOverlay';
import {
  clearMeasurementOverlayPrimitive,
  setMeasurementOverlayPrimitive,
} from './measurementOverlayLifecycle';
import type { MeasurementOverlayPrimitive } from './measurementOverlayPrimitive';
import {
  createSeriesMarkers,
  type ISeriesMarkersPluginApi,
  type Time,
} from 'lightweight-charts';
import type { ChartSeriesInfo, ChartSeriesMarker } from './ChartManager';

export class ChartSeriesOverlays {
  private readonly markerPlugins = new Map<
    string,
    ISeriesMarkersPluginApi<Time>
  >();
  private readonly protectiveLinePrimitives = new Map<
    string,
    ProtectiveLinesPrimitive
  >();
  private readonly measurementOverlayPrimitives = new Map<
    string,
    MeasurementOverlayPrimitive
  >();

  constructor(private readonly series: Map<string, ChartSeriesInfo>) {}

  setSeriesMarkers(
    key: string,
    markers: readonly ChartSeriesMarker[],
  ): boolean {
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

      this.markerPlugins.set(
        key,
        createSeriesMarkers(seriesInfo.series, nextMarkers),
      );
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
      console.error(
        `Failed to set protective lines for series '${key}':`,
        error,
      );
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
      console.error(
        `Failed to clear protective lines for series '${key}':`,
        error,
      );
      return false;
    }
  }

  setSeriesMeasurementOverlay(
    key: string,
    model: ChartMeasurementOverlayModel,
  ): boolean {
    return setMeasurementOverlayPrimitive(
      this.series,
      this.measurementOverlayPrimitives,
      key,
      model,
    );
  }

  clearSeriesMeasurementOverlay(key: string): boolean {
    return clearMeasurementOverlayPrimitive(
      this.series,
      this.measurementOverlayPrimitives,
      key,
    );
  }

  clearAll(): void {
    for (const key of Array.from(this.markerPlugins.keys())) {
      this.clearSeriesMarkers(key);
    }

    for (const key of Array.from(this.protectiveLinePrimitives.keys())) {
      this.clearSeriesProtectiveLines(key);
    }

    for (const key of Array.from(this.measurementOverlayPrimitives.keys())) {
      this.clearSeriesMeasurementOverlay(key);
    }
  }
}
