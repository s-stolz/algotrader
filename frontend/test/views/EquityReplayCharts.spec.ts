import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import EquityReplayCharts from '@/views/EquityReplayCharts.vue';

const { setData, remove, createChart, addSeries, fitContent, applyOptions, seriesOptions } = vi.hoisted(() => {
  const setData = vi.fn();
  const seriesOptions = vi.fn();
  const applyOptions = vi.fn();
  const addSeries = vi.fn((_kind: unknown, _options: { color: string }) => ({ setData, applyOptions: seriesOptions }));
  const fitContent = vi.fn();
  const remove = vi.fn();
  const createChart = vi.fn(() => ({
    addSeries,
    timeScale: () => ({ fitContent }),
    applyOptions,
    remove,
    removeSeries: vi.fn(),
  }));
  return { setData, addSeries, fitContent, remove, createChart, applyOptions, seriesOptions };
});

vi.mock('lightweight-charts', () => ({ createChart, LineSeries: 'LineSeries' }));

describe('EquityReplayCharts', () => {
  beforeEach(() => vi.clearAllMocks());

  it('converts millisecond points at the chart boundary and keeps negative drawdown', () => {
    const wrapper = mount(EquityReplayCharts, { props: { series: [{ runId: 'one', name: 'One', points: [
      { timestamp_ms: 1_700_000_000_123, equity: 100, drawdown_pct: 0 },
      { timestamp_ms: 1_700_000_060_123, equity: 95, drawdown_pct: -5 },
    ] }] } });

    expect(createChart).toHaveBeenCalledTimes(2);
    expect(setData).toHaveBeenNthCalledWith(1, [
      { time: 1_700_000_000, value: 100 },
      { time: 1_700_000_060, value: 95 },
    ]);
    expect(setData).toHaveBeenNthCalledWith(2, [
      { time: 1_700_000_000, value: 0 },
      { time: 1_700_000_060, value: -5 },
    ]);
    wrapper.unmount();
    expect(remove).toHaveBeenCalledTimes(2);
  });

  it('updates series without recreating chart canvases and fits the updated history', async () => {
    const run = { runId: 'one', name: 'One', points: [
      { timestamp_ms: 1_700_000_000_123, equity: 100, drawdown_pct: 0 },
    ] };
    const wrapper = mount(EquityReplayCharts, { props: { series: [run] } });
    await wrapper.setProps({ series: [{ ...run }] });
    expect(createChart).toHaveBeenCalledTimes(2);
    expect(remove).not.toHaveBeenCalled();
    expect(addSeries).toHaveBeenCalledTimes(2);
    await wrapper.setProps({ series: [] });
    expect(createChart).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it('refits dense histories after selection changes and container resizing', async () => {
    let resize = () => {};
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) { resize = callback; }
      observe() {}
      disconnect() {}
    });
    const points = Array.from({ length: 2000 }, (_, index) => ({
      timestamp_ms: 1_700_000_000_000 + index * 60_000, equity: 100 - index / 10000,
      drawdown_pct: -index / 10000,
    }));
    const wrapper = mount(EquityReplayCharts, { props: { series: [
      { runId: 'one', name: 'One', points },
    ] } });
    expect(fitContent).toHaveBeenCalledTimes(2);
    await wrapper.setProps({ series: [
      { runId: 'one', name: 'One', points },
      { runId: 'two', name: 'Two', points: points.map((point) => ({
        ...point, timestamp_ms: point.timestamp_ms + 30_000,
      })) },
    ] });
    expect(fitContent).toHaveBeenCalledTimes(4);
    expect(applyOptions).toHaveBeenCalledWith({ timeScale: { minBarSpacing: 1 / 4001 } });
    resize();
    expect(fitContent).toHaveBeenCalledTimes(6);
    expect(createChart).toHaveBeenCalledTimes(2);
    wrapper.unmount();
    vi.unstubAllGlobals();
  });

  it('gives tiny drawdowns enough percentage precision to remain visible', () => {
    const wrapper = mount(EquityReplayCharts, { props: { series: [
      { runId: 'one', name: 'One', points: [
        { timestamp_ms: 1_700_000_000_000, equity: 9999.97, drawdown_pct: -0.0003 },
      ] },
    ] } });
    const format = seriesOptions.mock.calls[0]![0].priceFormat;
    expect(format.formatter(-0.0003)).toBe('-0.000300%');
    expect(format.formatter(0)).toBe('0.000000%');
    expect(format.formatter(-0.00000001)).toBe('0.000000%');
    wrapper.unmount();
  });

  it('overlays stable run identities in both full-width charts', () => {
    const points = [{ timestamp_ms: 1_700_000_000_123, equity: 100,
      drawdown_pct: -2 }];
    const wrapper = mount(EquityReplayCharts, { props: { series: [
      { runId: 'one', name: 'First', ordinal: 0, points },
      { runId: 'two', name: 'Second', ordinal: 1, points },
    ] } });
    expect(wrapper.find('[aria-label="Equity chart"]').exists()).toBe(true);
    expect(wrapper.find('[aria-label="Drawdown chart"]').exists()).toBe(true);
    expect(wrapper.find('[aria-label="Compared runs"]').text()).toContain('#1');
    expect(wrapper.find('[aria-label="Compared runs"]').text()).toContain('#2');
    expect(wrapper.find('[aria-label="Compared runs"]').text()).not.toContain('one');
    expect(addSeries).toHaveBeenCalledTimes(4);
    expect(addSeries.mock.calls[0]?.[1].color).toBe(addSeries.mock.calls[1]?.[1].color);
    expect(addSeries.mock.calls[2]?.[1].color).toBe(addSeries.mock.calls[3]?.[1].color);
    expect(addSeries.mock.calls[0]?.[1].color).not.toBe(addSeries.mock.calls[2]?.[1].color);
    wrapper.unmount();
  });
});
