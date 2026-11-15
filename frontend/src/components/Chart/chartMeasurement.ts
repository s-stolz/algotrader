import type { ChartInfrastructure } from '@/utils/chart';
import { buildMeasurementOverlayModel } from '@/utils/chart/measurementOverlay';
import type { ChartInteractionMode } from './chartInteractionMode';

interface MeasurementEndpoint {
  price: number;
  logical: number;
}
interface MeasurementDragState {
  anchorPrice: number;
  anchorLogical: number;
  minMove: number;
}
interface MeasurementOptions {
  infrastructure: ChartInfrastructure;
  getMode: () => ChartInteractionMode;
  getMinMove: () => number | null;
  hasCandles: () => boolean;
  hasSeries: () => boolean;
}

export function createChartMeasurement({
  infrastructure,
  getMode,
  getMinMove,
  hasCandles,
  hasSeries,
}: MeasurementOptions) {
  let measurementPaneElement: HTMLElement | null = null;
  let activeMeasurement: MeasurementDragState | null = null;
  function setMeasurementPaneElement(paneElement: HTMLElement | null): void {
    if (measurementPaneElement === paneElement) {
      return;
    }

    if (measurementPaneElement) {
      measurementPaneElement.removeEventListener(
        'pointerdown',
        onMeasurementPointerDown,
        true,
      );
    }

    measurementPaneElement = paneElement;

    if (paneElement) {
      paneElement.addEventListener('pointerdown', onMeasurementPointerDown, {
        capture: true,
      });
    }
  }

  function applyInteractionMode(): void {
    infrastructure.setMouseDragScrollEnabled(getMode() !== 'measure');

    if (getMode() !== 'measure') {
      cancelMeasurementOverlay();
    }
  }

  function onMeasurementPointerDown(event: PointerEvent): void {
    if (!canStartMeasurement(event)) {
      return;
    }

    const endpoint = resolveMeasurementEndpoint(event);
    if (!endpoint) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    activeMeasurement = {
      anchorPrice: endpoint.price,
      anchorLogical: endpoint.logical,
      minMove: getMinMove() ?? 0,
    };
    addMeasurementWindowListeners();
    updateMeasurementOverlay(endpoint);
  }

  function onMeasurementPointerMove(event: PointerEvent): void {
    if (!activeMeasurement) {
      return;
    }

    if (event.buttons !== 1) {
      cancelMeasurementOverlay();
      return;
    }

    const endpoint = resolveMeasurementEndpoint(event);
    if (endpoint) {
      updateMeasurementOverlay(endpoint);
    }
  }

  function onMeasurementPointerRelease(): void {
    cancelMeasurementOverlay();
  }

  function onMeasurementKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      cancelMeasurementOverlay();
    }
  }

  function onMeasurementWindowBlur(): void {
    cancelMeasurementOverlay();
  }

  function canStartMeasurement(event: PointerEvent): boolean {
    return (
      getMode() === 'measure' &&
      event.button === 0 &&
      event.buttons === 1 &&
      activeMeasurement === null &&
      hasCandles() &&
      hasSeries() &&
      measurementPaneElement !== null
    );
  }

  function resolveMeasurementEndpoint(
    event: PointerEvent,
  ): MeasurementEndpoint | null {
    const paneElement = measurementPaneElement;
    if (!paneElement) {
      return null;
    }

    const paneRect = paneElement.getBoundingClientRect();
    const x = event.clientX - paneRect.left;
    const y = event.clientY - paneRect.top;
    const price = infrastructure.coordinateToCandlestickPrice(y);
    const logical = infrastructure.coordinateToLogical(x);

    if (
      price === null ||
      logical === null ||
      !Number.isFinite(price) ||
      !Number.isFinite(logical)
    ) {
      return null;
    }

    return { price, logical };
  }

  function updateMeasurementOverlay(endpoint: MeasurementEndpoint): void {
    const measurement = activeMeasurement;
    if (!measurement) {
      return;
    }

    infrastructure.setCandlestickMeasurementOverlay(
      buildMeasurementOverlayModel({
        anchorPrice: measurement.anchorPrice,
        endpointPrice: endpoint.price,
        anchorLogical: measurement.anchorLogical,
        endpointLogical: endpoint.logical,
        minMove: measurement.minMove,
      }),
    );
  }

  function addMeasurementWindowListeners(): void {
    window.addEventListener('pointermove', onMeasurementPointerMove);
    window.addEventListener('pointerup', onMeasurementPointerRelease);
    window.addEventListener('pointercancel', onMeasurementPointerRelease);
    window.addEventListener('keydown', onMeasurementKeyDown);
    window.addEventListener('blur', onMeasurementWindowBlur);
  }

  function removeMeasurementWindowListeners(): void {
    window.removeEventListener('pointermove', onMeasurementPointerMove);
    window.removeEventListener('pointerup', onMeasurementPointerRelease);
    window.removeEventListener('pointercancel', onMeasurementPointerRelease);
    window.removeEventListener('keydown', onMeasurementKeyDown);
    window.removeEventListener('blur', onMeasurementWindowBlur);
  }

  function cancelMeasurementOverlay(): void {
    if (!activeMeasurement) {
      return;
    }

    activeMeasurement = null;
    removeMeasurementWindowListeners();
    infrastructure.clearCandlestickMeasurementOverlay();
  }

  return {
    setMeasurementPaneElement,
    applyInteractionMode,
    dispose() {
      cancelMeasurementOverlay();
      setMeasurementPaneElement(null);
    },
  };
}
