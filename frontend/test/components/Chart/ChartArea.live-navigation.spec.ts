import { expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import {
  setupChartAreaTests,
  setupStores,
  chartAreaMocks,
  mountChartArea,
} from './ChartArea.fixtures';
import { chartCandle } from './chartSession.fixtures';
setupChartAreaTests();
it('reloads after the navigation revision watcher stops the previous session', async () => {
  const { createChartSession } = await vi.importActual<
    typeof import('@/components/Chart/chartSession')
  >('@/components/Chart/chartSession');
  const fetchLatest = vi.fn(async () => [chartCandle(300_000)]);
  chartAreaMocks.createChartSession.mockImplementation((adapter) => {
    (adapter as Parameters<typeof createChartSession>[0]).fetchCandles =
      fetchLatest;
    const session = createChartSession(
      adapter as Parameters<typeof createChartSession>[0],
    );
    return {
      setSession: vi.fn(session.setSession.bind(session)),
      stop: vi.fn(session.stop.bind(session)),
      requestOlderHistory: vi.fn(session.requestOlderHistory.bind(session)),
    };
  });
  const { candlesticksStore } = setupStores();
  const wrapper = mountChartArea();
  try {
    await flushPromises();
    fetchLatest.mockClear();
    await wrapper.get('[aria-label="Go to latest candle"]').trigger('click');
    await flushPromises();
    expect(fetchLatest).toHaveBeenCalledOnce();
    expect(fetchLatest).toHaveBeenCalledWith({
      symbol: 'EURUSD',
      timeframe: 'M5',
      exchange: 'FX',
    });
    expect(candlesticksStore.data).toEqual([chartCandle(300_000)]);
  } finally {
    wrapper.unmount();
  }
});
