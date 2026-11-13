import { parseReplayFrame } from '@/types/backtest/replayStream';
import type {
  EquityReplayPoint,
  EquityReplayResponse,
} from '@/types/backtesterContracts';

export interface ReplayStreamOptions {
  signal: AbortSignal;
  onPreview: (points: EquityReplayPoint[]) => void;
}

export async function readEquityReplayStream(
  url: string,
  options: ReplayStreamOptions,
): Promise<EquityReplayResponse> {
  const response = await fetch(url, { signal: options.signal });
  if (!response.ok || !response.body)
    throw new Error('Failed to load Equity Replay');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result: EquityReplayResponse | null = null;
  function consume(line: string) {
    if (line.length > 4_000_000)
      throw new Error('Equity Replay frame is too large');
    if (!line.trim()) return;
    if (result) throw new Error('Data after Equity Replay completion');
    const frame = parseReplayFrame(line);
    if (frame.type === 'error') throw new Error(frame.message);
    if (frame.type === 'complete') result = frame.result;
    else options.onPreview(frame.equity_curve);
  }
  try {
    while (true) {
      options.signal.throwIfAborted();
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let newline: number;
      while ((newline = buffer.indexOf('\n')) >= 0) {
        consume(buffer.slice(0, newline));
        buffer = buffer.slice(newline + 1);
      }
      if (buffer.length > 4_000_000)
        throw new Error('Equity Replay frame is too large');
      if (done) break;
    }
    options.signal.throwIfAborted();
    if (buffer.trim()) consume(buffer);
    if (!result) throw new Error('Equity Replay stream was interrupted');
    return result;
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
