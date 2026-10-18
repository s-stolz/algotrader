import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it } from 'vitest';

import { useModalStore } from '@/stores/modalStore';

import BaseModal from '@/components/Common/BaseModal.vue';

const NButtonStub = defineComponent({
  name: 'NButton',
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      onClick: () => emit('click'),
    }, slots.default?.());
  },
});

describe('BaseModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('renders when its modal id is active and closes through the modal store', async () => {
    const modalStore = useModalStore();
    modalStore.openModal('symbolSearch');

    const wrapper = mount(BaseModal, {
      props: {
        modalId: 'symbolSearch',
        title: 'Symbol',
      },
      slots: {
        default: '<p>Modal body</p>',
        footer: '<button>Footer action</button>',
      },
      global: {
        stubs: {
          NButton: NButtonStub,
          NIcon: true,
          CloseCircleOutline: true,
          'n-button': NButtonStub,
          'n-icon': true,
          'close-circle-outline': true,
        },
      },
    });

    expect(wrapper.text()).toContain('Symbol');
    expect(wrapper.text()).toContain('Modal body');

    await wrapper.find('.close-button').trigger('click');

    expect(modalStore.activeModal).toBeNull();
    expect(wrapper.find('.modal-backdrop').exists()).toBe(false);
  });

  it('does not render footer spacing without footer content', () => {
    const modalStore = useModalStore();
    modalStore.openModal('indicatorSearch');

    const wrapper = mount(BaseModal, {
      props: {
        modalId: 'indicatorSearch',
        title: 'Indicator',
      },
      slots: {
        default: '<p>Modal body</p>',
      },
      global: {
        stubs: {
          NButton: NButtonStub,
          NIcon: true,
          CloseCircleOutline: true,
          'n-button': NButtonStub,
          'n-icon': true,
          'close-circle-outline': true,
        },
      },
    });

    expect(wrapper.find('.modal-footer').exists()).toBe(false);
    expect(wrapper.findAll('.separator')).toHaveLength(1);
  });
});
