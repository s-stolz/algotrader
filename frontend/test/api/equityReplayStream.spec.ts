import { afterEach, describe, expect, it, vi } from 'vitest';
import { readEquityReplayStream } from '@/api/equityReplayStream';

const point = { timestamp_ms: 1, equity: 100, drawdown_pct: 0 };
const result = {
  availability: 'exact',
  reason: null,
  source_point_count: 1,
  returned_point_count: 1,
  sampled: false,
  equity_curve: [point],
};
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
afterEach(() => vi.unstubAllGlobals());
describe('equity stream transport', () => {
  it('handles fragmented frames and exposes previews before completion', async () => {
    const wire =
      JSON.stringify({ type: 'preview', equity_curve: [point] }) +
      '\n' +
      JSON.stringify({ type: 'complete', result }) +
      '\n';
    const cancel = serve([
      wire.slice(0, 15),
      wire.slice(15, 91),
      wire.slice(91),
    ]);
    const onPreview = vi.fn();
    expect(
      await readEquityReplayStream('/stream', {
        signal: new AbortController().signal,
        onPreview,
      }),
    ).toEqual(result);
    expect(onPreview).toHaveBeenCalledWith([point]);
    expect(cancel).toHaveBeenCalledOnce();
  });
  it('rejects EOF without a terminal frame', async () => {
    serve([JSON.stringify({ type: 'preview', equity_curve: [point] }) + '\n']);
    await expect(
      readEquityReplayStream('/stream', {
        signal: new AbortController().signal,
        onPreview: vi.fn(),
      }),
    ).rejects.toThrow('interrupted');
  });
  it('closes the reader on cancellation', async () => {
    const cancel = serve(['']);
    const controller = new AbortController();
    controller.abort();
    await expect(
      readEquityReplayStream('/stream', {
        signal: controller.signal,
        onPreview: vi.fn(),
      }),
    ).rejects.toThrow();
    expect(cancel).toHaveBeenCalledOnce();
  });
});
