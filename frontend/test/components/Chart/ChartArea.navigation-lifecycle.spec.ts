import { defineComponent, h, KeepAlive, ref } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import {
  setupChartAreaTests,
  setupStores,
  latestChartSession,
} from './ChartArea.fixtures';
import ChartArea from '@/components/Chart/ChartArea.vue';
import { useTradeNavigationStore } from '@/stores/tradeNavigationStore';

describe('chart navigation lifecycle', () => {
  setupChartAreaTests();
  it('offers a floating action to reload the live chart', async () => {
    setupStores();
    const wrapper = mount(ChartArea, {
      global: { stubs: { Indicator: true } },
    });
    await flushPromises();
    await wrapper.get('[aria-label="Go to latest candle"]').trigger('click');
    await flushPromises();
    expect(latestChartSession().setSession).toHaveBeenLastCalledWith(
      { symbol: 'EURUSD', timeframe: 'M5', exchange: 'FX' },
      expect.any(Function),
    );
    expect(useTradeNavigationStore().destination).toBeNull();
    wrapper.unmount();
  });
  it('stops while hidden and resumes in the current chart context', async () => {
    const { currentTimeframeStore } = setupStores();
    const visible = ref(true);
    const host = defineComponent({
      setup: () => () =>
        h(KeepAlive, null, {
          default: () => (visible.value ? h(ChartArea) : null),
        }),
    });
    const wrapper = mount(host, { global: { stubs: { Indicator: true } } });
    await flushPromises();
    const session = latestChartSession();
    visible.value = false;
    await flushPromises();
    expect(session.stop).toHaveBeenCalled();
    expect(useTradeNavigationStore().destination).toBeNull();
    const previousCalls = session.setSession.mock.calls.length;
    currentTimeframeStore.setCurrentTimeframe({ label: 'H1', value: 'H1' });
    await flushPromises();
    expect(session.setSession.mock.calls).toHaveLength(previousCalls);
    visible.value = true;
    await flushPromises();
    expect(session.setSession).toHaveBeenLastCalledWith(
      { symbol: 'EURUSD', exchange: 'FX', timeframe: 'H1' },
      expect.any(Function),
      undefined,
    );
    wrapper.unmount();
  });
});
