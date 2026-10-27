import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { requestIndicator } from '@/api/indicatorClient';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { IndicatorInfo, IndicatorResponse } from '@/types/contracts';
import { wsService } from '@/utils/websocketService';

vi.mock('@/api/indicatorClient', () => ({ requestIndicator: vi.fn() }));
vi.mock('@/utils/websocketService', () => ({ wsService: { send: vi.fn() } }));

const info: IndicatorInfo = {
  id: 1,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: false,
  inputs: [],
  outputs: {
    timestamp: { type: 'time' },
    sma: { type: 'line', plotOptions: { color: '#fff' } },
  },
  parameters: { length: { type: 'int', default: 14 } },
};

function response(timestampMs: number, value = 1): IndicatorResponse {
  return {
    data: {
      indicator_info: info,
      indicator_data: [{ timestamp_ms: timestampMs, sma: value }],
    },
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

describe('Indicator configuration and request lifecycle', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(requestIndicator).mockReset();
    vi.mocked(wsService.send).mockReset().mockResolvedValue();
    vi.spyOn(Date, 'now').mockReturnValue(12345);
  });

  it('uses the current default Candle range during older-history loading', async () => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, response(3_000).data.indicator_data, 1);
    let oldestTimestampMs = 2_000;
    const getLoadedCandleRange = vi.fn(() => ({
      oldestTimestampMs,
      newestTimestampMs: 3_000,
      exclusiveEndMs: 4_000,
    }));
    store.configureHistoryCoverage({ batchSize: 1, getLoadedCandleRange });
    vi.mocked(requestIndicator)
      .mockResolvedValueOnce(response(2_000))
      .mockResolvedValueOnce(response(1_000));

    await store.fetchOlderForAll('EURUSD', 'M1', 'FX', 1);
    oldestTimestampMs = 1_000;
    await store.ensureCoverageForAll('EURUSD', 'M1', 'FX');

    expect(requestIndicator).toHaveBeenNthCalledWith(
      2,
      1,
      {
        symbol: 'EURUSD',
        timeframe: 'M1',
        exchange: 'FX',
        endMs: 2_000,
        limit: 1,
      },
      { parameters: { length: 14 } },
    );
    expect(getLoadedCandleRange).toHaveBeenCalled();
    expect(store.getById(id)?.data.map((point) => point.timestamp_ms)).toEqual([
      1_000, 2_000, 3_000,
    ]);
    store.configureHistoryCoverage(null);
    await store.ensureCoverageForAll('EURUSD', 'M1');
    expect(requestIndicator).toHaveBeenCalledTimes(2);
  });

  it('rejects a superseded latest response and preserves subscription identity', async () => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, [], 1);
    const stale = deferred<IndicatorResponse>();
    vi.mocked(requestIndicator)
      .mockReturnValueOnce(stale.promise)
      .mockResolvedValueOnce(response(3_000, 9));
    const staleRequest = store.requestIndicator(id, 1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
    });
    const latestRequest = store.requestIndicator(id, 1, {
      symbol: 'EURUSD',
      timeframe: 'M5',
    });
    expect(await latestRequest).toBe(id);
    stale.resolve(response(1_000));
    expect(await staleRequest).toBeNull();
    expect(store.getById(id)?.data).toEqual([{ timestamp_ms: 3_000, sma: 9 }]);
    expect(wsService.send).toHaveBeenCalledTimes(1);
    expect(store.liveSubscriptions.get(id)).toMatchObject({
      clientIndicatorId: id,
      timeframe: 'M5',
      parameters: { length: 14 },
    });
  });

  it('keeps newer live values while historical data is prepended', async () => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, response(2_000).data.indicator_data, 1);
    store.updateIndicatorData(id, response(2_000).data.indicator_data);
    const older = deferred<IndicatorResponse>();
    vi.mocked(requestIndicator).mockReturnValueOnce(older.promise);
    const prepend = store.requestIndicatorPrepend(id, 1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
      end_ms: 2_000,
    });
    const livePoint = store.handleLiveUpdate({
      type: 'indicatorUpdate',
      clientIndicatorId: id,
      timestamp_ms: 3_000,
      values: { sma: 9 },
    });
    store.updateIndicatorData(id, [...store.getById(id)!.data, livePoint!]);
    older.resolve({
      data: {
        indicator_info: info,
        indicator_data: [
          { timestamp_ms: 1_000, sma: 1 },
          { timestamp_ms: 3_000, sma: 0 },
        ],
      },
    });
    await prepend;
    expect(store.getById(id)?.data).toEqual([
      { timestamp_ms: 1_000, sma: 1 },
      { timestamp_ms: 2_000, sma: 1 },
      { timestamp_ms: 3_000, sma: 9 },
    ]);
    expect(store.getById(id)?.lastLivePoint).toEqual(livePoint);
  });

  it('preserves provided parameters and isolates output styles per Indicator', () => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, [], 1, {
      length: { value: 20 },
      extra: 'open',
    });
    const indicator = store.getById(id)!;
    expect(store.extractParameterValues(indicator.parameters)).toEqual({
      length: 20,
      extra: 'open',
    });
    store.updateIndicatorParameters(id, {
      length: { default: 50 },
      missing: 2,
    });
    expect(indicator.parameters.length).toEqual({
      type: 'int',
      default: 14,
      value: 20,
    });
    indicator.styles.sma.color = '#000';
    expect(store.createStyles(info.outputs)).toEqual({
      sma: { color: '#fff' },
    });
    expect(info.outputs.sma.plotOptions?.color).toBe('#fff');
  });

  it('clears subscriptions and panes and ignores responses after removal', async () => {
    const store = useIndicatorsStore();
    const id = store.addIndicator(info, [], 1);
    store.updateIndicatorPaneElement(id, document.createElement('div'));
    await store.subscribeIndicatorLive(id, {
      symbol: 'EURUSD',
      timeframe: 'M1',
      exchange: 'FX',
      indicatorId: 1,
      parameters: { length: 14 },
    });
    const pending = deferred<IndicatorResponse>();
    vi.mocked(requestIndicator).mockReturnValueOnce(pending.promise);
    const refresh = store.requestIndicator(id, 1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
    });
    await Promise.resolve();
    store.clear();
    pending.resolve(response(1_000));
    expect(await refresh).toBeNull();
    expect(store.all).toEqual([]);
    expect(store.liveSubscriptions.size).toBe(0);
    expect(store.paneCount).toBe(1);
    expect(wsService.send).toHaveBeenCalledWith('unsubscribeIndicator', {
      symbol: 'EURUSD',
      timeframe: 'M1',
      exchange: 'FX',
      indicatorId: 1,
      parameters: { length: 14 },
      clientIndicatorId: id,
    });
    expect(
      store.handleLiveUpdate({
        type: 'indicatorUpdate',
        clientIndicatorId: id,
        timestamp_ms: 2_000,
        values: { sma: 2 },
      }),
    ).toBeNull();
  });
});
