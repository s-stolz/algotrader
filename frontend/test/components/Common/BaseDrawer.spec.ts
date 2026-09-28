import { mount } from '@vue/test-utils';
import { NDrawer, NDrawerContent } from 'naive-ui';
import { h } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import BaseDrawer from '@/components/Common/BaseDrawer.vue';

describe('BaseDrawer', () => {
  it('preserves drawer content, sizing, and close interactions with the shared theme', async () => {
    const onUpdateShow = vi.fn();
    const wrapper = mount(BaseDrawer, {
      props: { show: true, width: 600, onUpdateShow },
      slots: {
        default: () => h(NDrawerContent, { title: 'Details', closable: true }, {
          default: () => 'Panel content',
          footer: () => h('button', 'Apply'),
        }),
      },
    });

    expect(document.body.querySelector('.n-drawer')?.textContent).toContain('Panel content');
    expect(document.body.querySelector('.n-drawer-footer')?.textContent).toContain('Apply');
    const drawer = document.body.querySelector<HTMLElement>('.n-drawer')!;
    expect(drawer.style.width).toBe('600px');
    expect(getComputedStyle(drawer).getPropertyValue('--n-color').trim()).toBe('#171e27');
    document.body.querySelector<HTMLButtonElement>('.n-drawer-header__close')!.click();
    expect(onUpdateShow).toHaveBeenCalledWith(false);
    await wrapper.setProps({ show: false });
    wrapper.unmount();
  });

  it('allows local theme overrides while retaining shared defaults', () => {
    const wrapper = mount(BaseDrawer, {
      props: { themeOverrides: { color: '#202c38' } },
    });

    expect(wrapper.findComponent(NDrawer).props('themeOverrides')).toEqual(expect.objectContaining({
      color: '#202c38', textColor: '#dce4ed', headerBorderBottom: '1px solid #2b3541',
    }));
    wrapper.unmount();
  });
});
