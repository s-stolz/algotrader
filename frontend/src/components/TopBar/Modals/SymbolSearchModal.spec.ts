import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it } from 'vitest';

import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { Market } from '@/types/contracts';

import SymbolSearchModal from './SymbolSearchModal.vue';

const marketA: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const marketB: Market = {
  symbol_id: 2,
  symbol: 'AAPL',
  exchange: 'NASDAQ',
  market_type: 'Stock',
  min_move: 0.01,
  timezone: 'America/New_York',
};

const BaseModalStub = defineComponent({
  name: 'BaseModal',
  setup(_, { expose, slots }) {
    expose({ close: () => undefined });
    return () => h('div', [
      slots.default?.(),
      slots.footer?.(),
    ]);
  },
});

const SymbolRowStub = defineComponent({
  name: 'SymbolRow',
  props: {
    market: {
      type: Object,
      required: true,
    },
  },
  emits: ['market-click', 'remove-market', 'upload-data'],
  setup(props, { emit }) {
    return () => h('button', {
      class: `row-${(props.market as Market).symbol}`,
      onClick: () => emit('market-click', props.market),
    }, (props.market as Market).symbol);
  },
});

describe('SymbolSearchModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('filters markets, selects the first enter match, and emits add-market requests', async () => {
    const marketsStore = useMarketsStore();
    const currentMarketStore = useCurrentMarketStore();
    marketsStore.all = [marketB, marketA];
    const wrapper = mount(SymbolSearchModal, {
      global: {
        stubs: {
          AddCircleOutline: true,
          BaseModal: BaseModalStub,
          NButton: true,
          NIcon: true,
          NInput: true,
          NQrCode: true,
          NScrollbar: { template: '<div><slot /></div>' },
          NSpace: { template: '<div><slot /></div>' },
          NText: { template: '<span><slot /></span>' },
          SearchOutline: true,
          SymbolRow: SymbolRowStub,
          'add-circle-outline': true,
          'base-modal': BaseModalStub,
          'n-button': true,
          'n-icon': true,
          'n-input': true,
          'n-qr-code': true,
          'n-scrollbar': { template: '<div><slot /></div>' },
          'n-space': { template: '<div><slot /></div>' },
          'n-text': { template: '<span><slot /></span>' },
          'search-outline': true,
          'symbol-row': SymbolRowStub,
        },
      },
    });
    const modal = wrapper.vm as unknown as {
      onAddMarketClick: () => void;
      onKeypressEnter: () => void;
      symbolInput: string;
    };

    modal.symbolInput = 'eur';
    modal.onKeypressEnter();

    expect(currentMarketStore.symbol).toBe('EURUSD');
    expect(currentMarketStore.exchange).toBe('FX');

    modal.onAddMarketClick();

    expect(wrapper.emitted('open-symbol-form-modal')).toEqual([[]]);
  });
});
