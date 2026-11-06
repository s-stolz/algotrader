import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { recoverIndicatorHistory } from '@/stores/indicators/recovery';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { requestIndicator } from '@/api/indicatorClient';
import type {
  IndicatorInfo,
  IndicatorResponse,
  IndicatorUpdateMessage,
} from '@/types/contracts';
import { wsService } from '@/utils/websocketService';
import { deferred } from '../../components/Chart/chartSession.fixtures';

vi.mock('@/api/indicatorClient', () => ({ requestIndicator: vi.fn() }));
vi.mock('@/utils/websocketService', () => ({
  wsService: { send: vi.fn(), on: vi.fn(), off: vi.fn() },
}));
const info: IndicatorInfo = {
  id: 1,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: true,
  inputs: [],
  outputs: { sma: { type: 'line', plotOptions: {} } },
  parameters: {},
};
const point = (timestamp_ms: number, sma = 1) => ({ timestamp_ms, sma });
const query = {
  symbol: 'EURUSD',
  timeframe: 'M1',
  exchange: 'FX',
  startMs: 120_000,
  endMs: 300_000,
};
const response = (
  points = [point(120_000, 2), point(180_000, 3), point(240_000, 4)],
): IndicatorResponse => ({
  data: { indicator_info: info, indicator_data: points },
});
beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

it('corrects duplicates while preserving old history and fresh samples', async () => {
  const store = useIndicatorsStore();
  const id = store.addIndicator(info, [point(0)], 1);
  const version = store.getById(id)!.dataVersion;
  store.handleLiveUpdate({
    type: 'indicatorUpdate',
    clientIndicatorId: id,
    timestamp_ms: 60_000,
    values: { sma: 8 },
  });
  store.handleLiveUpdate({
    type: 'indicatorUpdate',
    clientIndicatorId: id,
    timestamp_ms: 120_000,
    values: { sma: 9 },
  });
  expect(store.getById(id)!.dataVersion).toBe(version);
  const pending = deferred<IndicatorResponse>();
  vi.mocked(requestIndicator).mockReturnValueOnce(pending.promise);
  const recovery = recoverIndicatorHistory(
    store,
    query,
    () => true,
    new AbortController().signal,
  );
  const listener = vi.mocked(wsService.on).mock.calls[0][1] as (
    message: IndicatorUpdateMessage,
  ) => void;
  listener({
    type: 'indicatorUpdate',
    clientIndicatorId: id,
    timestamp_ms: 240_000,
    values: { sma: 10 },
  });
  listener({
    type: 'indicatorUpdate',
    clientIndicatorId: id,
    timestamp_ms: 300_000,
    values: { sma: 11 },
  });
  const history = response();
  history.data.indicator_data[2] = { ...point(240_000, 4), signal: 12 };
  pending.resolve(history);
  await recovery;
  expect(requestIndicator).toHaveBeenCalledWith(1, query, { parameters: {} });
  expect(store.getById(id)!.data).toEqual([
    point(0),
    point(60_000, 8),
    point(120_000, 2),
    point(180_000, 3),
    { ...point(240_000, 10), signal: 12 },
    point(300_000, 11),
  ]);
  expect(wsService.off).toHaveBeenCalledWith('indicatorUpdate', listener);
});

it.each(['removed', 'generation', 'session'] as const)(
  'ignores obsolete indicator response: %s',
  async (reason) => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, [point(0)], 1);
    const pending = deferred<IndicatorResponse>();
    vi.mocked(requestIndicator).mockReturnValueOnce(pending.promise);
    let current = true;
    const recovery = recoverIndicatorHistory(
      store,
      query,
      () => current,
      new AbortController().signal,
    );
    if (reason === 'removed') store.removeIndicator(id);
    if (reason === 'generation') store.resetHistoryFlags();
    if (reason === 'session') current = false;
    pending.resolve(response());
    await recovery;
    expect(store.getById(id)?.data ?? []).not.toContainEqual(point(180_000, 3));
  },
);

it('recovers run-owned and historical-only indicators without retries', async () => {
  const store = useIndicatorsStore();
  store.addIndicator(info, [point(0)], 1, {}, 'run-1');
  const id = store.addIndicator(
    { ...info, supports_live: false },
    [point(0)],
    1,
  );
  vi.mocked(requestIndicator)
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce(response());
  await expect(
    recoverIndicatorHistory(
      store,
      query,
      () => true,
      new AbortController().signal,
    ),
  ).rejects.toThrow('offline');
  expect(requestIndicator).toHaveBeenCalledTimes(2);
  expect(store.getById(id)!.data).toContainEqual(point(180_000, 3));
  expect(wsService.send).not.toHaveBeenCalled();
});

it('removes the live listener immediately when the session aborts', async () => {
  const store = useIndicatorsStore();
  store.addIndicator(info, [point(0)], 1);
  const pending = deferred<IndicatorResponse>();
  vi.mocked(requestIndicator).mockReturnValueOnce(pending.promise);
  const controller = new AbortController();
  const recovery = recoverIndicatorHistory(
    store,
    query,
    () => !controller.signal.aborted,
    controller.signal,
  );
  controller.abort();
  expect(wsService.off).toHaveBeenCalled();
  pending.resolve(response());
  await recovery;
});
