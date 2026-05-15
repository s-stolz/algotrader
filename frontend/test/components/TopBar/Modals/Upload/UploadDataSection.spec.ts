import { mount } from '@vue/test-utils';
import { defineComponent, h, type PropType } from 'vue';
import { describe, expect, it } from 'vitest';
import type { UploadFileInfo } from 'naive-ui';

import UploadDataSection from '@/components/TopBar/Modals/Upload/UploadDataSection.vue';

const PassthroughStub = defineComponent({
  name: 'PassthroughStub',
  setup(_, { slots }) {
    return () => h('div', slots.default?.());
  },
});

const NUploadStub = defineComponent({
  name: 'NUpload',
  props: {
    beforeUpload: {
      type: Function as PropType<(data: { file: UploadFileInfo }) => boolean>,
      required: true,
    },
  },
  emits: ['change', 'remove'],
  setup(_, { emit, slots }) {
    return () => h('div', [
      slots.default?.(),
      h('button', {
        class: 'emit-change',
        onClick: () => emit('change', { fileList: [] }),
      }, 'Change'),
      h('button', {
        class: 'emit-remove',
        onClick: () => emit('remove'),
      }, 'Remove'),
    ]);
  },
});

describe('UploadDataSection', () => {
  it('emits file-change and file-remove events and rejects oversized files', async () => {
    const wrapper = mount(UploadDataSection, {
      props: { fileList: [] },
      global: {
        stubs: {
          CloudUploadOutline: true,
          NIcon: true,
          NP: true,
          NText: true,
          NUpload: NUploadStub,
          NUploadDragger: PassthroughStub,
          'cloud-upload-outline': true,
          'n-icon': true,
          'n-p': true,
          'n-text': true,
          'n-upload': NUploadStub,
          'n-upload-dragger': PassthroughStub,
        },
      },
    });

    const section = wrapper.vm as unknown as {
      beforeUpload: (data: { file: UploadFileInfo & { size?: number } }) => boolean;
      handleFileChange: (data: { fileList: UploadFileInfo[] }) => void;
      handleFileRemove: () => void;
    };
    section.handleFileChange({ fileList: [] });
    section.handleFileRemove();

    expect(wrapper.emitted('file-change')).toEqual([[{ fileList: [] }]]);
    expect(wrapper.emitted('file-remove')).toEqual([[]]);

    expect(section.beforeUpload({
      file: {
        id: 'large',
        name: 'large.csv',
        status: 'pending',
        size: 101 * 1024 * 1024,
      },
    })).toBe(false);
  });
});
