import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { expect, it, vi } from 'vitest';
import { lazyComponent } from '@/components/Common/lazyComponent';

it('forwards reactive props, events and slots after the feature loads', async () => {
  const feature = defineComponent({
    props: { value: String },
    emits: ['change'],
    setup(props, { emit, slots }) {
      return () =>
        h('button', { onClick: () => emit('change', props.value) }, [
          props.value,
          slots.default?.(),
        ]);
    },
  });
  const loader = vi.fn(async () => ({ default: feature }));
  const changed = vi.fn();
  const wrapper = mount(lazyComponent(loader, 'feature'), {
    props: { value: 'First', onChange: changed },
    slots: { default: () => h('span', 'slot content') },
  });
  try {
    expect(wrapper.find('[aria-label="Loading feature"]').exists()).toBe(true);
    await flushPromises();
    expect(wrapper.get('button').text()).toBe('Firstslot content');
    await wrapper.setProps({ value: 'Second' });
    await wrapper.get('button').trigger('click');
    expect(changed).toHaveBeenCalledWith('Second');
    expect(wrapper.get('button').text()).toBe('Secondslot content');
    expect(loader).toHaveBeenCalledOnce();
  } finally {
    wrapper.unmount();
  }
});
