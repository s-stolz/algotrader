import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useModalStore } from '@/stores/modalStore';
import type { Market } from '@/types/contracts';

import TopBarModals from '@/components/TopBar/Modals/TopBarModals.vue';

const market: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const updateCurrentMarket = vi.fn();

const SymbolSearchModalStub = defineComponent({
  name: 'SymbolSearchModal',
  emits: ['open-symbol-form-modal', 'remove-market', 'upload-data'],
  setup(_, { emit, expose }) {
    expose({ updateCurrentMarket });
    return () => h('div', [
      h('button', {
        class: 'open-symbol-form',
        onClick: () => emit('open-symbol-form-modal'),
      }, 'Add'),
      h('button', {
        class: 'remove-market',
        onClick: () => emit('remove-market', market),
      }, 'Remove'),
      h('button', {
        class: 'upload-data',
        onClick: () => emit('upload-data', market),
      }, 'Upload'),
    ]);
  },
});

const RemoveMarketModalStub = defineComponent({
  name: 'RemoveMarketModal',
  emits: ['market-removed'],
  setup(_, { emit }) {
    return () => h('button', {
      class: 'market-removed',
      onClick: () => emit('market-removed', market),
    }, 'Removed');
  },
});

const UploadDataModalStub = defineComponent({
  name: 'UploadDataModal',
  emits: ['upload-successful'],
  setup(_, { emit }) {
    return () => h('button', {
      class: 'upload-successful',
      onClick: () => emit('upload-successful', market),
    }, 'Uploaded');
  },
});

describe('TopBarModals', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    updateCurrentMarket.mockReset();
  });

  it('coordinates market modal events with kebab-case contracts', async () => {
    const modalStore = useModalStore();
    const wrapper = mount(TopBarModals, {
      global: {
        stubs: {
          IndicatorSearchModal: true,
          RemoveMarketModal: RemoveMarketModalStub,
          SymbolFormModal: true,
          SymbolSearchModal: SymbolSearchModalStub,
          UploadDataModal: UploadDataModalStub,
          'indicator-search-modal': true,
          'remove-market-modal': RemoveMarketModalStub,
          'symbol-form-modal': true,
          'symbol-search-modal': SymbolSearchModalStub,
          'upload-data-modal': UploadDataModalStub,
        },
      },
    });

    await wrapper.find('.open-symbol-form').trigger('click');
    expect(modalStore.activeModal).toBe('symbolForm');

    await wrapper.find('.remove-market').trigger('click');
    expect(modalStore.activeModal).toBe('removeMarket');
    await wrapper.find('.market-removed').trigger('click');
    expect(updateCurrentMarket).toHaveBeenCalledWith(market);

    await wrapper.find('.upload-data').trigger('click');
    expect(modalStore.activeModal).toBe('uploadData');
    await wrapper.find('.upload-successful').trigger('click');
    expect(updateCurrentMarket).toHaveBeenCalledWith(market);
  });
});
