import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TimeframeDropdown from '@/components/TopBar/TimeframeDropdown.vue';
import BaseGroupedSelect from '@/components/Common/BaseGroupedSelect.vue';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';

let mounted: ReturnType<typeof mount> | undefined;

afterEach(() => {
  mounted?.unmount();
  mounted = undefined;
  document.body.innerHTML = '';
  vi.useRealTimers();
});

describe('TimeframeDropdown', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('keeps the picker synchronized with chart timeframe state and persists a chosen timeframe', async () => {
    const store = useCurrentTimeframeStore();
    store.setCurrentTimeframe({ label: 'H4', value: 'H4' });
    const wrapper = mount(TimeframeDropdown, {
      global: { stubs: { BaseGroupedSelect: true } },
    });
    const picker = wrapper.getComponent(BaseGroupedSelect);
    expect(picker.props('value')).toBe('H4');
    expect(picker.props('groups').map((group) => group.label)).toEqual([
      'Minutes',
      'Hours',
      'Days',
    ]);
    picker.vm.$emit('update:value', 'M15');
    expect(store.value).toBe('M15');
    await wrapper.vm.$nextTick();
    expect(picker.props('value')).toBe('M15');
    setActivePinia(createPinia());
    expect(useCurrentTimeframeStore().value).toBe('M15');
    wrapper.unmount();
  });

  it('themes the real popup and retains a keyboard choice when remounted', async () => {
    const store = useCurrentTimeframeStore();
    store.setCurrentTimeframe({ label: 'H4', value: 'H4' });
    mounted = mount(TimeframeDropdown, { attachTo: document.body });
    const trigger = mounted.get('button[aria-haspopup="listbox"]');
    await trigger.trigger('keydown', { key: 'ArrowDown' });
    await flushPromises();
    const popup = document.querySelector('.base-popover') as HTMLElement;
    expect(popup).not.toBeNull();
    expect(popup.classList.contains('base-popover--design')).toBe(true);
    expect(popup.style.getPropertyValue('--design-font-ui')).toBe(
      'Tektur, sans-serif',
    );
    expect(popup.style.getPropertyValue('--design-text-secondary')).toBe(
      '12px',
    );
    expect(popup.style.getPropertyValue('--design-color-interactive')).toBe(
      '#63e2b7',
    );
    expect(document.activeElement?.getAttribute('data-value')).toBe('H4');
    document.activeElement?.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }),
    );
    expect(document.activeElement?.getAttribute('data-value')).toBe('D1');
    (document.activeElement as HTMLElement).click();
    await flushPromises();
    expect(store.value).toBe('D1');
    expect(trigger.text()).toBe('D1');
    expect(trigger.attributes('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(trigger.element);
    mounted.unmount();
    setActivePinia(createPinia());
    mounted = mount(TimeframeDropdown, { attachTo: document.body });
    const restored = mounted.get('button[aria-haspopup="listbox"]');
    expect(restored.text()).toBe('D1');
    await restored.trigger('keydown', { key: 'ArrowUp' });
    await flushPromises();
    expect(document.activeElement?.getAttribute('aria-selected')).toBe('true');
    document.activeElement?.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
    );
    await flushPromises();
    expect(restored.attributes('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(restored.element);
  });

  it('opens on hover and dismisses after leaving the popup', async () => {
    vi.useFakeTimers();
    mounted = mount(TimeframeDropdown, { attachTo: document.body });
    const trigger = mounted.get('button[aria-haspopup="listbox"]');
    await trigger.trigger('mouseenter');
    await vi.advanceTimersByTimeAsync(100);
    await flushPromises();
    expect(trigger.attributes('aria-expanded')).toBe('true');
    await trigger.trigger('mouseleave');
    await vi.advanceTimersByTimeAsync(200);
    await flushPromises();
    expect(trigger.attributes('aria-expanded')).toBe('false');
  });
});
