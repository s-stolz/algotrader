import { describe, expect, it, vi } from 'vitest';
import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import type {
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from 'lightweight-charts';
import { OpeningRangePrimitive } from '@/utils/chart/openingRange/primitive';
import { rangeStyle } from '@/utils/chart/openingRange/model';

const box = {
  start: 1,
  end: 3,
  extensionEnd: 5,
  high: 12,
  low: 8,
  ready: true,
};

function fixture(showExtensions = true) {
  const context = {
    save: vi.fn(),
    restore: vi.fn(),
    fillRect: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
  };
  const target = {
    useMediaCoordinateSpace: (draw: (scope: unknown) => void) =>
      draw({ context }),
  };
  const requestUpdate = vi.fn();
  const primitive = new OpeningRangePrimitive(
    [box],
    rangeStyle({ showExtensions }),
  );
  primitive.attached({
    chart: {
      timeScale: () => ({ timeToCoordinate: (time: number) => time * 10 }),
    },
    series: { priceToCoordinate: (price: number) => 100 - price },
    requestUpdate,
  } as unknown as SeriesAttachedParameter<Time, SeriesType>);
  const draw = () =>
    primitive
      .paneViews()[0]
      ?.renderer()
      ?.draw(target as CanvasRenderingTarget2D);
  return { primitive, context, draw, requestUpdate };
}

describe('opening range drawing', () => {
  it('draws a filled box with two bounded extension lines', () => {
    const { context, draw } = fixture();
    draw();
    expect(context.fillRect).toHaveBeenCalledWith(10, 88, 20, 4);
    expect(context.strokeRect).toHaveBeenCalledWith(10, 88, 20, 4);
    expect(context.moveTo.mock.calls).toEqual([
      [30, 88],
      [30, 92],
    ]);
    expect(context.lineTo.mock.calls).toEqual([
      [50, 88],
      [50, 92],
    ]);
  });

  it('hides extensions without hiding the box and clears on empty data', () => {
    const { primitive, context, draw, requestUpdate } = fixture(false);
    draw();
    expect(context.fillRect).toHaveBeenCalledOnce();
    expect(context.lineTo).not.toHaveBeenCalled();
    primitive.setData([], rangeStyle());
    expect(requestUpdate).toHaveBeenCalledOnce();
    expect(primitive.paneViews()).toEqual([]);
  });

  it('does not extend a developing range or render after detachment', () => {
    const { primitive, context, draw } = fixture();
    primitive.setData([{ ...box, ready: false }], rangeStyle());
    draw();
    expect(context.lineTo).not.toHaveBeenCalled();
    primitive.detached();
    expect(primitive.paneViews()[0].renderer()).toBeNull();
  });
});
