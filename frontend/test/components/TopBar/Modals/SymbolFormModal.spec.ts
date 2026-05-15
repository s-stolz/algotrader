import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h, type PropType } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createMarket } from '@/api/marketClient';
import { useMarketsStore } from '@/stores/marketsStore';
import type { MarketCreatePayload } from '@/types/contracts';

import SymbolFormModal from '@/components/TopBar/Modals/SymbolFormModal.vue';

vi.mock('@/api/marketClient', () => ({
  createMarket: vi.fn(),
}));

const BaseModalStub = defineComponent({
  name: 'BaseModal',
  setup(_, { expose, slots }) {
    const close = vi.fn();
    expose({ close });

    return () => h('div', [
      slots.default?.(),
      slots.footer?.(),
    ]);
  },
});

const NInputStub = defineComponent({
  name: 'NInput',
  props: {
    placeholder: {
      type: String,
      default: '',
    },
    value: {
      type: [String, Number, null] as PropType<string | number | null | undefined>,
      default: undefined,
    },
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () => h('input', {
      placeholder: props.placeholder,
      value: props.value ?? '',
      onInput: (event: Event) => {
        emit('update:value', (event.target as HTMLInputElement).value);
      },
    });
  },
});

const NInputNumberStub = defineComponent({
  name: 'NInputNumber',
  props: {
    value: {
      type: Number as PropType<number | null | undefined>,
      default: undefined,
    },
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () => h('input', {
      type: 'number',
      value: props.value ?? '',
      onInput: (event: Event) => {
        emit('update:value', Number((event.target as HTMLInputElement).value));
      },
    });
  },
});

const NSelectStub = defineComponent({
  name: 'NSelect',
  props: {
    options: {
      type: Array as PropType<Array<{ label: string; value: string }>>,
      default: () => [],
    },
    value: {
      type: String as PropType<string | null | undefined>,
      default: undefined,
    },
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () => h(
      'select',
      {
        value: props.value ?? '',
        onChange: (event: Event) => {
          emit('update:value', (event.target as HTMLSelectElement).value);
        },
      },
      [
        h('option', { value: '' }, ''),
        ...props.options.map((option) => h('option', { value: option.value }, option.label)),
      ],
    );
  },
});

const NButtonStub = defineComponent({
  name: 'NButton',
  emits: ['click'],
  setup(_, { emit, slots }) {
    return () => h('button', {
      onClick: () => emit('click'),
    }, slots.default?.());
  },
});

describe('SymbolFormModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(createMarket).mockReset();
    vi.mocked(createMarket).mockResolvedValue({ symbol_id: 1, status: 'created' });
  });

  it('creates markets through the typed client and refreshes markets after success', async () => {
    const marketsStore = useMarketsStore();
    vi.spyOn(marketsStore, 'fetch').mockResolvedValue();
    const wrapper = mount(SymbolFormModal, {
      global: {
        stubs: {
          BaseModal: BaseModalStub,
          NInput: NInputStub,
          NInputNumber: NInputNumberStub,
          NSelect: NSelectStub,
          NButton: NButtonStub,
          'base-modal': BaseModalStub,
          'n-input': NInputStub,
          'n-input-number': NInputNumberStub,
          'n-select': NSelectStub,
          'n-button': NButtonStub,
        },
      },
    });

    const form = wrapper.vm as unknown as {
      addSymbol: () => Promise<void>;
      exchange: string;
      marketType: string;
      symbol: string;
    };
    form.symbol = ' eurusd ';
    form.exchange = ' fx ';
    form.marketType = 'Forex';

    await form.addSymbol();
    await flushPromises();

    const expectedPayload: MarketCreatePayload = {
      symbol: 'EURUSD',
      exchange: 'FX',
      min_move: 0.00001,
      market_type: 'Forex',
      timezone: 'UTC',
    };
    expect(createMarket).toHaveBeenCalledWith(expectedPayload);
    expect(marketsStore.fetch).toHaveBeenCalledOnce();
  });
});
