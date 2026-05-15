import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { describe, expect, it } from 'vitest';

import type { Market } from '@/types/contracts';

import SymbolRow from './SymbolRow.vue';

const market: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const NDropdownStub = defineComponent({
  name: 'NDropdown',
  emits: ['select'],
  setup(_, { emit, slots }) {
    return () => h('div', [
      slots.default?.(),
      h('button', {
        class: 'select-upload',
        onClick: (event: MouseEvent) => {
          event.stopPropagation();
          emit('select', 'upload');
        },
      }, 'Upload'),
      h('button', {
        class: 'select-remove',
        onClick: (event: MouseEvent) => {
          event.stopPropagation();
          emit('select', 'remove');
        },
      }, 'Remove'),
    ]);
  },
});

describe('SymbolRow', () => {
  it('emits market selection and action events with the row market', async () => {
    const wrapper = mount(SymbolRow, {
      props: { market },
      global: {
        stubs: {
          NButton: true,
          NDropdown: NDropdownStub,
          NIcon: true,
          EllipsisHorizontalCircleOutline: true,
          'n-button': true,
          'n-dropdown': NDropdownStub,
          'n-icon': true,
          'ellipsis-horizontal-circle-outline': true,
        },
      },
    });

    const row = wrapper.vm as unknown as {
      onMenuSelect: (key: string) => void;
      onRowClick: () => void;
    };
    row.onRowClick();
    row.onMenuSelect('upload');
    row.onMenuSelect('remove');

    expect(wrapper.emitted('market-click')).toEqual([[market]]);
    expect(wrapper.emitted('upload-data')).toEqual([[market]]);
    expect(wrapper.emitted('remove-market')).toEqual([[market]]);
  });
});
