import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';
import SymbolSearchModal from '@/components/TopBar/Modals/SymbolSearchModal.vue';
import { useMarketsStore } from '@/stores/marketsStore';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useModalStore } from '@/stores/modalStore';
import type { Market } from '@/types/contracts';

const market: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

describe('SymbolSearchModal interactions', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    useModalStore().openModal('symbolSearch');
  });

  it('filters through the field and selects the matching identity with Enter', async () => {
    useMarketsStore().all = [market];
    const wrapper = mount(SymbolSearchModal);
    const input = wrapper.get('input[placeholder="Symbol"]');
    await input.setValue('eur');
    expect(wrapper.text()).toContain('EURUSD');
    expect(wrapper.find('[aria-selected="false"]').exists()).toBe(true);
    await input.trigger('keyup', { key: 'Enter' });
    expect(useCurrentMarketStore().symbol).toBe('EURUSD');
    expect(useCurrentMarketStore().exchange).toBe('FX');
    expect(useModalStore().activeModal).toBeNull();
    wrapper.unmount();
  });

  it('distinguishes an empty collection from an empty search and keeps Add available', async () => {
    const wrapper = mount(SymbolSearchModal);
    expect(wrapper.text()).toContain('Don’t have a broker yet?');
    useMarketsStore().all = [market];
    const input = wrapper.get('input[placeholder="Symbol"]');
    await input.setValue('missing');
    expect(wrapper.text()).toContain('No symbols match your search.');
    expect(wrapper.text()).not.toContain('Don’t have a broker yet?');
    await input.trigger('keyup', { key: 'Enter' });
    expect(useModalStore().activeModal).toBe('symbolSearch');
    await wrapper.get('[aria-label="Add Market"]').trigger('click');
    expect(wrapper.emitted('open-symbol-form-modal')).toEqual([[]]);
    wrapper.unmount();
  });
});
