import { mount } from '@vue/test-utils';
import { NDrawer, NDrawerContent } from 'naive-ui';
import { h } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import BaseDrawer from '@/components/Common/BaseDrawer.vue';
import DesignScope from '@/components/Common/DesignScope.vue';
import { designTokens } from '@/design/tokens';

describe('BaseDrawer', () => {
  it('preserves drawer content, sizing, and close interactions with the shared theme', async () => {
    const onUpdateShow = vi.fn();
    const wrapper = mount(BaseDrawer, {
      props: { show: true, width: 600, onUpdateShow },
      slots: {
        default: () =>
          h(
            NDrawerContent,
            { title: 'Details', closable: true },
            {
              default: () => 'Panel content',
              footer: () => h('button', 'Apply'),
            },
          ),
      },
    });

    expect(document.body.querySelector('.n-drawer')?.textContent).toContain(
      'Panel content',
    );
    expect(
      document.body.querySelector('.n-drawer-footer')?.textContent,
    ).toContain('Apply');
    const drawer = document.body.querySelector<HTMLElement>('.n-drawer')!;
    expect(drawer.style.width).toBe('600px');
    expect(drawer.style.fontSize).toBe('');
    expect(getComputedStyle(drawer).getPropertyValue('--n-color').trim()).toBe(
      '#171e27',
    );
    document.body
      .querySelector<HTMLButtonElement>('.n-drawer-header__close')!
      .click();
    expect(onUpdateShow).toHaveBeenCalledWith(false);
    await wrapper.setProps({ show: false });
    wrapper.unmount();
  });

  it('allows local theme overrides while retaining shared defaults', () => {
    const wrapper = mount(BaseDrawer, {
      props: { themeOverrides: { color: '#202c38' } },
    });

    expect(wrapper.findComponent(NDrawer).props('themeOverrides')).toEqual(
      expect.objectContaining({
        color: '#202c38',
        textColor: '#dce4ed',
        headerBorderBottom: '1px solid #2b3541',
      }),
    );
    wrapper.unmount();
  });

  it('carries the design into the teleported drawer and keeps close events', () => {
    const onUpdateShow = vi.fn();
    const wrapper = mount(DesignScope, {
      slots: {
        default: () =>
          h(
            BaseDrawer,
            { show: true, onUpdateShow },
            {
              default: () =>
                h(
                  NDrawerContent,
                  { title: 'Create', closable: true },
                  {
                    default: () => 'Draft fields',
                  },
                ),
            },
          ),
      },
    });
    const drawer = document.querySelector<HTMLElement>('.n-drawer')!;
    expect(drawer.style.fontFamily).toBe(designTokens.font.ui);
    expect(drawer.style.getPropertyValue('--design-color-error')).toBe(
      designTokens.color.error,
    );
    const theme = wrapper.findComponent(NDrawer).props('themeOverrides');
    expect(theme).toMatchObject({
      titleFontSize: designTokens.text.heading,
      bodyPadding: designTokens.space.xl,
      closeBorderRadius: designTokens.radius.circle,
    });
    document
      .querySelector<HTMLButtonElement>('.n-drawer-header__close')!
      .click();
    expect(onUpdateShow).toHaveBeenCalledWith(false);
    wrapper.unmount();
  });

  it('applies body typography outside the provider without flattening text roles', () => {
    const previousFontSize = document.body.style.fontSize;
    document.body.style.fontSize = '14px';
    const wrapper = mount(DesignScope, {
      slots: {
        default: () =>
          h(
            BaseDrawer,
            { show: true },
            {
              default: () =>
                h(
                  NDrawerContent,
                  { title: 'Review' },
                  {
                    default: () => [
                      h('p', { class: 'review-copy' }, 'Review the draft'),
                      h(
                        'p',
                        {
                          class: 'review-description',
                          style: { fontSize: designTokens.text.secondary },
                        },
                        'Confirm the selected Strategy Version',
                      ),
                    ],
                  },
                ),
            },
          ),
      },
    });

    try {
      const drawer = document.querySelector<HTMLElement>('.n-drawer')!;
      const copy = drawer.querySelector<HTMLElement>('.review-copy')!;
      const description = drawer.querySelector<HTMLElement>(
        '.review-description',
      )!;
      expect(drawer.closest('.design-scope')).toBeNull();
      expect(getComputedStyle(copy).fontSize).toBe('13px');
      expect(getComputedStyle(description).fontSize).toBe('12px');
      expect(
        getComputedStyle(drawer).getPropertyValue('--n-title-font-size').trim(),
      ).toBe('17px');
    } finally {
      wrapper.unmount();
      document.body.style.fontSize = previousFontSize;
    }
  });

  it('retains caller typography and title overrides in a migrated drawer', () => {
    const wrapper = mount(DesignScope, {
      slots: {
        default: () =>
          h(
            BaseDrawer,
            {
              show: true,
              style: { fontSize: '16px', fontFamily: 'monospace' },
              themeOverrides: { titleFontSize: '19px' },
            },
            {
              default: () =>
                h(
                  NDrawerContent,
                  { title: 'Details' },
                  {
                    default: () =>
                      h('p', { class: 'custom-copy' }, 'Custom copy'),
                  },
                ),
            },
          ),
      },
    });

    try {
      const drawer = document.querySelector<HTMLElement>('.n-drawer')!;
      const copy = drawer.querySelector<HTMLElement>('.custom-copy')!;
      expect(getComputedStyle(copy).fontSize).toBe('16px');
      expect(getComputedStyle(copy).fontFamily).toBe('monospace');
      expect(
        getComputedStyle(drawer).getPropertyValue('--n-title-font-size').trim(),
      ).toBe('19px');
    } finally {
      wrapper.unmount();
    }
  });
});
