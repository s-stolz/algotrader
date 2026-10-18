import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { UploadFileInfo } from 'naive-ui';

import UploadDataModal from '@/components/TopBar/Modals/Upload/UploadDataModal.vue';
import {
  getColumnMapping,
  getHeaderLine,
  getSeparator,
  parseCsvToCandles,
  uploadCandlesInBatches,
} from '@/components/TopBar/Modals/Upload/utils';
import type { Candle, Market, UploadColumnMapping } from '@/types/contracts';

const uploadMocks = vi.hoisted(() => ({
  getColumnMapping: vi.fn(),
  getHeaderLine: vi.fn(),
  getSeparator: vi.fn(),
  parseCsvToCandles: vi.fn(),
  uploadCandlesInBatches: vi.fn(),
}));

vi.mock('@/components/TopBar/Modals/Upload/utils', () => uploadMocks);

const market: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const candle: Candle = {
  timestamp_ms: 1_700_000_000_000,
  open: 1,
  high: 2,
  low: 0.5,
  close: 1.5,
  volume: 100,
};

const BaseModalStub = defineComponent({
  name: 'BaseModal',
  setup(_, { expose, slots }) {
    expose({ close: vi.fn() });
    return () => h('div', [
      slots.default?.(),
      slots.footer?.(),
    ]);
  },
});

const PassthroughStub = defineComponent({
  name: 'PassthroughStub',
  setup(_, { slots }) {
    return () => h('div', slots.default?.());
  },
});

const NButtonStub = defineComponent({
  name: 'NButton',
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      onClick: () => emit('click'),
    }, slots.default?.());
  },
});

function uploadInfo(file: File): UploadFileInfo {
  return {
    id: 'file-1',
    name: file.name,
    status: 'pending',
    file,
  };
}

describe('UploadDataModal', () => {
  beforeEach(() => {
    vi.mocked(getSeparator).mockReset();
    vi.mocked(getSeparator).mockReturnValue(',');
    vi.mocked(getHeaderLine).mockReset();
    vi.mocked(getHeaderLine).mockReturnValue(['timestamp', 'open', 'high', 'low', 'close', 'volume']);
    vi.mocked(getColumnMapping).mockReset();
    vi.mocked(getColumnMapping).mockReturnValue({
      0: 'timestamp',
      1: 'open',
      2: 'high',
      3: 'low',
      4: 'close',
      5: 'volume',
    });
    vi.mocked(parseCsvToCandles).mockReset();
    vi.mocked(parseCsvToCandles).mockResolvedValue([candle]);
    vi.mocked(uploadCandlesInBatches).mockReset();
    vi.mocked(uploadCandlesInBatches).mockResolvedValue();
  });

  it('loads preview mapping from selected files, clears it on remove, and emits after upload', async () => {
    const file = new File(
      ['timestamp,open,high,low,close,volume\n2024-01-01T00:00:00Z,1,2,0.5,1.5,100\n'],
      'candles.csv',
      { type: 'text/csv' },
    );
    const fileData = {
      file: uploadInfo(file),
      fileList: [uploadInfo(file)],
      event: undefined,
    };
    const wrapper = mount(UploadDataModal, {
      props: { market },
      global: {
        stubs: {
          BaseModal: BaseModalStub,
          NButton: NButtonStub,
          NTabPane: PassthroughStub,
          NTabs: PassthroughStub,
          UploadDataPreview: true,
          UploadDataSection: true,
          'base-modal': BaseModalStub,
          'n-button': NButtonStub,
          'n-tab-pane': PassthroughStub,
          'n-tabs': PassthroughStub,
          'upload-data-preview': true,
          'upload-data-section': true,
        },
      },
    });
    const modal = wrapper.vm as unknown as {
      columnMapping: UploadColumnMapping;
      fileList: UploadFileInfo[];
      handleFileChange: (data: typeof fileData) => Promise<void>;
      handleFileRemove: () => void;
      headerLine: string[];
      uploadData: () => Promise<void>;
    };

    await modal.handleFileChange(fileData);

    expect(getSeparator).toHaveBeenCalled();
    expect(modal.headerLine).toEqual(['timestamp', 'open', 'high', 'low', 'close', 'volume']);
    expect(modal.columnMapping[4]).toBe('close');

    modal.handleFileRemove();

    expect(modal.fileList).toEqual([]);
    expect(modal.headerLine).toEqual([]);
    expect(modal.columnMapping).toEqual({});

    await modal.handleFileChange(fileData);
    await modal.uploadData();

    expect(parseCsvToCandles).toHaveBeenCalledWith(
      file,
      ',',
      expect.objectContaining({ 0: 'timestamp', 4: 'close' }),
      expect.any(Function),
    );
    expect(uploadCandlesInBatches).toHaveBeenCalledWith('EURUSD', [candle], 'FX', expect.any(Function));
    expect(wrapper.emitted('upload-successful')).toEqual([[market]]);
  });
});
