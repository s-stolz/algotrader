import { describe, expect, it, vi } from 'vitest';
import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import type {
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from 'lightweight-charts';
import { ProtectiveLinesPrimitive } from '@/utils/chart/protectiveLinesPrimitive';
import { buildBacktestProtectiveLineSegments } from '@/utils/chart/backtestOverlay';
import type { BacktestClosedTrade } from '@/types/backtesterContracts';

const day = 86400000;
const trade: BacktestClosedTrade = {
  sequence: 0,
  trade_id: 'intraday',
  symbol: 'TEST',
  trade_direction: 'long',
  quantity: 1,
  entry_timestamp_ms: day + 60000,
  exit_timestamp_ms: day + 120000,
  entry_price: 100,
  exit_price: 102,
  realized_pnl: 2,
  fees: 0,
  exit_reason: 'take_profit',
  stop_loss_price: 99,
  take_profit_price: 102,
};

function fixture(
  exitTime = trade.exit_timestamp_ms,
  barSpacing = 10,
  dashed = false,
) {
  const segments = buildBacktestProtectiveLineSegments(
    [{ ...trade, exit_timestamp_ms: exitTime }],
    [day, day * 2],
  );
  segments[0].dashed = dashed;
  const primitive = new ProtectiveLinesPrimitive(segments);
  const context = {
    setLineDash: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    stroke: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
  };
  const target = {
    useMediaCoordinateSpace: (draw: (scope: unknown) => void) =>
      draw({ context }),
  };
  const priceToCoordinate = vi.fn((price: number) => 200 - price);
  primitive.attached({
    chart: {
      timeScale: () => ({
        timeToCoordinate: (time: number) => (time === day / 1000 ? 100 : 120),
        options: () => ({ barSpacing }),
      }),
    },
    series: { priceToCoordinate },
    requestUpdate: vi.fn(),
  } as unknown as SeriesAttachedParameter<Time, SeriesType>);
  primitive
    .paneViews()[0]
    ?.renderer()
    ?.draw(target as CanvasRenderingTarget2D);
  return { context, segments, priceToCoordinate };
}

describe('protective price lines', () => {
  it('draws pending dashes and resets the next line to solid', () => {
    const { context } = fixture(undefined, 10, true);
    expect(context.setLineDash.mock.calls).toEqual([[[6, 4]], [[]]]);
  });

  it.each([2, 10, 30])(
    'renders visible levels within one candle at spacing %s',
    (spacing) => {
      const { context, segments, priceToCoordinate } = fixture(
        undefined,
        spacing,
      );
      expect(segments[0].startTime).toBe(segments[0].endTime);
      expect(context.stroke).toHaveBeenCalledTimes(2);
      for (let i = 0; i < 2; i++) {
        const start = context.moveTo.mock.calls[i];
        const end = context.lineTo.mock.calls[i];
        expect(end[0] - start[0]).toBeGreaterThanOrEqual(6);
        expect((start[0] + end[0]) / 2).toBe(100.5);
        expect(start[1]).toBe(end[1]);
      }
      expect(priceToCoordinate.mock.calls).toEqual([[99], [102]]);
    },
  );

  it('preserves the span of trades crossing candle boundaries', () => {
    const { context } = fixture(day * 2 + 60000);
    expect(context.moveTo.mock.calls).toEqual([
      [100.5, 101.5],
      [100.5, 98.5],
    ]);
    expect(context.lineTo.mock.calls).toEqual([
      [120.5, 101.5],
      [120.5, 98.5],
    ]);
  });
});
