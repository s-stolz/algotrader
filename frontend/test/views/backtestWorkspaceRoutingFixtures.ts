import { createPinia, setActivePinia } from 'pinia';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, onTestFinished, vi } from 'vitest';
import App from '@/App.vue';
import router from '@/router';
import { useMarketsStore } from '@/stores/marketsStore';
import {
  getBacktest,
  getBacktestRun,
  listBacktests,
  listBacktestMembers,
} from '@/api/backtesterClient';
import { installBacktestSocket } from '../backtestEventSocket';
import {
  backtest as queuedBacktest,
  member,
} from '../components/Backtest/backtestOverviewFixtures';

const backtest = {
  ...queuedBacktest,
  accepted_definition: {
    ...queuedBacktest.accepted_definition,
    shared_request: {
      ...queuedBacktest.accepted_definition.shared_request,
      end_ms: 1_714_608_000_000,
    },
  },
};

vi.mock('@/views/ChartView.vue', () => ({
  default: { template: '<main>Chart page</main>' },
}));
vi.mock('@/api/backtesterClient', () => ({
  getBacktest: vi.fn(),
  getBacktestRun: vi.fn(),
  listBacktests: vi.fn(),
  listBacktestMembers: vi.fn(),
  listBacktestEvents: vi.fn().mockResolvedValue([]),
  fetchBacktestQueue: vi.fn().mockResolvedValue({
    snapshot_at_ms: Date.now(),
    active_run: null,
    last_heartbeat_ms: Date.now(),
    availability: 'healthy',
    stale_after_ms: 30_000,
    operational_faults: [],
    queued: [],
  }),
  fetchStrategyCatalog: vi.fn().mockResolvedValue([]),
  fetchBacktestCapabilities: vi.fn().mockResolvedValue({
    max_backtest_candidate_count: 1000,
  }),
  previewBacktest: vi.fn(),
  submitBacktest: vi.fn(),
  renameExperiment: vi.fn(),
  cancelBacktestRun: vi.fn(),
  controlBacktest: vi.fn(),
  deleteBacktest: vi.fn(),
  fetchBacktestClosedTrades: vi.fn().mockResolvedValue([]),
  fetchBacktestFills: vi.fn().mockResolvedValue([]),
  fetchBacktestEquityCurve: vi.fn().mockResolvedValue({
    availability: 'unavailable',
    reason: 'replay_metadata_missing',
    source_point_count: 0,
    returned_point_count: 0,
    sampled: false,
    equity_curve: [],
  }),
}));

export function setupRoutingTests() {
  beforeEach(() => {
    installBacktestSocket();
    localStorage.clear();
    vi.mocked(listBacktests).mockReset().mockResolvedValue([backtest]);
    vi.mocked(getBacktest).mockReset().mockResolvedValue(backtest);
    vi.mocked(getBacktestRun).mockReset().mockResolvedValue(member(0));
    vi.mocked(listBacktestMembers)
      .mockReset()
      .mockResolvedValue([member(0), member(1)]);
  });
}

export async function openWorkspace(path = '/backtests/backtest-1') {
  const pinia = createPinia();
  setActivePinia(pinia);
  useMarketsStore().all = [
    {
      symbol_id: 1,
      symbol: 'EURUSD',
      exchange: 'FX',
      market_type: 'Forex',
      min_move: 0.00001,
      timezone: 'UTC',
    },
  ];
  await router.replace(path);
  const wrapper = mount(App, {
    attachTo: document.body,
    global: { plugins: [pinia, router], stubs: { EquityReplayCharts: true } },
  });
  onTestFinished(() => wrapper.unmount());
  await vi.dynamicImportSettled();
  await flushPromises();
  return wrapper;
}

export { backtest };
