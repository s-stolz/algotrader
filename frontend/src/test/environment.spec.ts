import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';
import { describe, expect, it } from 'vitest';

const HarnessComponent = defineComponent({
  props: {
    label: {
      type: String,
      required: true,
    },
  },
  template: '<button type="button">{{ label }}</button>',
});

describe('frontend test environment', () => {
  it('mounts Vue components in a DOM-like test environment', () => {
    const wrapper = mount(HarnessComponent, {
      props: {
        label: 'Ready',
      },
    });

    expect(wrapper.get('button').text()).toBe('Ready');
    expect(document.createElement('div')).toBeInstanceOf(HTMLDivElement);
  });
});
