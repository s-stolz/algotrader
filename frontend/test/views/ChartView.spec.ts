import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchMarkets } from '@/api/marketClient';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import type { Market } from '@/types/contracts';

import ChartView from '@/views/ChartView.vue';

vi.mock('@/api/marketClient', () => ({
  fetchMarkets: vi.fn(),
}));

const marketA: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const marketB: Market = {
  symbol_id: 2,
  symbol: 'EURUSD',
  exchange: 'ALT',
  market_type: 'Forex',
  min_move: 0.0001,
  timezone: 'UTC',
};

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

const ChartAreaModeStub = defineComponent({
  name: 'ChartArea',
  props: {
    interactionMode: {
      type: String,
      default: 'pan',
    },
  },
  setup(props) {
    return () => h('div', {
      'data-testid': 'chart-area-mode',
      'data-interaction-mode': props.interactionMode,
    });
  },
});

describe('ChartView startup', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    vi.mocked(fetchMarkets).mockReset();
  });

  it('fetches markets and initializes the current market when persisted state is invalid', async () => {
    vi.mocked(fetchMarkets).mockResolvedValue([marketA]);
    const currentMarketStore = useCurrentMarketStore();
    currentMarketStore.setMarket(marketB);

    mount(ChartView, {
      global: {
        stubs: {
          ChartArea: true,
          TheTopBar: true,
          'chart-area': true,
          'the-top-bar': true,
        },
      },
    });
    await flushPromises();

    expect(fetchMarkets).toHaveBeenCalledOnce();
    expect(currentMarketStore.symbol).toBe('EURUSD');
    expect(currentMarketStore.exchange).toBe('FX');
    expect(currentMarketStore.symbol_id).toBe(1);
  });

  it('owns Chart Interaction Mode as non-persisted chart UI state', async () => {
    vi.mocked(fetchMarkets).mockResolvedValue([marketA, marketB]);
    const currentMarketStore = useCurrentMarketStore();
    const currentTimeframeStore = useCurrentTimeframeStore();
    currentMarketStore.setMarket(marketA);
    currentTimeframeStore.setCurrentTimeframe({ label: 'M5', value: 'M5' });

    const wrapper = mount(ChartView, {
      global: {
        stubs: {
          ChartArea: ChartAreaModeStub,
          NButton: NButtonStub,
          NIcon: { template: '<span><slot /></span>' },
          TimeframeDropdown: true,
          TopBarModals: true,
          HandRightOutline: true,
          ListOutline: true,
          ResizeOutline: true,
          'chart-area': ChartAreaModeStub,
          'n-button': NButtonStub,
          'n-icon': { template: '<span><slot /></span>' },
          'timeframe-dropdown': true,
          'top-bar-modals': true,
        },
      },
    });
    await flushPromises();

    const panButton = wrapper.find('[data-testid="chart-interaction-mode-pan"]');
    const measureButton = wrapper.find('[data-testid="chart-interaction-mode-measure"]');
    expect(panButton.exists()).toBe(true);
    expect(measureButton.exists()).toBe(true);
    expect(panButton.text()).toBe('');
    expect(measureButton.text()).toBe('');
    expect(wrapper.find('[data-testid="chart-interaction-mode-pan-tooltip"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="chart-interaction-mode-measure-tooltip"]').exists()).toBe(
      false,
    );
    expect(panButton.attributes('aria-pressed')).toBe('true');
    expect(measureButton.attributes('aria-pressed')).toBe('false');
    expect(panButton.classes()).toContain('chart-interaction-mode-button--active');
    expect(measureButton.classes()).not.toContain('chart-interaction-mode-button--active');
    expect(wrapper.find('[data-testid="chart-area-mode"]').attributes('data-interaction-mode')).toBe(
      'pan',
    );

    await measureButton.trigger('click');

    expect(panButton.attributes('aria-pressed')).toBe('false');
    expect(measureButton.attributes('aria-pressed')).toBe('true');
    expect(panButton.classes()).not.toContain('chart-interaction-mode-button--active');
    expect(measureButton.classes()).toContain('chart-interaction-mode-button--active');
    expect(wrapper.find('[data-testid="chart-area-mode"]').attributes('data-interaction-mode')).toBe(
      'measure',
    );

    currentMarketStore.setMarket(marketB);
    currentTimeframeStore.setCurrentTimeframe({ label: 'H1', value: 'H1' });
    await flushPromises();

    expect(measureButton.attributes('aria-pressed')).toBe('true');
    expect(wrapper.find('[data-testid="chart-area-mode"]').attributes('data-interaction-mode')).toBe(
      'measure',
    );

    wrapper.unmount();
    setActivePinia(createPinia());
    localStorage.clear();
    vi.mocked(fetchMarkets).mockResolvedValue([marketA]);

    const freshWrapper = mount(ChartView, {
      global: {
        stubs: {
          ChartArea: ChartAreaModeStub,
          NButton: NButtonStub,
          NIcon: { template: '<span><slot /></span>' },
          TimeframeDropdown: true,
          TopBarModals: true,
          HandRightOutline: true,
          ListOutline: true,
          ResizeOutline: true,
          'chart-area': ChartAreaModeStub,
          'n-button': NButtonStub,
          'n-icon': { template: '<span><slot /></span>' },
          'timeframe-dropdown': true,
          'top-bar-modals': true,
        },
      },
    });
    await flushPromises();

    expect(
      freshWrapper.find('[data-testid="chart-interaction-mode-pan"]').attributes('aria-pressed'),
    ).toBe('true');
    expect(
      freshWrapper.find('[data-testid="chart-area-mode"]').attributes('data-interaction-mode'),
    ).toBe('pan');
  });
});
