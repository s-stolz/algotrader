import { marketPricePrecision } from './priceFormatting';

export type MeasurementOverlayDirection = 'positive' | 'negative' | 'neutral';

export interface MeasurementOverlayInput {
  anchorPrice: number;
  endpointPrice: number;
  anchorLogical: number;
  endpointLogical: number;
  minMove: number;
}

export interface ChartMeasurementOverlayBoxModel {
  anchorPrice: number;
  endpointPrice: number;
  topPrice: number;
  bottomPrice: number;
  anchorLogical: number;
  endpointLogical: number;
  leftLogical: number;
  rightLogical: number;
}

export interface ChartMeasurementOverlayLabelModel {
  priceDelta: string;
  percentDelta: string;
  candleCount: string;
  text: string;
}

export interface ChartMeasurementOverlayModel {
  priceDelta: number;
  percentDelta: number | null;
  candleCount: number;
  direction: MeasurementOverlayDirection;
  box: ChartMeasurementOverlayBoxModel;
  label: ChartMeasurementOverlayLabelModel;
}

export function buildMeasurementOverlayModel(
  input: MeasurementOverlayInput,
): ChartMeasurementOverlayModel {
  const anchorLogical = Math.round(input.anchorLogical);
  const endpointLogical = Math.round(input.endpointLogical);
  const priceDelta = input.endpointPrice - input.anchorPrice;
  const percentDelta =
    input.anchorPrice === 0 ? null : (priceDelta / input.anchorPrice) * 100;
  const candleCount = Math.abs(endpointLogical - anchorLogical) + 1;
  const direction = measurementDirection(priceDelta);
  const priceDeltaText = formatSignedNumber(
    priceDelta,
    marketPricePrecision(input.minMove),
  );
  const percentDeltaText =
    percentDelta === null ? 'N/A' : `${formatSignedNumber(percentDelta, 2)}%`;
  const candleCountText = `${candleCount} ${candleCount === 1 ? 'candle' : 'candles'}`;

  return {
    priceDelta,
    percentDelta,
    candleCount,
    direction,
    box: {
      anchorPrice: input.anchorPrice,
      endpointPrice: input.endpointPrice,
      topPrice: Math.max(input.anchorPrice, input.endpointPrice),
      bottomPrice: Math.min(input.anchorPrice, input.endpointPrice),
      anchorLogical,
      endpointLogical,
      leftLogical: Math.min(anchorLogical, endpointLogical),
      rightLogical: Math.max(anchorLogical, endpointLogical),
    },
    label: {
      priceDelta: priceDeltaText,
      percentDelta: percentDeltaText,
      candleCount: candleCountText,
      text: `${priceDeltaText} (${percentDeltaText}) ${candleCountText}`,
    },
  };
}

function measurementDirection(value: number): MeasurementOverlayDirection {
  if (value > 0) {
    return 'positive';
  }

  if (value < 0) {
    return 'negative';
  }

  return 'neutral';
}

function formatSignedNumber(value: number, precision: number): string {
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(precision)}`;
}
