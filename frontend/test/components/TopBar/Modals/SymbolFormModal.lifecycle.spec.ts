import { mount, flushPromises } from '@vue/test-utils';
import { beforeEach, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import SymbolFormModal from '@/components/TopBar/Modals/SymbolFormModal.vue';
import { createMarket } from '@/api/marketClient';
import { useMarketsStore } from '@/stores/marketsStore';
import { useModalStore } from '@/stores/modalStore';

vi.mock('@/api/marketClient', () => ({
  createMarket: vi.fn(),
  updateMarket: vi.fn(),
}));
beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  vi.spyOn(useMarketsStore(), 'fetch').mockResolvedValue();
});
it('does not reopen a history offer after the creation dialog is closed', async () => {
  let finish!: (value: { symbol_id: number; status: string }) => void;
  vi.mocked(createMarket).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const onCreated = vi.fn();
  useModalStore().openModal('symbolForm');
  const wrapper = mount(SymbolFormModal, { props: { onCreated } });
  const form = wrapper.vm as unknown as {
    symbol: string;
    exchange: string;
    marketType: string;
    currency: string;
    multiplier: number;
    minimum: number;
    step: number;
    addSymbol: () => Promise<void>;
  };
  Object.assign(form, {
    symbol: 'EURUSD',
    exchange: 'CSV',
    marketType: 'Forex',
    currency: 'USD',
    multiplier: 1,
    minimum: 1000,
    step: 1000,
  });
  const saving = form.addSymbol();
  wrapper.unmount();
  useModalStore().openModal('indicatorSearch');
  finish({ symbol_id: 7, status: 'created' });
  await saving;
  await flushPromises();
  expect(onCreated).not.toHaveBeenCalled();
  expect(useModalStore().activeModal).toBe('indicatorSearch');
});
