import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import BaseStepModal from '@/components/Common/BaseStepModal.vue';

describe('BaseStepModal', () => {
  it('constrains the rendered body so long forms scroll inside the card', () => {
    const wrapper = mount(BaseStepModal, {
      props: { show: true, title: 'Create', steps: ['Setup'], step: 0 },
      slots: {
        default: '<div>Form fields</div>',
        footer: '<button>Next</button>',
      },
    });
    try {
      const body = document.querySelector('.base-step-modal .step-body')!;
      const content = getComputedStyle(body.parentElement!);
      expect(content.display).toBe('flex');
      expect(content.flexDirection).toBe('column');
      expect(content.minHeight).toBe('0px');
      expect(content.overflow).toBe('hidden');
    } finally {
      wrapper.unmount();
    }
  });
});
