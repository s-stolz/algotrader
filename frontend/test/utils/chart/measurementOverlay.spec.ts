import { describe, expect, it } from 'vitest';

import {
  buildMeasurementOverlayModel,
  measurementPricePrecision,
} from '@/utils/chart/measurementOverlay';

describe('measurement overlay model', () => {
  it('builds a positive measurement from raw prices and nearest logical slot centers', () => {
    const model = buildMeasurementOverlayModel({
      anchorPrice: 100,
      endpointPrice: 112.34567,
      anchorLogical: 10.2,
      endpointLogical: 13.6,
      minMove: 0.0001,
    });

    expect(model.priceDelta).toBeCloseTo(12.34567);
    expect(model.percentDelta).toBeCloseTo(12.34567);
    expect(model.candleCount).toBe(5);
    expect(model.direction).toBe('positive');
    expect(model.box).toEqual({
      anchorPrice: 100,
      endpointPrice: 112.34567,
      topPrice: 112.34567,
      bottomPrice: 100,
      anchorLogical: 10,
      endpointLogical: 14,
      leftLogical: 10,
      rightLogical: 14,
    });
    expect(model.label).toEqual({
      priceDelta: '+12.3457',
      percentDelta: '+12.35%',
      candleCount: '5 candles',
      text: '+12.3457 (+12.35%) 5 candles',
    });
  });

  it('keeps vertical direction signed while horizontal drag direction only changes span', () => {
    const leftToRight = buildMeasurementOverlayModel({
      anchorPrice: 200,
      endpointPrice: 190,
      anchorLogical: 8,
      endpointLogical: 11,
      minMove: 0.01,
    });
    const rightToLeft = buildMeasurementOverlayModel({
      anchorPrice: 200,
      endpointPrice: 190,
      anchorLogical: 11,
      endpointLogical: 8,
      minMove: 0.01,
    });

    expect(leftToRight.direction).toBe('negative');
    expect(leftToRight.label.text).toBe('-10.00 (-5.00%) 4 candles');
    expect(rightToLeft.label.text).toBe(leftToRight.label.text);
    expect(rightToLeft.box.leftLogical).toBe(8);
    expect(rightToLeft.box.rightLogical).toBe(11);
  });

  it('formats a zero-span measurement with neutral direction and one candle', () => {
    const model = buildMeasurementOverlayModel({
      anchorPrice: 42,
      endpointPrice: 42,
      anchorLogical: 3.49,
      endpointLogical: 3.49,
      minMove: 0.01,
    });

    expect(model.direction).toBe('neutral');
    expect(model.candleCount).toBe(1);
    expect(model.label.text).toBe('0.00 (0.00%) 1 candle');
    expect(model.box).toEqual(expect.objectContaining({
      topPrice: 42,
      bottomPrice: 42,
      anchorLogical: 3,
      endpointLogical: 3,
      leftLogical: 3,
      rightLogical: 3,
    }));
  });

  it('displays N/A percent for a zero anchor while preserving signed raw price delta', () => {
    const model = buildMeasurementOverlayModel({
      anchorPrice: 0,
      endpointPrice: -1.5,
      anchorLogical: -1,
      endpointLogical: 1,
      minMove: 0.1,
    });

    expect(model.percentDelta).toBeNull();
    expect(model.label.text).toBe('-1.5 (N/A) 3 candles');
  });

  it('uses raw pointer-derived prices before formatting display values', () => {
    const model = buildMeasurementOverlayModel({
      anchorPrice: 10,
      endpointPrice: 10.004,
      anchorLogical: 1,
      endpointLogical: 2,
      minMove: 0.01,
    });

    expect(model.priceDelta).toBeCloseTo(0.004);
    expect(model.percentDelta).toBeCloseTo(0.04);
    expect(model.label.text).toBe('+0.00 (+0.04%) 2 candles');
  });

  it('derives display precision from the active market min move', () => {
    expect(measurementPricePrecision(1)).toBe(0);
    expect(measurementPricePrecision(0.01)).toBe(2);
    expect(measurementPricePrecision(0.00001)).toBe(5);
    expect(measurementPricePrecision(1e-8)).toBe(8);
  });
});
