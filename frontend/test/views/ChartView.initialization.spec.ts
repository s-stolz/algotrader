import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h, KeepAlive, ref } from 'vue';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { fetchMarkets } from '@/api/marketClient';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';
import ChartView from '@/views/ChartView.vue';

vi.mock('@/api/marketClient', () => ({ fetchMarkets: vi.fn() }));
const stubs = { ChartArea: true, TheTopBar: true };
beforeEach(() => {
  setActivePinia(createPinia());
  localStorage.clear();
  vi.mocked(fetchMarkets).mockReset();
  vi.mocked(fetchMarkets).mockResolvedValue([]);
});
afterEach(() => vi.restoreAllMocks());

it('keeps loading feedback through initialization and defers hidden chart mounting', async () => {
  let finish!: () => void;
  vi.spyOn(useIndicatorsStore(), 'restorePersistedIndicators').mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const chartMounted = vi.fn();
  const ChartAreaStub = defineComponent({
    setup() {
      chartMounted();
      return () => h('chart-area-stub');
    },
  });
  const visible = ref(true);
  const host = defineComponent({
    setup: () => () =>
      h(KeepAlive, null, {
        default: () => (visible.value ? h(ChartView) : null),
      }),
  });
  const wrapper = mount(host, {
    global: { stubs: { ...stubs, ChartArea: ChartAreaStub } },
  });
  await flushPromises();
  expect(
    wrapper.get('[aria-label="Loading Chart"]').attributes('aria-busy'),
  ).toBe('true');
  expect(wrapper.find('chart-area-stub').exists()).toBe(false);
  visible.value = false;
  await flushPromises();
  finish();
  await flushPromises();
  expect(chartMounted).not.toHaveBeenCalled();
  visible.value = true;
  await flushPromises();
  expect(wrapper.find('chart-area-stub').exists()).toBe(true);
  expect(wrapper.findComponent(BaseAsyncState).exists()).toBe(false);
  expect(fetchMarkets).toHaveBeenCalledOnce();
  expect(chartMounted).toHaveBeenCalledOnce();
  wrapper.unmount();
});

it.each(['markets', 'indicators'])(
  'shows a retryable error when %s initialization fails',
  async (owner) => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    if (owner === 'markets')
      vi.mocked(fetchMarkets).mockRejectedValueOnce(new Error('offline'));
    else
      vi.spyOn(useIndicatorsStore(), 'restorePersistedIndicators')
        .mockRejectedValueOnce(new Error('offline'))
        .mockResolvedValue();
    const wrapper = mount(ChartView, { global: { stubs } });
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'Couldn’t initialize Chart.',
    );
    expect(wrapper.find('chart-area-stub').exists()).toBe(false);
    await wrapper
      .get('[aria-label="Retry: Chart unavailable"]')
      .trigger('click');
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.find('chart-area-stub').exists()).toBe(true);
    wrapper.unmount();
  },
);
