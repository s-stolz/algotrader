import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchAvailableIndicators,
  requestIndicator,
} from '@/api/indicatorClient';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import {
  chartAreaMocks,
  setupStores,
  setupChartAreaTests,
  mountChartArea,
  backtestRun,
  latestChartSessionAdapter,
  eurUsdM5Key,
  candle,
} from './ChartArea.fixtures';

vi.mock('@/api/indicatorClient', () => ({
  fetchAvailableIndicators: vi.fn(),
  requestIndicator: vi.fn(),
}));

describe('ChartArea run-owned indicators', () => {
  setupChartAreaTests();
  it('loads after candle history and removes only the run group on mismatch', async () => {
    const { indicatorsStore, currentTimeframeStore } = setupStores('M5');
    chartAreaMocks.infrastructure.indicatorManager.removeIndicatorSeriesAndData.mockImplementation(
      (id: string) => indicatorsStore.removeIndicator(id),
    );
    const info = {
      id: 1,
      indicator_id: 'sma',
      name: 'SMA',
      overlay: true,
      inputs: [],
      outputs: { sma: { type: 'line' } },
      parameters: { window: { type: 'int', default: 20 } },
      supports_live: false,
    };
    const manual = indicatorsStore.addIndicator(info, [], 1);
    vi.mocked(fetchAvailableIndicators).mockResolvedValue([
      { id: 1, indicator_id: 'sma', name: 'SMA' },
    ]);
    vi.mocked(requestIndicator).mockResolvedValue({
      data: {
        indicator_info: info,
        indicator_data: [{ timestamp_ms: 300000, sma: 10 }],
      },
    });
    const overlay = useBacktestOverlayStore();
    overlay.selectedRun = backtestRun({
      request: { ...backtestRun().request, timeframe: 'M5' },
      diagnostics: {
        chart_indicators: {
          schema_version: 1,
          items: [{ indicator_id: 'sma', parameters: { window: 5 } }],
        },
      },
    });
    overlay.selectedRunId = 'run-123';
    mountChartArea();
    await flushPromises();
    expect(indicatorsStore.all).toHaveLength(1);
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300000),
    ]);
    await flushPromises();
    expect(indicatorsStore.all).toHaveLength(2);
    expect(
      indicatorsStore.all.find((item) => item.ownerRunId)?.parameters.window
        .value,
    ).toBe(5);
    currentTimeframeStore.setCurrentTimeframe({ label: 'M15', value: 'M15' });
    await flushPromises();
    expect(indicatorsStore.all.map((item) => item._id)).toEqual([manual]);
    expect(overlay.selectedRunId).toBe('run-123');
  });
});
