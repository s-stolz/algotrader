import { createPinia, setActivePinia } from 'pinia';
import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createBacktestIndicators } from '@/components/Chart/backtestIndicators';
import {
  fetchAvailableIndicators,
  requestIndicator,
} from '@/api/indicatorClient';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { BacktestRun } from '@/types/backtesterContracts';
import type { IndicatorInfo, IndicatorResponse } from '@/types/contracts';

vi.mock('@/api/indicatorClient', () => ({
  fetchAvailableIndicators: vi.fn(),
  requestIndicator: vi.fn(),
}));
vi.mock('@/utils/websocketService', () => ({
  wsService: { send: vi.fn().mockResolvedValue(undefined) },
}));

const info: IndicatorInfo = {
  id: 1,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: true,
  inputs: [],
  outputs: { sma: { type: 'line', plotOptions: { color: '#fff' } } },
  parameters: { window: { type: 'int', default: 20 } },
  supports_live: false,
};
const response: IndicatorResponse = {
  data: {
    indicator_info: info,
    indicator_data: [{ timestamp_ms: 1000, sma: 2 }],
  },
};
const key = { symbol: 'TEST', exchange: 'FX', timeframe: 'M5' };
const run = {
  run_id: 'run-one',
  diagnostics: {
    chart_indicators: {
      schema_version: 1,
      items: [
        { indicator_id: 'sma', parameters: { window: 5 } },
        { indicator_id: 'sma', parameters: { window: 20 } },
      ],
    },
  },
} satisfies Pick<BacktestRun, 'run_id' | 'diagnostics'>;

function fixture() {
  const store = useIndicatorsStore();
  vi.spyOn(store, 'ensureCoverageForAll').mockResolvedValue();
  const manager = {
    removeIndicatorSeriesAndData: vi.fn((id: string) =>
      store.removeIndicator(id),
    ),
    updateMissingPaneHtmlElements: vi.fn().mockResolvedValue(undefined),
  };
  const coordinator = createBacktestIndicators({
    store,
    manager,
    getRange: () => ({
      oldestTimestampMs: 1000,
      newestTimestampMs: 2000,
      exclusiveEndMs: 302000,
    }),
  });
  coordinator.invalidate(run.run_id);
  return { store, manager, coordinator };
}

describe('backtest indicator group', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.mocked(fetchAvailableIndicators)
      .mockReset()
      .mockResolvedValue([{ id: 1, indicator_id: 'sma', name: 'SMA' }]);
    vi.mocked(requestIndicator).mockReset().mockResolvedValue(response);
  });

  it('loads both rolling range lines from the catalog and saved window', async () => {
    const rangeInfo: IndicatorInfo = {
      ...info,
      id: 8,
      indicator_id: 'rolling_range',
      name: 'Rolling High / Low',
      supports_live: true,
      outputs: {
        highest_high: { type: 'line', plotOptions: { color: '#EF5350' } },
        lowest_low: { type: 'line', plotOptions: { color: '#26A69A' } },
      },
    };
    vi.mocked(fetchAvailableIndicators).mockResolvedValue([
      { id: 8, indicator_id: 'rolling_range', name: rangeInfo.name },
    ]);
    vi.mocked(requestIndicator).mockResolvedValue({
      data: {
        indicator_info: rangeInfo,
        indicator_data: [
          { timestamp_ms: 1000, highest_high: 110, lowest_low: 90 },
        ],
      },
    });
    const { store, coordinator } = fixture();
    await coordinator.load(
      {
        ...run,
        diagnostics: {
          chart_indicators: {
            schema_version: 1,
            items: [
              { indicator_id: 'rolling_range', parameters: { window: 12 } },
            ],
          },
        },
      },
      key,
    );
    expect(store.all).toHaveLength(1);
    expect(store.all[0].parameters.window.value).toBe(12);
    expect(Object.keys(store.all[0].styles)).toEqual([
      'highest_high',
      'lowest_low',
    ]);
    expect(requestIndicator).toHaveBeenCalledWith(
      8,
      { ...key, endMs: 302000, limit: 500 },
      { parameters: { window: 12 } },
    );
  });

  it('restores saved parameters and styles without changing manual indicators', async () => {
    const { store, coordinator } = fixture();
    const manual = store.addIndicator(info, [], 1);
    await coordinator.load(run, key);
    const owned = store.all.filter((item) => item.ownerRunId);
    expect(owned).toHaveLength(2);
    expect(owned[0].parameters.window.value).toBe(5);
    expect(owned[1].parameters.window.value).toBe(20);
    expect(requestIndicator).toHaveBeenNthCalledWith(
      1,
      1,
      { ...key, endMs: 302000, limit: 500 },
      { parameters: { window: 5 } },
    );
    owned[0].styles.sma.color = '#00ff00';
    expect(
      store.updateIndicatorParameters(owned[0]._id, { window: 99 }),
    ).toBeNull();
    coordinator.invalidate(run.run_id);
    expect(store.all.map((item) => item._id)).toEqual([manual]);
    await coordinator.load(run, key);
    expect(store.all.find((item) => item.ownerRunId)?.styles.sma.color).toBe(
      '#00ff00',
    );
    coordinator.dispose();
    expect(store.all.map((item) => item._id)).toEqual([manual]);
  });

  it('preserves edited styles across refresh while the chart is mismatched', async () => {
    const first = fixture();
    await first.coordinator.load(run, key);
    first.store.all[1].styles.sma.color = '#123456';
    first.coordinator.invalidate(run.run_id);
    first.coordinator.dispose();
    setActivePinia(createPinia());
    const second = fixture();
    await second.coordinator.load(run, key);
    expect(second.store.all[1].styles.sma.color).toBe('#123456');
    expect(second.store.all[0].styles.sma.color).toBe('#fff');
    second.coordinator.invalidate('another-run');
    second.coordinator.invalidate(run.run_id);
    await second.coordinator.load(run, key);
    expect(second.store.all[1].styles.sma.color).toBe('#fff');
  });

  it('restores run panes before later manual panes', async () => {
    vi.mocked(requestIndicator).mockResolvedValue({
      data: {
        ...response.data,
        indicator_info: { ...info, overlay: false },
      },
    });
    const first = fixture();
    await first.coordinator.load(run, key);
    first.store.addIndicator({ ...info, overlay: false }, [], 1);
    expect(first.store.all.map((item) => item.paneIndex)).toEqual([1, 2, 3]);
    setActivePinia(createPinia());
    const second = fixture();
    const manualId = second.store.addIndicator(
      { ...info, overlay: false },
      [],
      1,
    );
    second.store.getById(manualId)!.paneIndex = 3;
    second.store.paneCount = 4;
    await second.coordinator.load(run, key);
    expect(second.store.all.map((item) => item.paneIndex)).toEqual([3, 1, 2]);
    expect(second.store.paneCount).toBe(4);
  });

  it('does not install responses from a deselected run', async () => {
    const { store, coordinator } = fixture();
    let resolve!: (value: IndicatorResponse) => void;
    vi.mocked(requestIndicator).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    const loading = coordinator.load(run, key);
    await flushPromises();
    coordinator.invalidate(null);
    resolve(response);
    await loading;
    expect(store.all).toEqual([]);
    expect(coordinator.isLoading.value).toBe(false);
  });

  it('restores available indicators when one calculation fails', async () => {
    const { store, coordinator } = fixture();
    const manual = store.addIndicator(info, [], 1);
    vi.mocked(requestIndicator)
      .mockResolvedValueOnce(response)
      .mockRejectedValueOnce(new Error('Unavailable'));
    await coordinator.load(run, key);
    expect(coordinator.error.value).toBeNull();
    expect(store.all).toHaveLength(2);
    expect(store.getById(manual)).toBeDefined();
  });

  it('does not infer indicators for legacy runs and reports unknown snapshot formats', async () => {
    const { coordinator } = fixture();
    await coordinator.load({ ...run, diagnostics: {} }, key);
    expect(fetchAvailableIndicators).not.toHaveBeenCalled();
    await coordinator.load(
      {
        ...run,
        diagnostics: { chart_indicators: { schema_version: 99, items: [] } },
      },
      key,
    );
    expect(coordinator.error.value).toBeNull();
  });
});
