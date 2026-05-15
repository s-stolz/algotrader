import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { describe, expect, it } from 'vitest';

import IndicatorSettingsStyles from '@/components/Chart/Indicator/IndicatorSettingsStyles.vue';
import type { IndicatorInfo, JsonObject } from '@/types/contracts';

const SlotStub = defineComponent({
  name: 'SlotStub',
  setup(_, { slots }) {
    return () => h('div', slots.default?.());
  },
});

const NInputNumberStub = defineComponent({
  name: 'NInputNumber',
  props: {
    value: {
      type: Number,
      default: null,
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('input', {
      ...attrs,
      type: 'number',
      value: props.value ?? '',
      onInput: (event: Event) => {
        const input = event.target as HTMLInputElement;
        emit('update:value', input.value === '' ? null : Number(input.value));
      },
    });
  },
});

const NInputStub = defineComponent({
  name: 'NInput',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('input', {
      ...attrs,
      type: 'text',
      value: props.value,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
    });
  },
});

const NColorPickerStub = defineComponent({
  name: 'NColorPicker',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () => h('input', {
      class: 'color-picker',
      type: 'color',
      value: props.value,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
    });
  },
});

const indicatorInfo: IndicatorInfo = {
  id: 7,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: false,
  inputs: [],
  outputs: {
    timestamp: { type: 'time' },
    sma: {
      type: 'line',
      plotOptions: {
        color: '#3366ff',
        lineWidth: 2,
        priceFormat: {
          precision: 2,
          minMove: 0.01,
        },
      },
    },
  },
  parameters: {
    length: {
      type: 'int',
      default: 14,
      min: 1,
      max: 200,
      step: 1,
    },
    source: {
      type: 'string',
      default: 'close',
      options: ['open', 'close'],
    },
  },
};

describe('IndicatorSettingsStyles', () => {
  it('emits style updates with the changed output styles', async () => {
    const wrapper = mount(IndicatorSettingsStyles, {
      props: {
        indicatorInfo,
      },
      global: {
        stubs: {
          NScrollbar: SlotStub,
          NH3: SlotStub,
          NColorPicker: NColorPickerStub,
          NInput: NInputStub,
          NInputNumber: NInputNumberStub,
          'n-scrollbar': SlotStub,
          'n-h3': SlotStub,
          'n-color-picker': NColorPickerStub,
          'n-input': NInputStub,
          'n-input-number': NInputNumberStub,
        },
      },
    });

    await wrapper.findAll('.n-input-number input')[0].setValue('4');

    expect(wrapper.emitted('update-styles')).toEqual([
      [{
        outputKey: 'sma',
        styles: {
          color: '#3366ff',
          lineWidth: 4,
          priceFormat: {
            precision: 2,
            minMove: 0.01,
          },
        } satisfies JsonObject,
      }],
    ]);
  });
});
