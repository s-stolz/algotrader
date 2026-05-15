import { describe, expect, it } from 'vitest';

import {
  isCandle,
  isCandleUpdateMessage,
  isIndicatorResponse,
  isIndicatorUpdateMessage,
  isMarket,
  isStoredCurrentMarket,
  isStoredCurrentTimeframe,
} from '@/types/contracts';

describe('shared frontend contract validators', () => {
  it('accepts representative valid API and browser state payloads', () => {
    expect(isMarket({
      symbol_id: 1,
      symbol: 'EURUSD',
      exchange: 'FX',
      market_type: 'forex',
      min_move: 0.00001,
      timezone: 'UTC',
    })).toBe(true);

    expect(isCandle({
      timestamp_ms: 1_700_000_000_000,
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      volume: 100,
    })).toBe(true);

    expect(isStoredCurrentMarket({
      symbol: 'EURUSD',
      exchange: 'FX',
      market_type: 'forex',
      min_move: 0.00001,
      symbol_id: 1,
    })).toBe(true);

    expect(isStoredCurrentTimeframe({ label: 'M5', value: 'M5' })).toBe(true);
  });

  it('rejects invalid external payloads', () => {
    expect(isMarket({ symbol: 'EURUSD' })).toBe(false);
    expect(isCandle({
      timestamp_ms: 1_700_000_000_000,
      open: 1,
      high: 0.25,
      low: 0.5,
      close: 1.5,
      volume: 100,
    })).toBe(false);
    expect(isStoredCurrentMarket({ symbol: 42 })).toBe(false);
    expect(isStoredCurrentTimeframe({ label: '1 minute', value: 'NOPE' })).toBe(false);
  });

  it('validates WebSocket candle and indicator messages', () => {
    expect(isCandleUpdateMessage({
      type: 'candleUpdate',
      symbol: 'EURUSD',
      timeframe: 'M1',
      timestamp_ms: 1_700_000_000_000,
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      volume: 10,
    })).toBe(true);

    expect(isIndicatorUpdateMessage({
      type: 'indicatorUpdate',
      clientIndicatorId: 'client-1',
      streamId: 'stream-1',
      symbol: 'EURUSD',
      timeframe: 'M1',
      indicatorId: 1,
      timestamp_ms: 1_700_000_000_000,
      values: { sma: 1.2 },
    })).toBe(true);

    expect(isCandleUpdateMessage({ type: 'candleUpdate', symbol: 'EURUSD' })).toBe(false);
    expect(isIndicatorUpdateMessage({
      type: 'indicatorUpdate',
      clientIndicatorId: 'client-1',
      values: null,
    })).toBe(false);
  });

  it('validates indicator response contracts', () => {
    expect(isIndicatorResponse({
      data: {
        indicator_info: {
          id: 1,
          indicator_id: 'sma',
          name: 'SMA',
          overlay: true,
          inputs: [],
          outputs: { sma: { type: 'line' } },
          parameters: {},
        },
        indicator_data: [{ timestamp_ms: 1_700_000_000_000, sma: 1.2 }],
      },
    })).toBe(true);

    expect(isIndicatorResponse({
      data: {
        indicator_info: { id: 1, name: 'SMA' },
        indicator_data: [{ sma: 1.2 }],
      },
    })).toBe(false);
  });
});
