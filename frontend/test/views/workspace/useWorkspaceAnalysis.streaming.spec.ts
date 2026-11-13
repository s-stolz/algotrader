import { effectScope, ref } from 'vue';
import { flushPromises } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useWorkspaceAnalysis } from '@/views/workspace/useWorkspaceAnalysis';
import {
  fetchBacktestEquityCurve,
  getBacktestRun,
} from '@/api/backtesterClient';
import type {
  BacktestRun,
  EquityReplayResponse,
} from '@/types/backtesterContracts';

vi.mock('@/api/backtesterClient', () => ({
  getBacktestRun: vi.fn(),
  fetchBacktestEquityCurve: vi.fn(),
  fetchBacktestClosedTrades: vi.fn().mockResolvedValue([]),
}));
const point = { timestamp_ms: 1, equity: 10, drawdown_pct: 0 };
const exact: EquityReplayResponse = {
  availability: 'exact',
  reason: null,
  source_point_count: 1,
  returned_point_count: 1,
  sampled: false,
  equity_curve: [point],
};
const scope = effectScope();
afterEach(() => {
  vi.clearAllMocks();
});
function setup() {
  const runs = ['a', 'b', 'c'].map(
    (run_id) => ({ run_id, status: 'succeeded' }) as BacktestRun,
  );
  vi.mocked(getBacktestRun).mockImplementation(async (id) =>
    runs.find((r) => r.run_id === id)!,
  );
  const pending = new Map<string, (value: EquityReplayResponse) => void>();
  const failures = new Map<string, (error: Error) => void>();
  vi.mocked(fetchBacktestEquityCurve).mockImplementation(
    (id, _max, options) =>
      new Promise((resolve, reject) => {
        pending.set(id, resolve);
        failures.set(id, reject);
        options!.signal.addEventListener('abort', () =>
          reject(new DOMException('Aborted', 'AbortError')),
        );
      }),
  );
  const model = scope.run(() => useWorkspaceAnalysis(ref(runs)))!;
  model.setComparison(['a', 'b', 'c']);
  return { model, pending, failures };
}
describe('stream lifecycle', () => {
  it('limits streams to two, discards previews on stop, retains completed curves', async () => {
    const { model, pending } = setup();
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(2);
    const options = vi.mocked(fetchBacktestEquityCurve).mock.calls[0][2]!;
    options.onPreview([point]);
    expect(model.analysis.value.a.preview).toEqual([point]);
    expect(model.analysis.value.a.curve).toBeNull();
    pending.get('b')!(exact);
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(3);
    model.stop();
    await flushPromises();
    expect(options.signal.aborted).toBe(true);
    expect(model.analysis.value.a.preview).toEqual([]);
    expect(model.analysis.value.b.curve).toEqual(exact);
    model.loadAnalysis();
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(5);
    model.stop();
  });
  it('aborts deselected runs and drops their previews', async () => {
    const { model } = setup();
    await flushPromises();
    const call = vi.mocked(fetchBacktestEquityCurve).mock.calls[0][2]!;
    call.onPreview([point]);
    model.setComparison(['b', 'c']);
    await flushPromises();
    expect(call.signal.aborted).toBe(true);
    expect(model.analysis.value.a).toBeUndefined();
    model.stop();
  });
  it('clears failed previews and retries only on explicit action', async () => {
    const { model, failures } = setup();
    await flushPromises();
    vi.mocked(fetchBacktestEquityCurve).mock.calls[0][2]!.onPreview([point]);
    failures.get('a')!(new Error('Disconnected'));
    await flushPromises();
    expect(model.analysis.value.a.preview).toEqual([]);
    expect(model.analysis.value.a.error).toBe('Disconnected');
    const count = vi.mocked(fetchBacktestEquityCurve).mock.calls.length;
    model.loadAnalysis();
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(count);
    model.setComparison(['a']);
    await flushPromises();
    model.retryAnalysis('a');
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(count + 1);
    model.stop();
  });
});
