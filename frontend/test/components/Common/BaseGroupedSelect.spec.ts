import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it } from 'vitest';
import BaseGroupedSelect from '@/components/Common/BaseGroupedSelect.vue';

const groups = [
  { label: 'Minutes', options: [{ label: 'M1', value: 'M1' }, { label: 'M5', value: 'M5', disabled: true }] },
  { label: 'Hours', options: [{ label: 'H1', value: 'H1' }, { label: 'H4', value: 'H4' }] },
];
let wrapper: ReturnType<typeof mount> | undefined;
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; });

async function openPicker(value = 'H1') {
  wrapper = mount(BaseGroupedSelect, { attachTo: document.body, props: { label: 'Timeframe', value, groups } });
  const trigger = wrapper.get('button[aria-haspopup="listbox"]');
  await trigger.trigger('keydown', { key: 'ArrowDown' });
  await flushPromises();
  return trigger;
}
function press(key: string) {
  document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
}

describe('BaseGroupedSelect', () => {
  it('opens at the current selection, skips disabled options, and restores focus on Escape without selecting', async () => {
    const trigger = await openPicker();
    expect(document.activeElement?.getAttribute('data-value')).toBe('H1');
    press('ArrowLeft');
    expect(document.activeElement?.getAttribute('data-value')).toBe('M1');
    press('End');
    expect(document.activeElement?.getAttribute('data-value')).toBe('H4');
    press('Escape');
    await flushPromises();
    expect(trigger.attributes('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(trigger.element);
    expect(wrapper?.emitted('update:value')).toBeUndefined();
  });

  it('emits a choice, closes, and reflects external value changes on reopening', async () => {
    const trigger = await openPicker();
    (document.querySelector('[role="option"][data-value="H4"]') as HTMLElement).click();
    await flushPromises();
    expect(wrapper?.emitted('update:value')).toEqual([['H4']]);
    expect(trigger.attributes('aria-expanded')).toBe('false');
    await wrapper?.setProps({ value: 'M1' });
    expect(trigger.text()).toBe('M1');
    await trigger.trigger('keydown', { key: 'ArrowDown' });
    await flushPromises();
    expect(document.querySelector('[role="option"][aria-selected="true"]')?.textContent).toBe('M1');
    expect(document.activeElement?.getAttribute('data-value')).toBe('M1');
  });

  it('disables an empty picker and keeps focus fallback independent of an unavailable current value', async () => {
    await openPicker('D1');
    expect(document.activeElement?.getAttribute('data-value')).toBe('M1');
    wrapper?.unmount();
    wrapper = mount(BaseGroupedSelect, { props: { label: 'Timeframe', value: 'D1', groups: [] } });
    expect(wrapper.get('button').attributes('disabled')).toBeDefined();
  });
});
