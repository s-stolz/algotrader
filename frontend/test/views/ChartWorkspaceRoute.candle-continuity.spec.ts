import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h, KeepAlive } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';
import { describe, expect, it, vi } from 'vitest';
import {
  candle,
  chartAreaMocks,
  setupChartAreaTests,
  setupStores,
} from '../components/Chart/ChartArea.fixtures';
import { createChartSession } from '@/components/Chart/chartSession';
import { fetchCandles } from '@/api/candleClient';
import { useMarketsStore } from '@/stores/marketsStore';
import type { CandleUpdateMessage } from '@/types/contracts';
import ChartWorkspaceRoute from '@/views/ChartWorkspaceRoute.vue';

async function openChart() {
  const real = await vi.importActual<
    typeof import('@/components/Chart/chartSession')
  >('@/components/Chart/chartSession');
  vi.mocked(createChartSession).mockImplementation(real.createChartSession);
  const stores = setupStores();
  vi.spyOn(useMarketsStore(), 'fetch').mockResolvedValue();
  const handlers = new Set<(message: CandleUpdateMessage) => void>();
  chartAreaMocks.wsOn.mockImplementation((event, handler) => {
    if (event === 'candleUpdate') handlers.add(handler);
  });
  chartAreaMocks.wsOff.mockImplementation((event, handler) => {
    if (event === 'candleUpdate') handlers.delete(handler);
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: ChartWorkspaceRoute },
      { path: '/backtests', component: { template: '<main>Backtests</main>' } },
    ],
  });
  await router.push('/');
  const host = defineComponent({
    setup: () => () =>
      h(RouterView, null, {
        default: ({ Component }: { Component: object }) =>
          h(KeepAlive, null, { default: () => h(Component) }),
      }),
  });
  const wrapper = mount(host, {
    global: { plugins: [router], stubs: { TheTopBar: true, Indicator: true } },
  });
  await vi.dynamicImportSettled();
  await flushPromises();
  await vi.waitFor(() => expect(handlers.size).toBe(1));
  await flushPromises();
  const emit = (timestamp: number) => {
    for (const handler of handlers)
      handler({
        ...candle(timestamp),
        type: 'candleUpdate',
        market_id: 1,
        symbol: 'EURUSD',
        timeframe: 'M5',
      });
  };
  return { ...stores, router, wrapper, handlers, emit };
}

describe('Chart route candle continuity', () => {
  setupChartAreaTests();

  it('keeps the live candle through repeated navigation and delayed history', async () => {
    const chart = await openChart();
    try {
      chart.emit(600_000);
      expect(chart.candlesticksStore.data.at(-1)?.timestamp_ms).toBe(600_000);
      for (let visit = 0; visit < 2; visit++) {
        await chart.router.push('/backtests');
        await flushPromises();
        expect(chart.handlers.size).toBe(0);
        let resolve!: (value: ReturnType<typeof candle>[]) => void;
        vi.mocked(fetchCandles).mockReturnValueOnce(
          new Promise((done) => {
            resolve = done;
          }),
        );
        await chart.router.push('/');
        await flushPromises();
        expect(chart.handlers.size).toBe(1);
        resolve([candle(300_000)]);
        await flushPromises();
        expect(chart.candlesticksStore.data.map((c) => c.timestamp_ms)).toEqual(
          [300_000, 600_000],
        );
      }
      expect(chartAreaMocks.infrastructure.init).toHaveBeenCalledOnce();
      chart.emit(900_000);
      expect(chart.candlesticksStore.data.at(-1)?.timestamp_ms).toBe(900_000);
    } finally {
      chart.wrapper.unmount();
    }
  });

  it('keeps a newer live update received while resumed history is pending', async () => {
    const chart = await openChart();
    try {
      chart.emit(600_000);
      await chart.router.push('/backtests');
      await flushPromises();
      let resolve!: (value: ReturnType<typeof candle>[]) => void;
      vi.mocked(fetchCandles).mockReturnValueOnce(
        new Promise((done) => {
          resolve = done;
        }),
      );
      await chart.router.push('/');
      await flushPromises();
      chart.emit(900_000);
      resolve([candle(300_000)]);
      await flushPromises();
      expect(chart.candlesticksStore.data.map((c) => c.timestamp_ms)).toEqual([
        300_000, 600_000, 900_000,
      ]);
    } finally {
      chart.wrapper.unmount();
    }
  });

  it('does not carry a live candle into a different timeframe', async () => {
    const chart = await openChart();
    try {
      chart.emit(600_000);
      await chart.router.push('/backtests');
      await flushPromises();
      chart.currentTimeframeStore.setCurrentTimeframe({
        label: 'H1',
        value: 'H1',
      });
      await chart.router.push('/');
      await flushPromises();
      expect(chart.candlesticksStore.data.map((c) => c.timestamp_ms)).toEqual([
        300_000,
      ]);
    } finally {
      chart.wrapper.unmount();
    }
  });
});
