import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, expect, it, vi } from 'vitest';
import HistoryDownloadModal from '@/components/TopBar/Modals/history/HistoryDownloadModal.vue';
import {
  changeHistoryDownload,
  fetchHistoryDownloads,
  fetchMarketCoverage,
  requestHistoryDownload,
} from '@/api/historyDownloadClient';
import { useModalStore } from '@/stores/modalStore';
import type { Market } from '@/types/contracts';

vi.mock('@/api/historyDownloadClient', () => ({
  changeHistoryDownload: vi.fn(),
  fetchHistoryDownloads: vi.fn(),
  fetchMarketCoverage: vi.fn(),
  requestHistoryDownload: vi.fn(),
}));
vi.mock('@/utils/websocketService', () => ({
  wsService: { send: vi.fn(), on: vi.fn(), off: vi.fn() },
}));

const market: Market = {
  symbol_id: 7,
  symbol: 'EURUSD',
  exchange: 'BROKER',
  source_type: 'broker',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  useModalStore().openModal('historyDownload');
  vi.mocked(fetchMarketCoverage).mockResolvedValue({
    market_id: 7,
    oldest_timestamp_ms: null,
    latest_timestamp_ms: null,
    candle_count: 0,
  });
  vi.mocked(fetchHistoryDownloads).mockResolvedValue([]);
});

it.each(['queued', 'downloading'] as const)(
  'labels an accepted %s offer Close and preserves its background request',
  async (status) => {
    vi.mocked(requestHistoryDownload).mockImplementation(async () => {
      const accepted = {
        id: 'job-1',
        market_id: 7,
        status,
        start_ms: null,
        candle_count: 10000,
        end_exclusive_ms: 180000,
        cursor_ms: 180000,
        fetched_count: 0,
        inserted_count: 0,
        revision: 1,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        failure_reason: null,
        availability_reason: null,
      };
      vi.mocked(fetchHistoryDownloads).mockResolvedValue([accepted]);
      return accepted;
    });
    const wrapper = mount(HistoryDownloadModal, {
      props: { market, offer: true },
    });
    await flushPromises();
    const footer = () => wrapper.get('.modal-footer');
    expect(footer().text()).toContain('Skip');
    (wrapper.vm as unknown as { mode: string }).mode = 'count';
    await footer()
      .findAll('button')
      .find((button) => button.text() === 'Download')!
      .trigger('click');
    await flushPromises();
    expect(requestHistoryDownload).toHaveBeenCalledOnce();
    expect(footer().text()).not.toContain('Skip');
    const close = footer().get('button');
    expect(close.text()).toBe('Close');
    await close.trigger('click');
    expect(useModalStore().activeModal).toBeNull();
    expect(changeHistoryDownload).not.toHaveBeenCalled();
    wrapper.unmount();
    expect(changeHistoryDownload).not.toHaveBeenCalled();
  },
);
