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
    setActivePinia(createPinia());
    vi.mocked(fetchAvailableIndicators)
      .mockReset()
      .mockResolvedValue([{ id: 1, indicator_id: 'sma', name: 'SMA' }]);
    vi.mocked(requestIndicator).mockReset().mockResolvedValue(response);
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

  it('fails the group atomically when one calculation is unavailable', async () => {
    const { store, coordinator } = fixture();
    const manual = store.addIndicator(info, [], 1);
    vi.mocked(requestIndicator)
      .mockResolvedValueOnce(response)
      .mockRejectedValueOnce(new Error('Unavailable'));
    await coordinator.load(run, key);
    expect(coordinator.error.value).toBe('Unavailable');
    expect(store.all.map((item) => item._id)).toEqual([manual]);
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
    expect(coordinator.error.value).toContain('unsupported');
  });
});
