import { flushPromises, mount } from '@vue/test-utils';
import { NPopover } from 'naive-ui';
import { h } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import BasePopover from '@/components/Common/BasePopover.vue';
import DesignScope from '@/components/Common/DesignScope.vue';

describe('BasePopover', () => {
  it('preserves popover slots, sizing, and show updates with the drawer theme', async () => {
    const onUpdateShow = vi.fn();
    const wrapper = mount(BasePopover, {
      props: { show: true, trigger: 'click', width: 500, onUpdateShow },
      slots: { trigger: '<button>Columns</button>', default: 'Show columns' },
    });
    const popover = wrapper.getComponent(NPopover);
    expect(popover.props('width')).toBe(500);
    expect(document.body.querySelector('.base-popover')?.textContent).toContain(
      'Show columns',
    );
    expect(popover.props('themeOverrides')).toEqual(
      expect.objectContaining({
        color: '#131722',
        textColor: '#dce4ed',
        borderRadius: '6px',
        padding: '16px',
      }),
    );
    await wrapper.get('button').trigger('click');
    expect(onUpdateShow).toHaveBeenCalledWith(false);
    wrapper.unmount();
  });

  it('merges local theme overrides with shared defaults', () => {
    const wrapper = mount(BasePopover, {
      props: { themeOverrides: { color: '#202c38' } },
      slots: { trigger: '<button>Columns</button>' },
    });
    expect(wrapper.getComponent(NPopover).props('themeOverrides')).toEqual(
      expect.objectContaining({
        color: '#202c38',
        textColor: '#dce4ed',
      }),
    );
    wrapper.unmount();
  });

  it('keeps legacy overlays separate from an explicitly migrated overlay', async () => {
    const legacy = mount(BasePopover, {
      props: { show: true },
      slots: { trigger: '<button>Legacy</button>', default: 'Legacy content' },
    });
    const migrated = mount(DesignScope, {
      slots: {
        default: () =>
          h(
            BasePopover,
            { show: true },
            {
              trigger: () => h('button', 'Migrated'),
              default: () => 'Migrated content',
            },
          ),
      },
    });
    try {
      await flushPromises();
      const overlays = Array.from(
        document.querySelectorAll<HTMLElement>('.base-popover'),
      );
      const legacyOverlay = overlays.find((entry) =>
        entry.textContent?.includes('Legacy content'),
      );
      const migratedOverlay = overlays.find((entry) =>
        entry.textContent?.includes('Migrated content'),
      );
      expect(legacyOverlay?.classList.contains('base-popover--design')).toBe(
        false,
      );
      expect(legacyOverlay?.style.getPropertyValue('--design-font-ui')).toBe(
        '',
      );
      expect(migratedOverlay?.style.getPropertyValue('--design-font-ui')).toBe(
        'Tektur, sans-serif',
      );
      expect(
        migrated.getComponent(NPopover).props('themeOverrides'),
      ).toMatchObject({
        color: '#131722',
        textColor: '#dce4ed',
        fontSize: '13px',
      });
    } finally {
      migrated.unmount();
      legacy.unmount();
    }
  });
});
