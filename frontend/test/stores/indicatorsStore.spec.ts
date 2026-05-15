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

  it('prepends older history through the typed client', async () => {
    vi.mocked(requestIndicatorClient).mockResolvedValue(indicatorResponse([
      { timestamp_ms: 1_000, sma: 1.1 },
    ]));
    const store = useIndicatorsStore();
    const localId = store.addIndicator(indicatorInfo, [{ timestamp_ms: 2_000, sma: 1.2 }], 1);

    await store.fetchOlderForAll('EURUSD', 'M1', 'FX', 250);

    expect(requestIndicatorClient).toHaveBeenCalledWith(1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
      exchange: 'FX',
      endMs: 2_000,
      limit: 250,
    }, {
      parameters: { length: 14, source: 'close' },
    });
    expect(store.getById(localId)?.data).toEqual([
      { timestamp_ms: 1_000, sma: 1.1 },
      { timestamp_ms: 2_000, sma: 1.2 },
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
