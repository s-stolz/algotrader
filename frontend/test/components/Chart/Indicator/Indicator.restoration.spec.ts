import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, expect, it, vi } from 'vitest';
import Indicator from '@/components/Chart/Indicator/Indicator.vue';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import {
  IndicatorManager,
  type IndicatorChartManager,
} from '@/utils/chart/IndicatorManager';
import type { IndicatorInfo } from '@/types/contracts';

vi.mock('@/utils/websocketService', () => ({
  wsService: { send: vi.fn().mockResolvedValue(undefined) },
}));
const info: IndicatorInfo = {
  id: 1,
  indicator_id: 'currency_strength',
  name: 'Currency Strength',
  overlay: false,
  inputs: [],
  outputs: { eur: { type: 'line', plotOptions: {} } },
  parameters: {},
};

beforeEach(() => {
  setActivePinia(createPinia());
  localStorage.clear();
});

it('creates restored series and their pane when history arrives after mount', async () => {
  const store = useIndicatorsStore();
  const id = store.addIndicator(info, [], 1);
  const pane = document.createElement('div');
  let paneCreated = false;
  const chart = {
    series: new Map(),
    addSeries: vi.fn((key, _type, _data, _options, paneIndex) => {
      paneCreated = paneIndex === 1;
      chart.series.set(key, {});
      return null;
    }),
    updateSeriesOptions: vi.fn(),
    updateSeriesPoint: vi.fn(),
    setSeriesData: vi.fn(),
    removeSeries: vi.fn(),
    getPaneHtmlElement: vi.fn(async () => {
      if (!paneCreated)
        throw new Error('Invalid pane index: 1. Available panes: 1');
      return pane;
    }),
  } satisfies IndicatorChartManager;
  const manager = new IndicatorManager(chart);
  const wrapper = mount(Indicator, {
    props: { indicator: store.getById(id)!, indicatorManager: manager },
    global: {
      stubs: {
        teleport: true,
        IndicatorPanel: true,
        IndicatorSettingsModal: true,
      },
    },
  });
  await flushPromises();
  expect(chart.getPaneHtmlElement).not.toHaveBeenCalled();
  store.updateIndicatorData(id, [{ timestamp_ms: 1000, eur: 1 }]);
  await flushPromises();
  expect(chart.addSeries).toHaveBeenCalledWith(
    `${id}_eur`,
    'line',
    [{ time: 1, value: 1 }],
    expect.any(Object),
    1,
  );
  expect(store.getById(id)!.paneHtmlElement).toBe(pane);
  store.updateIndicatorData(id, [{ timestamp_ms: 1000, eur: 2 }]);
  await flushPromises();
  expect(chart.setSeriesData).toHaveBeenCalledWith(`${id}_eur`, [
    { time: 1, value: 2 },
  ]);
  wrapper.unmount();
});

it('preserves saved configuration when the renderer is destroyed', async () => {
  const store = useIndicatorsStore();
  await store.restorePersistedIndicators();
  const id = store.addIndicator(info, [], 1);
  const pane = document.createElement('div');
  store.updateIndicatorPaneElement(id, pane);
  const manager = new IndicatorManager({
    series: new Map(),
    addSeries: vi.fn(),
    updateSeriesOptions: vi.fn(),
    updateSeriesPoint: vi.fn(),
    setSeriesData: vi.fn(),
    removeSeries: vi.fn(),
    getPaneHtmlElement: vi.fn(),
  });
  await flushPromises();
  const saved = localStorage.getItem('algotrader_indicators');
  manager.destroy();
  await flushPromises();
  expect(store.getById(id)?.paneHtmlElement).toBeNull();
  expect(localStorage.getItem('algotrader_indicators')).toBe(saved);
});
