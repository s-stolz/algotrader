import { describe, expect, it } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import FixedInputsPopover from '@/views/workspace/heatmap/FixedInputsPopover.vue';

describe('fixed input keyboard focus', () => {
  it('enters the dialog and returns to its trigger on Escape and close', async () => {
    const wrapper = mount(FixedInputsPopover, {
      attachTo: document.body,
      props: { fields: [], values: {} },
    });
    try {
      const trigger = wrapper.get('button');
      await trigger.trigger('click');
      await flushPromises();
      const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
      expect(document.activeElement).toBe(dialog);
      expect(trigger.attributes('aria-controls')).toBe(dialog.id);
      dialog.dispatchEvent(
        new KeyboardEvent('keydown', {
          key: 'Escape',
          bubbles: true,
        }),
      );
      await flushPromises();
      expect(trigger.attributes('aria-expanded')).toBe('false');
      expect(document.activeElement).toBe(trigger.element);
      await trigger.trigger('click');
      await flushPromises();
      document
        .querySelector<HTMLButtonElement>('[aria-label="Close fixed inputs"]')!
        .click();
      await flushPromises();
      expect(trigger.attributes('aria-expanded')).toBe('false');
      expect(document.activeElement).toBe(trigger.element);
    } finally {
      wrapper.unmount();
    }
  });
});
