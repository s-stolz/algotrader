import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { describe, expect, it } from 'vitest';

import UploadDataPreview from '@/components/TopBar/Modals/Upload/UploadDataPreview.vue';
import type { UploadColumnMapping } from '@/types/contracts';

const PassthroughStub = defineComponent({
  name: 'PassthroughStub',
  setup(_, { slots }) {
    return () => h('div', slots.default?.());
  },
});

describe('UploadDataPreview', () => {
  it('emits updated column mappings without mutating the prop object', () => {
    const mapping: UploadColumnMapping = { 0: 'timestamp', 1: 'open' };
    const wrapper = mount(UploadDataPreview, {
      props: {
        headerLine: ['timestamp', 'open'],
        columnMapping: mapping,
      },
      global: {
        stubs: {
          NScrollbar: PassthroughStub,
          NSelect: true,
          NTable: PassthroughStub,
          'n-scrollbar': PassthroughStub,
          'n-select': true,
          'n-table': PassthroughStub,
        },
      },
    });

    (wrapper.vm as unknown as {
      updateColumnMapping: (index: number, value: 'close') => void;
    }).updateColumnMapping(1, 'close');

    expect(wrapper.emitted('update:column-mapping')).toEqual([[
      { 0: 'timestamp', 1: 'close' },
    ]]);
    expect(mapping).toEqual({ 0: 'timestamp', 1: 'open' });
  });
});
