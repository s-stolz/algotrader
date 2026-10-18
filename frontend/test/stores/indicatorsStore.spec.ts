import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { requestIndicator as requestIndicatorClient } from '@/api/indicatorClient';
import type {
  IndicatorDataPoint,
  IndicatorInfo,
  IndicatorResponse,
} from '@/types/contracts';
import { wsService } from '@/utils/websocketService';

import { useIndicatorsStore } from '@/stores/indicatorsStore';

vi.mock('@/api/indicatorClient', () => ({
  requestIndicator: vi.fn(),
}));

vi.mock('@/utils/websocketService', () => ({
  wsService: {
    send: vi.fn(),
  },
}));

const indicatorInfo: IndicatorInfo = {
  id: 1,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: false,
  inputs: [],
  outputs: {
    timestamp: { type: 'time' },
    sma: {
      type: 'line',
      plotOptions: { color: '#fff', lineWidth: 2 },
    },
  },
  parameters: {
    length: { type: 'int', default: 14 },
    source: { type: 'string', default: 'close' },
  },
};

const indicatorResponse = (points: IndicatorDataPoint[]): IndicatorResponse => ({
  data: {
    indicator_info: indicatorInfo,
    indicator_data: points,
  },
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

describe('indicators store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(requestIndicatorClient).mockReset();
    vi.mocked(wsService.send).mockReset();
    vi.mocked(wsService.send).mockResolvedValue();
    vi.spyOn(Date, 'now').mockReturnValue(12345);
  });

  it('requests indicators through the typed client, stores defaults, and subscribes live updates', async () => {
    vi.mocked(requestIndicatorClient).mockResolvedValue(indicatorResponse([
      { timestamp_ms: 1_000, sma: 1.2 },
    ]));

    const store = useIndicatorsStore();
    const localId = await store.requestIndicator(null, 1, {
      symbol: 'EURUSD',
      timeframe: 'M5',
      exchange: 'FX',
      limit: 500,
    }, {});

    expect(requestIndicatorClient).toHaveBeenCalledWith(1, {
      symbol: 'EURUSD',
      timeframe: 'M5',
      exchange: 'FX',
      endMs: null,
      limit: 500,
    }, {});
    expect(localId).toBe('12345');
    expect(store.all).toHaveLength(1);
    expect(store.getById('12345')).toMatchObject({
      _id: '12345',
      indicatorId: 1,
      paneIndex: 1,
      data: [{ timestamp_ms: 1_000, sma: 1.2 }],
      parameters: {
        length: { type: 'int', default: 14, value: 14 },
        source: { type: 'string', default: 'close', value: 'close' },
      },
      styles: {
        sma: { color: '#fff', lineWidth: 2 },
      },
      currentLimit: 1,
      hasExpandedHistory: false,
    });
    expect(wsService.send).toHaveBeenCalledWith('subscribeIndicator', {
      symbol: 'EURUSD',
      timeframe: 'M5',
      exchange: 'FX',
      indicatorId: 1,
      parameters: { length: 14, source: 'close' },
      clientIndicatorId: '12345',
    });
    expect(store.liveSubscriptions.get('12345')).toEqual({
      symbol: 'EURUSD',
      timeframe: 'M5',
      exchange: 'FX',
      indicatorId: 1,
      parameters: { length: 14, source: 'close' },
      clientIndicatorId: '12345',
    });
  });

  it('requests the latest visible batch first and backfills older batches until candles are covered', async () => {
    vi.mocked(requestIndicatorClient)
      .mockResolvedValueOnce(indicatorResponse([
        { timestamp_ms: 3_000, sma: 1.3 },
        { timestamp_ms: 4_000, sma: 1.4 },
      ]))
      .mockResolvedValueOnce(indicatorResponse([
        { timestamp_ms: 1_000, sma: 1.1 },
        { timestamp_ms: 2_000, sma: 1.2 },
      ]));

    const store = useIndicatorsStore();
    const coverageOptions = {
      batchSize: 2,
      getLoadedCandleRange: () => ({
        oldestTimestampMs: 1_000,
        newestTimestampMs: 4_000,
        exclusiveEndMs: 5_000,
      }),
    };

    const localId = await store.requestIndicator(null, 1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
      exchange: 'FX',
    }, {}, coverageOptions);
    await store.ensureCoverageForAll('EURUSD', 'M1', 'FX', coverageOptions);

    expect(requestIndicatorClient).toHaveBeenNthCalledWith(1, 1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
      exchange: 'FX',
      endMs: 5_000,
      limit: 2,
    }, {});
    expect(requestIndicatorClient).toHaveBeenNthCalledWith(2, 1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
      exchange: 'FX',
      endMs: 3_000,
      limit: 2,
    }, {
      parameters: { length: 14, source: 'close' },
    });
    expect(store.getById(localId!)?.data).toEqual([
      { timestamp_ms: 1_000, sma: 1.1 },
      { timestamp_ms: 2_000, sma: 1.2 },
      { timestamp_ms: 3_000, sma: 1.3 },
      { timestamp_ms: 4_000, sma: 1.4 },
    ]);
  });

  it('widens the target range without starting overlapping backfill requests', async () => {
    const firstBackfill = deferred<IndicatorResponse>();
    const secondBackfill = deferred<IndicatorResponse>();
    vi.mocked(requestIndicatorClient)
      .mockReturnValueOnce(firstBackfill.promise)
      .mockReturnValueOnce(secondBackfill.promise);

    const store = useIndicatorsStore();
    const localId = store.addIndicator(indicatorInfo, [
      { timestamp_ms: 3_000, sma: 1.3 },
      { timestamp_ms: 4_000, sma: 1.4 },
    ], 1);
    let oldestTimestampMs = 2_000;
    const coverageOptions = {
      batchSize: 1,
      getLoadedCandleRange: () => ({
        oldestTimestampMs,
        newestTimestampMs: 4_000,
        exclusiveEndMs: 5_000,
      }),
    };

    const firstEnsure = store.ensureCoverageForAll('EURUSD', 'M1', 'FX', coverageOptions);
    expect(requestIndicatorClient).toHaveBeenCalledTimes(1);

    oldestTimestampMs = 1_000;
    const secondEnsure = store.ensureCoverageForAll('EURUSD', 'M1', 'FX', coverageOptions);
    expect(requestIndicatorClient).toHaveBeenCalledTimes(1);

    firstBackfill.resolve(indicatorResponse([{ timestamp_ms: 2_000, sma: 1.2 }]));
    await Promise.resolve();
    expect(requestIndicatorClient).toHaveBeenCalledTimes(2);

    secondBackfill.resolve(indicatorResponse([{ timestamp_ms: 1_000, sma: 1.1 }]));
    await Promise.all([firstEnsure, secondEnsure]);

    expect(store.getById(localId)?.data).toEqual([
      { timestamp_ms: 1_000, sma: 1.1 },
      { timestamp_ms: 2_000, sma: 1.2 },
      { timestamp_ms: 3_000, sma: 1.3 },
      { timestamp_ms: 4_000, sma: 1.4 },
    ]);
  });

  it('ignores stale backfill results after a parameter refresh invalidates the generation', async () => {
    const staleBackfill = deferred<IndicatorResponse>();
    vi.mocked(requestIndicatorClient)
      .mockReturnValueOnce(staleBackfill.promise)
      .mockResolvedValueOnce(indicatorResponse([
        { timestamp_ms: 3_000, sma: 9.9 },
      ]));

    const store = useIndicatorsStore();
    const localId = store.addIndicator(indicatorInfo, [{ timestamp_ms: 3_000, sma: 1.3 }], 1);
    let oldestTimestampMs = 1_000;
    const coverageOptions = {
      batchSize: 1,
      getLoadedCandleRange: () => ({
        oldestTimestampMs,
        newestTimestampMs: 3_000,
        exclusiveEndMs: 4_000,
      }),
    };

    const staleEnsure = store.ensureCoverageForAll('EURUSD', 'M1', 'FX', coverageOptions);
    oldestTimestampMs = 3_000;
    await store.requestIndicator(localId, 1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
    }, {
      parameters: { length: 20 },
    }, coverageOptions);

    staleBackfill.resolve(indicatorResponse([{ timestamp_ms: 1_000, sma: 1.1 }]));
    await staleEnsure;

    expect(store.getById(localId)?.data).toEqual([
      { timestamp_ms: 3_000, sma: 9.9 },
    ]);
  });

  it('marks history exhausted when an older batch returns no data', async () => {
    vi.mocked(requestIndicatorClient).mockResolvedValue(indicatorResponse([]));
    const store = useIndicatorsStore();
    const localId = store.addIndicator(indicatorInfo, [{ timestamp_ms: 3_000, sma: 1.3 }], 1);
    const coverageOptions = {
      batchSize: 1,
      getLoadedCandleRange: () => ({
        oldestTimestampMs: 1_000,
        newestTimestampMs: 3_000,
        exclusiveEndMs: 4_000,
      }),
    };

    await store.ensureCoverageForAll('EURUSD', 'M1', 'FX', coverageOptions);
    await store.ensureCoverageForAll('EURUSD', 'M1', 'FX', coverageOptions);

    expect(requestIndicatorClient).toHaveBeenCalledTimes(1);
    expect(store.getById(localId)?.historyExhausted).toBe(true);
  });

  it('trims merged historical data to the loaded candle range and keeps existing duplicates', async () => {
    vi.mocked(requestIndicatorClient).mockResolvedValue(indicatorResponse([
      { timestamp_ms: 1_000, sma: 1.1 },
      { timestamp_ms: 2_000, sma: 1.2 },
      { timestamp_ms: 3_000, sma: 7.7 },
    ]));
    const store = useIndicatorsStore();
    const localId = store.addIndicator(indicatorInfo, [{ timestamp_ms: 3_000, sma: 1.3 }], 1);

    await store.ensureCoverageForAll('EURUSD', 'M1', 'FX', {
      batchSize: 3,
      getLoadedCandleRange: () => ({
        oldestTimestampMs: 2_000,
        newestTimestampMs: 3_000,
        exclusiveEndMs: 4_000,
      }),
    });

    expect(requestIndicatorClient).toHaveBeenCalledWith(1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
      exchange: 'FX',
      endMs: 3_000,
      limit: 3,
    }, {
      parameters: { length: 14, source: 'close' },
    });
    expect(store.getById(localId)?.data).toEqual([
      { timestamp_ms: 2_000, sma: 1.2 },
      { timestamp_ms: 3_000, sma: 1.3 },
    ]);
    expect(store.getById(localId)?.hasExpandedHistory).toBe(true);
  });

  it('merges same-timestamp live updates, accepts newer points, and ignores older points', () => {
    const store = useIndicatorsStore();
    const localId = store.addIndicator(indicatorInfo, [], 1);

    expect(store.handleLiveUpdate({
      type: 'indicatorUpdate',
      clientIndicatorId: localId,
      timestamp_ms: 2_000,
      values: { sma: 1.2 },
    })).toEqual({ timestamp_ms: 2_000, sma: 1.2 });

    expect(store.handleLiveUpdate({
      type: 'indicatorUpdate',
      clientIndicatorId: localId,
      timestamp_ms: 2_000,
      values: { signal: 1.3 },
    })).toEqual({ timestamp_ms: 2_000, sma: 1.2, signal: 1.3 });

    expect(store.handleLiveUpdate({
      type: 'indicatorUpdate',
      clientIndicatorId: localId,
      timestamp_ms: 1_000,
      values: { sma: 0.9 },
    })).toBeNull();

    expect(store.handleLiveUpdate({
      type: 'indicatorUpdate',
      clientIndicatorId: localId,
      timestamp_ms: 3_000,
      values: { sma: 1.4 },
    })).toEqual({ timestamp_ms: 3_000, sma: 1.4 });
  });

  it('tracks subscribe and unsubscribe payloads', async () => {
    const store = useIndicatorsStore();

    await store.subscribeIndicatorLive('client-1', {
      symbol: 'EURUSD',
      timeframe: 'H1',
      exchange: null,
      indicatorId: 1,
      parameters: { length: 20 },
    });

    expect(store.liveSubscriptions.get('client-1')).toEqual({
      symbol: 'EURUSD',
      timeframe: 'H1',
      exchange: null,
      indicatorId: 1,
      parameters: { length: 20 },
      clientIndicatorId: 'client-1',
    });
    expect(wsService.send).toHaveBeenCalledWith('subscribeIndicator', {
      symbol: 'EURUSD',
      timeframe: 'H1',
      exchange: null,
      indicatorId: 1,
      parameters: { length: 20 },
      clientIndicatorId: 'client-1',
    });

    await store.unsubscribeIndicatorLive('client-1');

    expect(store.liveSubscriptions.has('client-1')).toBe(false);
    expect(wsService.send).toHaveBeenCalledWith('unsubscribeIndicator', {
      symbol: 'EURUSD',
      timeframe: 'H1',
      exchange: null,
      indicatorId: 1,
      parameters: { length: 20 },
      clientIndicatorId: 'client-1',
    });
  });

  it('updates parameters and removes indicator panes without breaking following pane indices', () => {
    const store = useIndicatorsStore();
    const firstId = store.addIndicator(indicatorInfo, [{ timestamp_ms: 1_000, sma: 1.2 }], 1);
    vi.spyOn(Date, 'now').mockReturnValue(67890);
    const secondId = store.addIndicator(indicatorInfo, [{ timestamp_ms: 2_000, sma: 1.3 }], 1);
    const paneElement = document.createElement('div');

    store.updateIndicatorPaneElement(secondId, paneElement);
    expect(store.updateIndicatorParameters(firstId, {
      length: 20,
      source: { value: 'open' },
    })).toMatchObject({
      length: { value: 20 },
      source: { value: 'open' },
    });

    store.removeIndicator(firstId);

    expect(store.exists(firstId)).toBe(false);
    expect(store.getById(secondId)?.paneIndex).toBe(1);
    expect(store.getById(secondId)?.paneHtmlElement).toBeNull();
    expect(store.paneCount).toBe(2);
  });
});
