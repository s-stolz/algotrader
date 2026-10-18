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

export interface ChartProtectiveLineSegment {
  id: string;
  startTime: Time;
  endTime: Time;
  price: number;
  color: string;
  lineWidth?: number;
}

const DEFAULT_LINE_WIDTH = 2;
const EMPTY_PANE_VIEWS: readonly IPrimitivePaneView[] = [];

type CoordinateResolver<T> = (value: T) => Coordinate | null;

function alignStrokeCoordinate(value: Coordinate): number {
  return Math.round(Number(value)) + 0.5;
}

class ProtectiveLinesPaneRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly segments: readonly ChartProtectiveLineSegment[],
    private readonly timeToCoordinate: CoordinateResolver<Time>,
    private readonly priceToCoordinate: CoordinateResolver<number>,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useMediaCoordinateSpace(({ context }) => {
      context.save();
      context.lineCap = 'butt';

      for (const segment of this.segments) {
        const startX = this.timeToCoordinate(segment.startTime);
        const endX = this.timeToCoordinate(segment.endTime);
        const y = this.priceToCoordinate(segment.price);

        if (startX === null || endX === null || y === null) {
          continue;
        }

        context.beginPath();
        context.strokeStyle = segment.color;
        context.lineWidth = segment.lineWidth ?? DEFAULT_LINE_WIDTH;
        context.moveTo(alignStrokeCoordinate(startX), alignStrokeCoordinate(y));
        context.lineTo(alignStrokeCoordinate(endX), alignStrokeCoordinate(y));
        context.stroke();
      }

      context.restore();
    });
  }
}

class ProtectiveLinesPaneView implements IPrimitivePaneView {
  constructor(private readonly primitive: ProtectiveLinesPrimitive) {}

  zOrder(): PrimitivePaneViewZOrder {
    return 'top';
  }

  renderer(): IPrimitivePaneRenderer | null {
    return this.primitive.createRenderer();
  }
}

export class ProtectiveLinesPrimitive implements ISeriesPrimitive<Time> {
  private readonly paneView = new ProtectiveLinesPaneView(this);
  private readonly paneViewsList: readonly IPrimitivePaneView[] = [this.paneView];
  private attachedParams: SeriesAttachedParameter<Time, SeriesType> | null = null;
  private segments: ChartProtectiveLineSegment[];

  constructor(segments: readonly ChartProtectiveLineSegment[] = []) {
    this.segments = [...segments];
  }

  setSegments(segments: readonly ChartProtectiveLineSegment[]): void {
    this.segments = [...segments];
    this.attachedParams?.requestUpdate();
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.segments.length > 0 ? this.paneViewsList : EMPTY_PANE_VIEWS;
  }

  autoscaleInfo(startTimePoint: Logical, endTimePoint: Logical): AutoscaleInfo | null {
    if (!this.attachedParams || this.segments.length === 0) {
      return null;
    }

    const prices = this.segments
      .filter((segment) => this.segmentIntersectsLogicalRange(segment, startTimePoint, endTimePoint))
      .map((segment) => segment.price);

    if (prices.length === 0) {
      return null;
    }

    return {
      priceRange: {
        minValue: Math.min(...prices),
        maxValue: Math.max(...prices),
      },
    };
  }

  attached(param: SeriesAttachedParameter<Time, SeriesType>): void {
    this.attachedParams = param;
  }

  detached(): void {
    this.attachedParams = null;
  }

  createRenderer(): IPrimitivePaneRenderer | null {
    if (!this.attachedParams || this.segments.length === 0) {
      return null;
    }

    return new ProtectiveLinesPaneRenderer(
      this.segments,
      (time) => this.timeToCoordinate(time),
      (price) => this.attachedParams?.series.priceToCoordinate(price) ?? null,
    );
  }

  private timeToCoordinate(time: Time): Coordinate | null {
    const timeScale = this.attachedParams?.chart.timeScale();
    if (!timeScale) {
      return null;
    }

    const exactCoordinate = timeScale.timeToCoordinate(time);
    if (exactCoordinate !== null) {
      return exactCoordinate;
    }

    const nearestIndex = timeScale.timeToIndex(time, true);
    return nearestIndex === null
      ? null
      : timeScale.logicalToCoordinate(nearestIndex as unknown as Logical);
  }

  private segmentIntersectsLogicalRange(
    segment: ChartProtectiveLineSegment,
    startTimePoint: Logical,
    endTimePoint: Logical,
  ): boolean {
    const startIndex = this.attachedParams?.chart.timeScale().timeToIndex(segment.startTime, true);
    const endIndex = this.attachedParams?.chart.timeScale().timeToIndex(segment.endTime, true);

    if (startIndex === null || startIndex === undefined || endIndex === null || endIndex === undefined) {
      return false;
    }

    return Math.max(Number(startIndex), Number(endIndex)) >= Number(startTimePoint) &&
      Math.min(Number(startIndex), Number(endIndex)) <= Number(endTimePoint);
  }
}
