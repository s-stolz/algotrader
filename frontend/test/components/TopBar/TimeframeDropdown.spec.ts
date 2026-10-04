import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';
import TimeframeDropdown from '@/components/TopBar/TimeframeDropdown.vue';
import BaseGroupedSelect from '@/components/Common/BaseGroupedSelect.vue';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';

describe('TimeframeDropdown', () => {
  beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()); });

  it('keeps the picker synchronized with chart timeframe state and persists a chosen timeframe', async () => {
    const store = useCurrentTimeframeStore();
    store.setCurrentTimeframe({ label: 'H4', value: 'H4' });
    const wrapper = mount(TimeframeDropdown, { global: { stubs: { BaseGroupedSelect: true } } });
    const picker = wrapper.getComponent(BaseGroupedSelect);
    expect(picker.props('value')).toBe('H4');
    expect(picker.props('groups').map(group => group.label)).toEqual(['Minutes', 'Hours', 'Days']);
    picker.vm.$emit('update:value', 'M15');
    expect(store.value).toBe('M15');
    await wrapper.vm.$nextTick();
    expect(picker.props('value')).toBe('M15');
    setActivePinia(createPinia());
    expect(useCurrentTimeframeStore().value).toBe('M15');
    wrapper.unmount();
  });
});
