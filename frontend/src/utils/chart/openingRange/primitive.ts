import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  Logical,
  SeriesAttachedParameter,
  SeriesType,
  Time,
  UTCTimestamp,
} from 'lightweight-charts';
import type { RangeBox, RangeStyle } from './model';

export class OpeningRangePrimitive implements ISeriesPrimitive<Time> {
  private attachment: SeriesAttachedParameter<Time, SeriesType> | null = null;
  private readonly view: IPrimitivePaneView = {
    zOrder: () => 'bottom',
    renderer: () => this.renderer(),
  };

  constructor(
    private boxes: RangeBox[],
    private style: RangeStyle,
  ) {}

  setData(boxes: RangeBox[], style: RangeStyle): void {
    this.boxes = boxes;
    this.style = style;
    this.attachment?.requestUpdate();
  }

  attached(attachment: SeriesAttachedParameter<Time, SeriesType>): void {
    this.attachment = attachment;
  }

  detached(): void {
    this.attachment = null;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.boxes.length ? [this.view] : [];
  }

  private renderer(): IPrimitivePaneRenderer | null {
    const attachment = this.attachment;
    if (!attachment) return null;
    return {
      draw: (target: CanvasRenderingTarget2D) => {
        target.useMediaCoordinateSpace(({ context }) => {
          const scale = attachment.chart.timeScale();
          const x = (time: number) => {
            const exact = scale.timeToCoordinate(time as UTCTimestamp);
            if (exact !== null) return exact;
            const index = scale.timeToIndex(time as UTCTimestamp, true);
            return index === null
              ? null
              : scale.logicalToCoordinate(Number(index) as Logical);
          };
          context.save();
          context.strokeStyle = this.style.color;
          context.fillStyle = this.style.fillColor;
          context.lineWidth = this.style.lineWidth;
          for (const box of this.boxes) {
            const left = x(box.start);
            const right = x(box.end);
            const top = attachment.series.priceToCoordinate(box.high);
            const bottom = attachment.series.priceToCoordinate(box.low);
            if (
              left === null ||
              right === null ||
              top === null ||
              bottom === null
            )
              continue;
            context.fillRect(left, top, right - left, bottom - top);
            context.strokeRect(left, top, right - left, bottom - top);
            const extension = x(box.extensionEnd);
            if (!box.ready || !this.style.showExtensions || extension === null)
              continue;
            context.beginPath();
            context.moveTo(right, top);
            context.lineTo(extension, top);
            context.moveTo(right, bottom);
            context.lineTo(extension, bottom);
            context.stroke();
          }
          context.restore();
        });
      },
    };
  }
}
