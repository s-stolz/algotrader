import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h, nextTick } from 'vue';
import { beforeEach, expect, it } from 'vitest';
import TopBarModals from '@/components/TopBar/Modals/TopBarModals.vue';
import { useModalStore } from '@/stores/modalStore';
import type { Market } from '@/types/contracts';

const broker: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
  source_type: 'broker',
};
const search = defineComponent({
  name: 'SymbolSearchModal',
  emits: ['download-history'],
  setup: () => () => h('div'),
});
const form = defineComponent({
  name: 'SymbolFormModal',
  emits: ['created'],
  setup: () => () => h('div'),
});
const history = defineComponent({
  name: 'HistoryDownloadModal',
  props: ['market', 'offer'],
  setup: () => () => h('div'),
});
function render() {
  return mount(TopBarModals, {
    global: {
      stubs: {
        SymbolSearchModal: search,
        SymbolFormModal: form,
        HistoryDownloadModal: history,
        IndicatorSearchModal: true,
        RemoveMarketModal: true,
        UploadDataModal: true,
      },
    },
  });
}

beforeEach(() => setActivePinia(createPinia()));
it('offers the same history dialog after broker creation and from its market menu', async () => {
  useModalStore().openModal('symbolForm');
  const wrapper = render();
  wrapper.getComponent(form).vm.$emit('created', broker);
  await nextTick();
  expect(wrapper.getComponent(history).props()).toEqual({
    market: broker,
    offer: true,
  });
  useModalStore().openModal('symbolSearch');
  await nextTick();
  wrapper.getComponent(search).vm.$emit('download-history', broker);
  await nextTick();
  expect(wrapper.getComponent(history).props()).toEqual({
    market: broker,
    offer: false,
  });
  wrapper.unmount();
});
it('does not offer broker downloads for custom market creation or menu events', async () => {
  useModalStore().openModal('symbolForm');
  const wrapper = render();
  const custom = { ...broker, source_type: 'custom' };
  wrapper.getComponent(form).vm.$emit('created', custom);
  await nextTick();
  expect(wrapper.findComponent(history).exists()).toBe(false);
  useModalStore().openModal('symbolSearch');
  await nextTick();
  wrapper.getComponent(search).vm.$emit('download-history', custom);
  await nextTick();
  expect(wrapper.findComponent(history).exists()).toBe(false);
  wrapper.unmount();
});
