import { mount, flushPromises } from '@vue/test-utils';
import { defineComponent, h, nextTick } from 'vue';
import { beforeEach, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import SymbolFormModal from '@/components/TopBar/Modals/SymbolFormModal.vue';
import { createMarket, updateMarket } from '@/api/marketClient';
import { useMarketsStore } from '@/stores/marketsStore';
import { useModalStore } from '@/stores/modalStore';
import type { BrokerInstrument } from '@/types/brokerContracts';

vi.mock('@/api/marketClient', () => ({
  createMarket: vi.fn(),
  updateMarket: vi.fn(),
}));
const picker = defineComponent({
  name: 'BrokerInstrumentPicker',
  emits: ['verified'],
  setup: () => () => h('div'),
});
const instrument: BrokerInstrument = {
  source_type: 'broker',
  broker_provider: 'ctrader',
  broker_account_id: '42',
  broker_environment: 'demo',
  broker_symbol_id: 99,
  symbol: 'EURUSD',
  exchange: 'BROKER',
  timezone: 'UTC',
  market_type: 'Forex',
  settlement_currency: 'USD',
  minimum_quantity: 1000,
  quantity_step: 1000,
  min_move: null,
  suggested_min_move: 0.00001,
  contract_multiplier: null,
};

beforeEach(() => {
  setActivePinia(createPinia());
  useModalStore().openModal('symbolForm');
  vi.clearAllMocks();
  vi.spyOn(useMarketsStore(), 'fetch').mockResolvedValue();
  vi.mocked(createMarket).mockResolvedValue({
    symbol_id: 7,
    status: 'created',
  });
  vi.mocked(updateMarket).mockResolvedValue({
    symbol_id: 7,
    status: 'updated',
  });
});

it('requires confirmed tick size and multiplier for broker instruments', async () => {
  const wrapper = mount(SymbolFormModal, {
    global: { stubs: { BrokerInstrumentPicker: picker } },
  });
  const form = wrapper.vm as unknown as {
    sourceType: string;
    minMove: number;
    multiplier: number;
    addSymbol: () => Promise<void>;
  };
  form.sourceType = 'broker';
  await nextTick();
  await form.addSymbol();
  expect(createMarket).not.toHaveBeenCalled();
  wrapper.getComponent(picker).vm.$emit('verified', instrument);
  await nextTick();
  await form.addSymbol();
  expect(createMarket).not.toHaveBeenCalled();
  form.minMove = 0.00001;
  form.multiplier = 1;
  await form.addSymbol();
  await flushPromises();
  expect(createMarket).toHaveBeenCalledWith(
    expect.objectContaining({
      source_type: 'broker',
      broker_symbol_id: 99,
      broker_account_id: '42',
      symbol: 'EURUSD',
      exchange: 'BROKER',
      min_move: 0.00001,
      contract_multiplier: 1,
    }),
  );
  expect(wrapper.emitted('created')?.[0]).toEqual([
    expect.objectContaining({ symbol_id: 7, source_type: 'broker' }),
  ]);
  wrapper.unmount();
});

it('keeps broker identity read-only when editing instrument specifications', async () => {
  const market = {
    ...instrument,
    symbol_id: 7,
    timezone: 'UTC',
    market_type: 'Forex',
    settlement_currency: 'USD',
    minimum_quantity: 1000,
    quantity_step: 1000,
    min_move: 0.00001,
    contract_multiplier: 1,
  };
  const wrapper = mount(SymbolFormModal, { props: { market } });
  expect(
    wrapper.get('input[placeholder="Symbol"]').attributes('disabled'),
  ).toBeDefined();
  expect(
    wrapper.get('input[placeholder="Exchange"]').attributes('disabled'),
  ).toBeDefined();
  expect(wrapper.find('[aria-label="Data source"]').exists()).toBe(false);
  await wrapper.get('.new-symbol-button').trigger('click');
  await flushPromises();
  expect(updateMarket).toHaveBeenCalledWith(
    7,
    expect.objectContaining({ broker_symbol_id: 99, source_type: 'broker' }),
  );
  wrapper.unmount();
});
