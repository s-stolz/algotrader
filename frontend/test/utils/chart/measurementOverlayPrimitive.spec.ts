import { describe, expect, it, vi } from 'vitest';

import { buildMeasurementOverlayModel } from '@/utils/chart/measurementOverlay';
import { MeasurementOverlayPrimitive } from '@/utils/chart/measurementOverlayPrimitive';

describe('MeasurementOverlayPrimitive', () => {
  it('draws the overlay box and label from logical slot centers and exact endpoint prices', () => {
    const model = buildMeasurementOverlayModel({
      anchorPrice: 100,
      endpointPrice: 110,
      anchorLogical: 1,
      endpointLogical: 4,
      minMove: 0.01,
    });
    const logicalToCoordinate = vi.fn((logical: number) => {
      const coordinates = new Map([
        [1, 10],
        [4, 40],
      ]);
      return coordinates.get(logical) ?? null;
    });
    const priceToCoordinate = vi.fn((price: number) => {
      const coordinates = new Map([
        [110, 20],
        [100, 70],
      ]);
      return coordinates.get(price) ?? null;
    });
    const requestUpdate = vi.fn();
    const fillStyles: string[] = [];
    const strokeStyles: string[] = [];
    const context = {
      save: vi.fn(),
      restore: vi.fn(),
      fillRect: vi.fn(),
      strokeRect: vi.fn(),
      fillText: vi.fn(),
      measureText: vi.fn(() => ({ width: 120 })),
      set fillStyle(value: string) {
        fillStyles.push(value);
      },
      set strokeStyle(value: string) {
        strokeStyles.push(value);
      },
      set lineWidth(_value: number) {},
      set font(_value: string) {},
      set textBaseline(_value: CanvasTextBaseline) {},
    } as unknown as CanvasRenderingContext2D;
    const target = {
      useMediaCoordinateSpace: vi.fn((callback) => {
        callback({
          context,
          mediaSize: { width: 180, height: 120 },
        });
      }),
    };
    const primitive = new MeasurementOverlayPrimitive(model);

    primitive.attached({
      requestUpdate,
      chart: {
        timeScale: () => ({ logicalToCoordinate }),
      },
      series: { priceToCoordinate },
    } as never);

    const renderer = primitive.paneViews()[0]?.renderer();
    renderer?.draw(target as never);

    expect(logicalToCoordinate).toHaveBeenCalledWith(1);
    expect(logicalToCoordinate).toHaveBeenCalledWith(4);
    expect(priceToCoordinate).toHaveBeenCalledWith(110);
    expect(priceToCoordinate).toHaveBeenCalledWith(100);
    expect(fillStyles).toContain('rgba(22, 163, 74, 0.18)');
    expect(strokeStyles).toContain('#16a34a');
    expect(context.fillRect).toHaveBeenNthCalledWith(1, 10, 20, 30, 50);
    expect(context.strokeRect).toHaveBeenCalledWith(10.5, 20.5, 30, 50);
    expect(context.fillText).toHaveBeenCalledWith(
      '+10.00 (+10.00%) 4 candles',
      expect.any(Number),
      expect.any(Number),
    );

    primitive.setModel({
      ...model,
      direction: 'neutral',
    });

    expect(requestUpdate).toHaveBeenCalled();
  });
});
