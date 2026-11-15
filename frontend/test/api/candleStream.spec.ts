import { afterEach, describe, expect, it, vi } from 'vitest';
import { streamCandles } from '@/api/candleStream';

const candle = {
  timestamp_ms: 1000,
  open: 1,
  high: 2,
  low: 0,
  close: 1,
  volume: 10,
};
const frame = (candles = [candle]) =>
  JSON.stringify({ type: 'candles', candles }) + '\n';
function serve(chunks: string[]) {
  const cancel = vi.fn().mockResolvedValue(undefined);
  let index = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: async () =>
            index < chunks.length
              ? {
                  done: false,
                  value: new TextEncoder().encode(chunks[index++]),
                }
              : { done: true },
          cancel,
          releaseLock: vi.fn(),
        }),
      },
    }),
  );
  return cancel;
}
const options = () => ({
  startMs: 0,
  endMs: 5000,
  exchange: 'FX',
  signal: new AbortController().signal,
  onBatch: vi.fn(),
});
afterEach(() => vi.unstubAllGlobals());

describe('candle streaming transport', () => {
  it('parses fragmented NDJSON and converts milliseconds to chart seconds', async () => {
    const wire = frame() + '{"type":"complete"}\n';
    const cancel = serve([
      wire.slice(0, 12),
      wire.slice(12, 60),
      wire.slice(60),
    ]);
    const request = options();
    await streamCandles('EUR/USD', 'M5', request);
    expect(request.onBatch).toHaveBeenCalledWith([{ ...candle, time: 1 }]);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('EUR%2FUSD/stream?'),
      { signal: request.signal },
    );
    expect(cancel).toHaveBeenCalledOnce();
  });
  it.each([
    [frame(), 'interrupted'],
    [frame() + frame() + '{"type":"complete"}\n', 'ordering'],
    ['{"type":"complete"}\n' + frame(), 'frame'],
    [frame([{ ...candle, timestamp_ms: 5000 }]), 'range'],
  ])('rejects incomplete or invalid streams', async (wire, error) => {
    serve([wire]);
    await expect(streamCandles('EURUSD', 'M5', options())).rejects.toThrow(
      error,
    );
  });
  it('stops delivering frames and closes the reader on abort', async () => {
    const cancel = serve([
      frame() + frame([{ ...candle, timestamp_ms: 2000 }]),
    ]);
    const controller = new AbortController();
    const onBatch = vi.fn(() => controller.abort());
    await expect(
      streamCandles('EURUSD', 'M5', {
        ...options(),
        signal: controller.signal,
        onBatch,
      }),
    ).rejects.toThrow();
    expect(onBatch).toHaveBeenCalledOnce();
    expect(cancel).toHaveBeenCalledOnce();
  });
});
