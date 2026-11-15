import {
  isCandleArray,
  isRecord,
  toChartCandle,
  type ChartCandle,
} from '@/types/contracts';
import { withQuery } from './http';

interface CandleStreamOptions {
  startMs: number;
  endMs: number;
  exchange: string | null;
  signal: AbortSignal;
  onBatch: (candles: ChartCandle[]) => Promise<void> | void;
}

export async function streamCandles(
  symbol: string,
  timeframe: string,
  options: CandleStreamOptions,
): Promise<void> {
  const response = await fetch(
    withQuery(
      `/api/data-accessor/candles/${encodeURIComponent(symbol)}/stream`,
      {
        timeframe,
        start_ms: options.startMs,
        end_ms: options.endMs,
        exchange: options.exchange,
      },
    ),
    { signal: options.signal },
  );
  if (!response.ok || !response.body)
    throw new Error('Failed to stream candles');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let complete = false;
  let previousTimestamp = -Infinity;
  async function consume(line: string) {
    if (!line.trim()) return;
    if (line.length > 1_000_000 || complete)
      throw new Error('Invalid candle stream frame');
    const frame: unknown = JSON.parse(line);
    if (!isRecord(frame)) throw new Error('Invalid candle stream frame');
    if (frame.type === 'complete') {
      complete = true;
      return;
    }
    if (
      frame.type !== 'candles' ||
      !isCandleArray(frame.candles) ||
      frame.candles.length > 1024
    )
      throw new Error('Invalid candle stream batch');
    for (const candle of frame.candles) {
      if (
        candle.timestamp_ms <= previousTimestamp ||
        candle.timestamp_ms < options.startMs ||
        candle.timestamp_ms >= options.endMs
      )
        throw new Error('Invalid candle stream ordering or range');
      previousTimestamp = candle.timestamp_ms;
    }
    options.signal.throwIfAborted();
    await options.onBatch(frame.candles.map(toChartCandle));
  }
  try {
    while (true) {
      options.signal.throwIfAborted();
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let newline: number;
      while ((newline = buffer.indexOf('\n')) >= 0) {
        await consume(buffer.slice(0, newline));
        buffer = buffer.slice(newline + 1);
      }
      if (buffer.length > 1_000_000)
        throw new Error('Candle stream frame is too large');
      if (done) break;
    }
    options.signal.throwIfAborted();
    if (buffer.trim()) await consume(buffer);
    if (!complete) throw new Error('Candle stream was interrupted');
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
