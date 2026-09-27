import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import EquityReplayCharts from '@/views/EquityReplayCharts.vue';

const { setData, remove, createChart } = vi.hoisted(() => {
  const setData = vi.fn();
  const addSeries = vi.fn(() => ({ setData }));
  const fitContent = vi.fn();
  const remove = vi.fn();
  const createChart = vi.fn(() => ({
    addSeries,
    timeScale: () => ({ fitContent }),
    applyOptions: vi.fn(),
    remove,
  }));
  return { setData, addSeries, fitContent, remove, createChart };
});

vi.mock('lightweight-charts', () => ({ createChart, LineSeries: 'LineSeries' }));

describe('EquityReplayCharts', () => {
  beforeEach(() => vi.clearAllMocks());

  it('converts millisecond points at the chart boundary and keeps negative drawdown', () => {
    const wrapper = mount(EquityReplayCharts, { props: { points: [
      { timestamp_ms: 1_700_000_000_123, equity: 100, drawdown_pct: 0 },
      { timestamp_ms: 1_700_000_060_123, equity: 95, drawdown_pct: -5 },
    ] } });

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
});
