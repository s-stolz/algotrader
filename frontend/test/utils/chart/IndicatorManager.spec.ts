import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { IndicatorDataPoint, IndicatorInfo } from '@/types/contracts';
import { wsService } from '@/utils/websocketService';

import { IndicatorManager } from '@/utils/chart/IndicatorManager';

vi.mock('@/utils/websocketService', () => ({
  wsService: {
    send: vi.fn(),
  },
}));

const indicatorInfo: IndicatorInfo = {
  id: 1,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: false,
  inputs: [],
  outputs: {
    timestamp: { type: 'time' },
    sma: {
      type: 'line',
      plotOptions: { color: '#fff', lineWidth: 2 },
    },
    signal: {
      type: 'histogram',
      plotOptions: { color: '#f00' },
    },
  },
  parameters: {},
};

const createChartManager = () => ({
  addSeries: vi.fn(),
  updateSeriesOptions: vi.fn(() => true),
  updateSeriesPoint: vi.fn(),
  removeSeries: vi.fn(),
  setSeriesData: vi.fn(() => true),
  getPaneHtmlElement: vi.fn(),
  series: new Map(),
});

describe('IndicatorManager', () => {
  it('attaches range drawings once, refreshes them, and detaches on removal', async () => {
    const chart = createChartManager();
    const series = { attachPrimitive: vi.fn(), detachPrimitive: vi.fn() };
    chart.series.set('ohlc', { series });
    const manager = new IndicatorManager(chart);
    const id = manager.indicatorsStore.addIndicator(
      {
        ...indicatorInfo,
        indicator_id: 'opening_range',
        overlay: true,
        outputs: {
          range_high: {
            type: 'opening_range',
            plotOptions: { showExtensions: true },
          },
        },
      },
      [
        {
          timestamp_ms: 3000,
          range_start_ms: 1000,
          range_end_ms: 2000,
          extension_end_ms: 5000,
          range_high: 12,
          range_low: 8,
          ready: 1,
        },
      ],
      7,
    );
    await manager.addIndicatorSeries(id);
    const primitive = series.attachPrimitive.mock.calls[0][0];
    const update = vi.spyOn(primitive, 'setData');
    manager.refreshIndicatorSeries(id);
    manager.updateIndicatorStyles(id, 'range_high', { color: '#ff0000' });
    expect(series.attachPrimitive).toHaveBeenCalledOnce();
    expect(chart.addSeries).not.toHaveBeenCalled();
    expect(update.mock.calls[1][1]).toMatchObject({ color: '#ff0000' });
    manager.indicatorsStore.updateIndicatorData(id, []);
    manager.refreshIndicatorSeries(id);
    expect(primitive.paneViews()).toEqual([]);
    manager.removeIndicatorSeriesAndData(id);
    expect(series.detachPrimitive).toHaveBeenCalledWith(primitive);
  });
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(wsService.send).mockReset();
    vi.mocked(wsService.send).mockResolvedValue();
  });

  it('transforms indicator output data into finite numeric chart points', () => {
    const manager = new IndicatorManager(createChartManager());
    const data: IndicatorDataPoint[] = [
      { timestamp_ms: 1_000, sma: 1.2 },
      { timestamp_ms: 2_000, sma: null },
      { timestamp_ms: 3_000, sma: 'not-a-number' },
      { timestamp_ms: Number.NaN, sma: 1.5 },
    ];

    expect(manager.transformIndicatorData(data, 'sma')).toEqual([
      { time: 1, value: 1.2 },
    ]);
  });

  it('adds non-timestamp Indicator outputs with default options', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(12345);
    const chartManager = createChartManager();
    const manager = new IndicatorManager(chartManager);
    const store = manager.indicatorsStore;
    const indicatorId = store.addIndicator(
      indicatorInfo,
      [{ timestamp_ms: 1_000, sma: 1.2 }],
      1,
    );

    await manager.addIndicatorSeries(indicatorId);

    expect(chartManager.addSeries).toHaveBeenCalledWith(
      `${indicatorId}_sma`,
      'line',
      [{ time: 1, value: 1.2 }],
      {
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
        color: '#fff',
        lineWidth: 2,
      },
      1,
    );
    expect(chartManager.addSeries).toHaveBeenCalledTimes(2);
    expect(chartManager.addSeries).toHaveBeenCalledWith(
      `${indicatorId}_signal`,
      'histogram',
      [],
      expect.any(Object),
      1,
    );
  });

  it('updates styles and data, applies live points, and removes series', () => {
    vi.spyOn(Date, 'now').mockReturnValue(12345);
    const chartManager = createChartManager();
    const manager = new IndicatorManager(chartManager);
    const store = manager.indicatorsStore;
    const indicatorId = store.addIndicator(
      indicatorInfo,
      [
        { timestamp_ms: 1_000, sma: 1.2, signal: null },
        { timestamp_ms: 2_000, sma: 1.3, signal: 2.1 },
      ],
      1,
    );
    chartManager.series.set(`${indicatorId}_sma`, {
      series: {
        setData: vi.fn(),
        update: vi.fn(),
        applyOptions: vi.fn(),
        barsInLogicalRange: vi.fn(),
      },
      type: 'line',
      data: [],
      options: {},
    });

    expect(
      manager.updateIndicatorStyles(indicatorId, 'sma', { color: '#0f0' }),
    ).toBe(true);
    manager.refreshIndicatorSeries(indicatorId);
    manager.updateIndicatorSeriesPoint(indicatorId, {
      timestamp_ms: 3_000,
      sma: 1.4,
      signal: 2.2,
    });
    manager.removeIndicatorSeriesAndData(indicatorId);

    expect(chartManager.updateSeriesOptions).toHaveBeenCalledWith(
      `${indicatorId}_sma`,
      {
        color: '#0f0',
      },
    );
    expect(chartManager.setSeriesData).toHaveBeenCalledWith(
      `${indicatorId}_sma`,
      [
        { time: 1, value: 1.2 },
        { time: 2, value: 1.3 },
      ],
    );
    expect(chartManager.updateSeriesPoint).toHaveBeenCalledWith(
      `${indicatorId}_sma`,
      {
        time: 3,
        value: 1.4,
      },
    );
    expect(chartManager.updateSeriesPoint).toHaveBeenCalledWith(
      `${indicatorId}_signal`,
      {
        time: 3,
        value: 2.2,
      },
    );
    expect(chartManager.removeSeries).toHaveBeenCalledWith(
      `${indicatorId}_sma`,
    );
    expect(chartManager.removeSeries).toHaveBeenCalledWith(
      `${indicatorId}_signal`,
    );
    expect(store.exists(indicatorId)).toBe(false);
  });
});
