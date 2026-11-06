import { expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import { requestIndicator } from '@/api/indicatorClient';
import {
  setupChartAreaTests,
  setupStores,
  mountChartArea,
  chartAreaMocks,
  indicatorInfo,
} from './ChartArea.fixtures';

vi.mock('@/api/indicatorClient', () => ({ requestIndicator: vi.fn() }));
setupChartAreaTests();
it('restores live Bollinger delivery when the chart remounts with retained stores', async () => {
  const { createChartSession } = await vi.importActual<
    typeof import('@/components/Chart/chartSession')
  >('@/components/Chart/chartSession');
  chartAreaMocks.createChartSession.mockImplementation((adapter) => {
    const session = createChartSession(
      adapter as Parameters<typeof createChartSession>[0],
    );
    return {
      setSession: vi.fn(session.setSession.bind(session)),
      stop: vi.fn(session.stop.bind(session)),
      requestOlderHistory: vi.fn(session.requestOlderHistory.bind(session)),
    };
  });
  const { indicatorsStore } = setupStores('M1');
  for (const action of [
    indicatorsStore.requestAllIndicators,
    indicatorsStore.unsubscribeAllLive,
    indicatorsStore.resetHistoryFlags,
  ]) {
    vi.mocked(action).mockRestore();
  }
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    frames.push(callback);
    return frames.length;
  });
  const info = {
    ...indicatorInfo,
    id: 3,
    indicator_id: 'bbands',
    overlay: true,
    outputs: {
      lower: { type: 'line' },
      mid: { type: 'line' },
      upper: { type: 'line' },
    },
  };
  const id = indicatorsStore.addIndicator(info, [], 3);
  vi.mocked(requestIndicator).mockResolvedValue({
    data: {
      indicator_info: info,
      indicator_data: [{ timestamp_ms: 300_000, lower: 1, mid: 1.5, upper: 2 }],
    },
  });
  const first = mountChartArea();
  await flushPromises();
  expect(requestIndicator).toHaveBeenCalled();
  expect(indicatorsStore.liveSubscriptions.has(id)).toBe(true);
  first.unmount();
  const second = mountChartArea();
  await flushPromises();
  const renderer =
    chartAreaMocks.infrastructure.indicatorManager.updateIndicatorSeriesPoint;
  renderer.mockClear();
  try {
    for (const timestamp of [360_000, 420_000]) {
      for (const handler of chartAreaMocks.indicatorHandlers)
        handler({
          type: 'indicatorUpdate',
          clientIndicatorId: id,
          timestamp_ms: timestamp,
          values: { lower: 1.1, mid: 1.6, upper: 2.1 },
        });
      for (const callback of frames.splice(0)) callback(0);
      expect(renderer).toHaveBeenLastCalledWith(id, {
        timestamp_ms: timestamp,
        lower: 1.1,
        mid: 1.6,
        upper: 2.1,
      });
    }
    expect(indicatorsStore.liveSubscriptions.has(id)).toBe(true);
    expect(chartAreaMocks.indicatorHandlers.size).toBe(1);
  } finally {
    second.unmount();
    await flushPromises();
  }
});
