import { mount, flushPromises } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useHistoryDownloads } from '@/components/TopBar/Modals/history/useHistoryDownloads';
import {
  changeHistoryDownload,
  fetchHistoryDownloads,
  fetchMarketCoverage,
  requestHistoryDownload,
} from '@/api/historyDownloadClient';
import type { HistoryDownload } from '@/types/historyDownloadContracts';
import { wsService } from '@/utils/websocketService';

const events = vi.hoisted(
  () => new Map<string, (value: Record<string, unknown>) => void>(),
);
vi.mock('@/api/historyDownloadClient', () => ({
  changeHistoryDownload: vi.fn(),
  fetchHistoryDownloads: vi.fn(),
  fetchMarketCoverage: vi.fn(),
  requestHistoryDownload: vi.fn(),
}));
vi.mock('@/utils/websocketService', () => ({
  wsService: {
    send: vi.fn(),
    on: vi.fn((event, handler) => events.set(event, handler)),
    off: vi.fn((event) => events.delete(event)),
  },
}));

function job(overrides: Partial<HistoryDownload> = {}): HistoryDownload {
  return {
    id: 'job-1',
    market_id: 7,
    status: 'queued',
    start_ms: null,
    candle_count: 100,
    end_exclusive_ms: 180000,
    cursor_ms: 180000,
    fetched_count: 0,
    inserted_count: 0,
    revision: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    failure_reason: null,
    availability_reason: null,
    ...overrides,
  };
}

function mountModel() {
  let model!: ReturnType<typeof useHistoryDownloads>;
  const wrapper = mount(
    defineComponent({
      setup() {
        model = useHistoryDownloads(7);
        return () => h('div');
      },
    }),
  );
  return { wrapper, model };
}

beforeEach(() => {
  vi.clearAllMocks();
  events.clear();
  vi.mocked(fetchMarketCoverage).mockResolvedValue({
    market_id: 7,
    oldest_timestamp_ms: 180000,
    latest_timestamp_ms: 240000,
    candle_count: 2,
  });
  vi.mocked(fetchHistoryDownloads).mockResolvedValue([]);
  vi.mocked(requestHistoryDownload).mockResolvedValue(job());
  vi.mocked(changeHistoryDownload).mockResolvedValue(
    job({ status: 'cancelled', revision: 2 }),
  );
});

describe('background history download dialog', () => {
  it('submits an M1 count and closing only removes the browser subscription', async () => {
    const { model, wrapper } = mountModel();
    await flushPromises();
    model.mode.value = 'count';
    model.candleCount.value = 100;
    await model.submit();
    expect(requestHistoryDownload).toHaveBeenCalledWith({
      market_id: 7,
      request_id: expect.any(String),
      candle_count: 100,
    });
    expect(model.current.value?.status).toBe('queued');
    wrapper.unmount();
    expect(changeHistoryDownload).not.toHaveBeenCalled();
    expect(wsService.send).toHaveBeenLastCalledWith(
      'unsubscribeHistoryDownloads',
      { market_id: 7 },
    );
    expect(events.size).toBe(0);
  });

  it('retains submission identity after a lost acknowledgement and validates count', async () => {
    const { model, wrapper } = mountModel();
    await flushPromises();
    model.mode.value = 'count';
    model.candleCount.value = 0;
    await model.submit();
    expect(requestHistoryDownload).not.toHaveBeenCalled();
    model.candleCount.value = 100;
    vi.mocked(requestHistoryDownload).mockRejectedValueOnce(
      new Error('Connection lost'),
    );
    await model.submit();
    await model.submit();
    const calls = vi.mocked(requestHistoryDownload).mock.calls;
    expect(calls[0][0].request_id).toBe(calls[1][0].request_id);
    wrapper.unmount();
  });

  it('refreshes on matching changes and reconnect, preserving newer job revisions', async () => {
    vi.mocked(fetchHistoryDownloads).mockResolvedValue([
      job({ status: 'downloading', revision: 4 }),
    ]);
    const { model, wrapper } = mountModel();
    await flushPromises();
    vi.mocked(fetchHistoryDownloads).mockResolvedValue([job({ revision: 2 })]);
    events.get('historyDownloadChanged')?.({ market_id: 9 });
    expect(fetchHistoryDownloads).toHaveBeenCalledTimes(1);
    events.get('historyDownloadsConnection')?.({
      market_id: 7,
      connected: true,
    });
    await flushPromises();
    expect(fetchHistoryDownloads).toHaveBeenCalledTimes(2);
    expect(model.current.value?.revision).toBe(4);
    expect(model.connected.value).toBe(true);
    events.get('historyDownloadsConnection')?.({
      market_id: 7,
      connected: true,
    });
    await flushPromises();
    expect(fetchHistoryDownloads).toHaveBeenCalledTimes(3);
    events.get('disconnected')?.({});
    expect(model.connected.value).toBe(false);
    wrapper.unmount();
  });

  it('cancels explicitly and requests UTC dates without making a market setting', async () => {
    const { model, wrapper } = mountModel();
    await flushPromises();
    model.startDate.value = '1970-01-01';
    await model.submit();
    expect(requestHistoryDownload).toHaveBeenCalledWith({
      market_id: 7,
      request_id: expect.any(String),
      start_date: '1970-01-01',
    });
    await model.change('cancel');
    expect(changeHistoryDownload).toHaveBeenCalledWith('job-1', 'cancel');
    expect(model.current.value?.status).toBe('cancelled');
    wrapper.unmount();
  });
});
