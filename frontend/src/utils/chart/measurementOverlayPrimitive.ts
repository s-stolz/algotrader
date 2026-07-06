import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import type {
  AutoscaleInfo,
  Coordinate,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  Logical,
  PrimitivePaneViewZOrder,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from 'lightweight-charts';

import type {
  ChartMeasurementOverlayModel,
  MeasurementOverlayDirection,
} from './measurementOverlay';

interface MeasurementOverlayStyle {
  fill: string;
  border: string;
  labelBackground: string;
  labelText: string;
}

const EMPTY_PANE_VIEWS: readonly IPrimitivePaneView[] = [];
const MIN_BOX_SIZE = 1;
const LABEL_FONT = '12px sans-serif';
const LABEL_HEIGHT = 24;
const LABEL_HORIZONTAL_PADDING = 8;
const LABEL_OFFSET = 8;

const MEASUREMENT_OVERLAY_STYLES: Record<MeasurementOverlayDirection, MeasurementOverlayStyle> = {
  positive: {
    fill: 'rgba(22, 163, 74, 0.18)',
    border: '#16a34a',
    labelBackground: 'rgba(22, 163, 74, 0.95)',
    labelText: '#f0fdf4',
  },
  negative: {
    fill: 'rgba(220, 38, 38, 0.18)',
    border: '#dc2626',
    labelBackground: 'rgba(220, 38, 38, 0.95)',
    labelText: '#fef2f2',
  },
  neutral: {
    fill: 'rgba(148, 163, 184, 0.18)',
    border: '#94a3b8',
    labelBackground: 'rgba(51, 65, 85, 0.95)',
    labelText: '#f8fafc',
  },
};

type CoordinateResolver<T> = (value: T) => Coordinate | null;

function alignStrokeCoordinate(value: number): number {
  return Math.round(value) + 0.5;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

class MeasurementOverlayPaneRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly model: ChartMeasurementOverlayModel,
    private readonly logicalToCoordinate: CoordinateResolver<number>,
    private readonly priceToCoordinate: CoordinateResolver<number>,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useMediaCoordinateSpace(({ context, mediaSize }) => {
      const leftX = this.logicalToCoordinate(this.model.box.leftLogical);
      const rightX = this.logicalToCoordinate(this.model.box.rightLogical);
      const topY = this.priceToCoordinate(this.model.box.topPrice);
      const bottomY = this.priceToCoordinate(this.model.box.bottomPrice);
      const endpointX = this.logicalToCoordinate(this.model.box.endpointLogical);
      const endpointY = this.priceToCoordinate(this.model.box.endpointPrice);

      if (
        leftX === null ||
        rightX === null ||
        topY === null ||
        bottomY === null ||
        endpointX === null ||
        endpointY === null
      ) {
        return;
      }

      const style = MEASUREMENT_OVERLAY_STYLES[this.model.direction];
      const left = Math.min(Number(leftX), Number(rightX));
      const top = Math.min(Number(topY), Number(bottomY));
      const width = Math.max(MIN_BOX_SIZE, Math.abs(Number(rightX) - Number(leftX)));
      const height = Math.max(MIN_BOX_SIZE, Math.abs(Number(bottomY) - Number(topY)));

      context.save();
      context.fillStyle = style.fill;
      context.fillRect(left, top, width, height);
      context.strokeStyle = style.border;
      context.lineWidth = 1;
      context.strokeRect(
        alignStrokeCoordinate(left),
        alignStrokeCoordinate(top),
        width,
        height,
      );
      this.drawLabel(
        context,
        mediaSize.width,
        mediaSize.height,
        Number(endpointX),
        Number(endpointY),
        style,
      );
      context.restore();
    });
  }

  private drawLabel(
    context: CanvasRenderingContext2D,
    paneWidth: number,
    paneHeight: number,
    endpointX: number,
    endpointY: number,
    style: MeasurementOverlayStyle,
  ): void {
    context.font = LABEL_FONT;
    context.textBaseline = 'middle';

    const textWidth = Math.ceil(context.measureText(this.model.label.text).width);
    const labelWidth = textWidth + LABEL_HORIZONTAL_PADDING * 2;
    const maxX = Math.max(0, paneWidth - labelWidth);
    const maxY = Math.max(0, paneHeight - LABEL_HEIGHT);
    const preferredX = endpointX + LABEL_OFFSET;
    const preferredY = endpointY - LABEL_HEIGHT - LABEL_OFFSET;
    const flippedX = endpointX - labelWidth - LABEL_OFFSET;
    const flippedY = endpointY + LABEL_OFFSET;
    const x = clamp(
      preferredX + labelWidth > paneWidth ? flippedX : preferredX,
      0,
      maxX,
    );
    const y = clamp(
      preferredY < 0 ? flippedY : preferredY,
      0,
      maxY,
    );

    context.fillStyle = style.labelBackground;
    context.fillRect(x, y, labelWidth, LABEL_HEIGHT);
    context.fillStyle = style.labelText;
    context.fillText(
      this.model.label.text,
      x + LABEL_HORIZONTAL_PADDING,
      y + LABEL_HEIGHT / 2,
    );
  }
}

class MeasurementOverlayPaneView implements IPrimitivePaneView {
  constructor(private readonly primitive: MeasurementOverlayPrimitive) {}

  zOrder(): PrimitivePaneViewZOrder {
    return 'top';
  }

  renderer(): IPrimitivePaneRenderer | null {
    return this.primitive.createRenderer();
  }
}

export class MeasurementOverlayPrimitive implements ISeriesPrimitive<Time> {
  private readonly paneView = new MeasurementOverlayPaneView(this);
  private readonly paneViewsList: readonly IPrimitivePaneView[] = [this.paneView];
  private attachedParams: SeriesAttachedParameter<Time, SeriesType> | null = null;
  private model: ChartMeasurementOverlayModel | null;

  constructor(model: ChartMeasurementOverlayModel | null = null) {
    this.model = model;
  }

  setModel(model: ChartMeasurementOverlayModel): void {
    this.model = model;
    this.attachedParams?.requestUpdate();
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.model ? this.paneViewsList : EMPTY_PANE_VIEWS;
  }

  autoscaleInfo(_startTimePoint: Logical, _endTimePoint: Logical): AutoscaleInfo | null {
    return null;
  }

  attached(param: SeriesAttachedParameter<Time, SeriesType>): void {
    this.attachedParams = param;
  }

  detached(): void {
    this.attachedParams = null;
  }

  createRenderer(): IPrimitivePaneRenderer | null {
    if (!this.attachedParams || !this.model) {
      return null;
    }

    return new MeasurementOverlayPaneRenderer(
      this.model,
      (logical) => this.logicalToCoordinate(logical),
      (price) => this.attachedParams?.series.priceToCoordinate(price) ?? null,
    );
  }

  private logicalToCoordinate(logical: number): Coordinate | null {
    const timeScale = this.attachedParams?.chart.timeScale();
    return timeScale?.logicalToCoordinate(logical as Logical) ?? null;
  }
}
