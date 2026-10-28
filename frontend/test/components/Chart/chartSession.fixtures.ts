import { vi } from 'vitest';

import {
  type ChartSessionKey,
  type ChartSessionSubscriptionsAdapter,
} from '@/components/Chart/chartSession';
import type { CandleUpdateMessage, ChartCandle } from '@/types/contracts';

function keyLabel(key: ChartSessionKey): string {
  return `${key.symbol}:${key.exchange ?? ''}:${key.timeframe}`;
}

export function chartCandle(timestampMs: number, close = 1.5): ChartCandle {
  return {
    timestamp_ms: timestampMs,
    time: Math.floor(timestampMs / 1000),
    open: 1,
    high: 2,
    low: 0.5,
    close,
    volume: 10,
  };
}

export function candleUpdate(
  timestampMs: number,
  close = 1.5,
): CandleUpdateMessage {
  return {
    type: 'candleUpdate',
    symbol: 'EURUSD',
    timeframe: 'M5',
    timestamp_ms: timestampMs,
    open: 1,
    high: 2,
    low: 0.5,
    close,
    volume: 10,
  };
}

export function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });

  return {
    promise,
    resolve,
  };
}

type FakeChartSessionAdapter = ChartSessionSubscriptionsAdapter & {
  fetchCandles(
    key: ChartSessionKey,
  ): Promise<readonly ChartCandle[]> | readonly ChartCandle[];
  renderCandles(key: ChartSessionKey, candles: readonly ChartCandle[]): void;
  requestIndicators(key: ChartSessionKey): Promise<void> | void;
  unsubscribeIndicators(): Promise<void> | void;
  resetIndicatorHistory(): void;
  reportLiveTailBufferOverflow(
    key: ChartSessionKey,
    candle: CandleUpdateMessage,
  ): void;
  getOldestCandleTimestampMs(): number | null;
  fetchOlderCandles(
    key: ChartSessionKey,
    endMs: number,
  ): Promise<readonly ChartCandle[]> | readonly ChartCandle[];
  prependOlderCandles(
    key: ChartSessionKey,
    candles: readonly ChartCandle[],
  ): Promise<void> | void;
  renderOlderCandles(key: ChartSessionKey): Promise<void> | void;
  requestOlderIndicators(key: ChartSessionKey): Promise<void> | void;
};

export function createFakeAdapter() {
  const handlers = new Set<(message: CandleUpdateMessage) => void>();
  const subscribes: ChartSessionKey[] = [];
  const unsubscribes: ChartSessionKey[] = [];
  const events: string[] = [];
  const fetchedCandles = [chartCandle(300_000)];

  const adapter: FakeChartSessionAdapter = {
    subscribeCandles: vi.fn((key) => {
      subscribes.push({ ...key });
      events.push(`subscribe:${keyLabel(key)}`);
    }),
    unsubscribeCandles: vi.fn((key) => {
      unsubscribes.push({ ...key });
      events.push(`unsubscribe:${keyLabel(key)}`);
    }),
    onCandleUpdate: vi.fn((handler) => {
      handlers.add(handler);
    }),
    offCandleUpdate: vi.fn((handler) => {
      handlers.delete(handler);
    }),
    fetchCandles: vi.fn((key: ChartSessionKey) => {
      events.push(`fetch:${keyLabel(key)}`);
      return Promise.resolve(fetchedCandles);
    }),
    renderCandles: vi.fn((key: ChartSessionKey) => {
      events.push(`render:${keyLabel(key)}`);
    }),
    requestIndicators: vi.fn((key: ChartSessionKey) => {
      events.push(`indicators:${keyLabel(key)}`);
    }),
    unsubscribeIndicators: vi.fn(() => {
      events.push('unsubscribe-indicators');
    }),
    resetIndicatorHistory: vi.fn(() => {
      events.push('reset-indicator-history');
    }),
    reportLiveTailBufferOverflow: vi.fn((key, candle) => {
      events.push(`overflow:${keyLabel(key)}:${candle.timestamp_ms}`);
    }),
    getOldestCandleTimestampMs: vi.fn(() => 300_000),
    fetchOlderCandles: vi.fn((key: ChartSessionKey, endMs: number) => {
      events.push(`fetch-older-candles:${keyLabel(key)}:${endMs}`);
      return Promise.resolve([chartCandle(0)]);
    }),
    prependOlderCandles: vi.fn((key: ChartSessionKey) => {
      events.push(`prepend-older-candles:${keyLabel(key)}`);
    }),
    renderOlderCandles: vi.fn((key: ChartSessionKey) => {
      events.push(`render-older-candles:${keyLabel(key)}`);
    }),
    requestOlderIndicators: vi.fn((key: ChartSessionKey) => {
      events.push(`fetch-older-indicators:${keyLabel(key)}`);
    }),
  };

  return {
    adapter,
    events,
    fetchedCandles,
    handlers,
    subscribes,
    unsubscribes,
  };
}
