import { flushPromises, mount } from '@vue/test-utils';
import { h } from 'vue';
import { describe, expect, it } from 'vitest';
import { NTimePicker } from 'naive-ui';
import BaseTimePicker from '@/components/Common/BaseTimePicker.vue';
import DesignScope from '@/components/Common/DesignScope.vue';
import { designTokens } from '@/design/tokens';

describe('BaseTimePicker', () => {
  it('owns a themed overlay outside the drawer and removes it on unmount', async () => {
    const wrapper = mount(DesignScope, {
      attachTo: document.body,
      slots: {
        default: () =>
          h(BaseTimePicker, {
            formattedValue: '06:30',
            format: 'HH:mm',
            valueFormat: 'HH:mm',
            show: true,
          }),
      },
    });
    await flushPromises();
    const portal = document.querySelector<HTMLElement>(
      '.base-time-picker-portal',
    )!;
    expect(portal.parentElement).toBe(document.body);
    expect(portal.style.fontFamily).toBe(designTokens.font.ui);
    expect(wrapper.findComponent(NTimePicker).props('formattedValue')).toBe(
      '06:30',
    );
    expect(
      wrapper.findComponent(NTimePicker).props('themeOverrides')?.panelColor,
    ).toBe(designTokens.color.panel);
    wrapper.unmount();
    expect(portal.isConnected).toBe(false);
  });
});
