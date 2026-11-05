import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, onTestFinished, vi } from 'vitest';
import {
  fetchStrategyCatalog,
  fetchBacktestCapabilities,
  previewBacktest,
  submitBacktest,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type {
  BacktestPreview,
  BacktestPreviewRequest,
} from '@/types/backtesterContracts';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';

export const catalog = [
  {
    strategy_id: 'sma_crossover',
    strategy_version: 1,
    display_name: 'SMA crossover',
    parameters: [
      {
        name: 'enabled',
        type: 'bool' as const,
        required: false,
        nullable: false,
        default: true,
      },
      {
        name: 'fast_window',
        type: 'int' as const,
        required: false,
        nullable: false,
        default: 5,
      },
      {
        name: 'label',
        type: 'str' as const,
        required: false,
        nullable: false,
        default: 'a',
        choices: ['a', 'b'],
      },
      {
        name: 'stop_loss_pct',
        type: 'float' as const,
        required: false,
        nullable: true,
        default: null,
      },
    ],
  },
];

export const reuseNames = [
  [null, '', '', null],
  ['Baseline', 'Baseline (copy)', '  Reviewed copy  ', 'Reviewed copy'],
  [
    '😀'.repeat(120),
    '😀'.repeat(113) + ' (copy)',
    '😀'.repeat(113) + ' (copy)',
    '😀'.repeat(113) + ' (copy)',
  ],
] as const;

export let pinia: ReturnType<typeof createPinia>;

export function openDrawer() {
  const wrapper = mount(BacktestCreationDrawer, {
    props: { show: true },
    global: { plugins: [pinia] },
    attachTo: document.body,
  });
  onTestFinished(() => wrapper.unmount());
  return wrapper;
}

export const selectionsCatalog = [
  {
    strategy_id: 'sma_crossover',
    strategy_version: 1,
    display_name: 'SMA crossover',
    parameters: [
      {
        name: 'fast_window',
        type: 'int' as const,
        required: false,
        nullable: false,
        default: 5,
      },
    ],
  },
];

export function previewFor(
  request: BacktestPreviewRequest,
  count: number,
): BacktestPreview {
  const market = { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' };
  return {
    max_backtest_candidate_count: 1000,
    normalized_selections: {
      markets: [market],
      timeframes: ['M1'],
      parameters: { fast_window: { mode: 'constant', values: [5] } },
      allowed_directions: ['long_and_short'],
    },
    raw_count: count,
    ready_count: count,
    excluded_count: 0,
    candidates: Array.from({ length: count }, (_, candidate_ordinal) => ({
      candidate_ordinal,
      market,
      timeframe: 'M1',
      parameters: { fast_window: 5 },
      allowed_directions: 'long_and_short',
      status: 'ready',
      run_ordinal: candidate_ordinal,
      request: {
        ...request,
        symbols: ['EURUSD'],
        exchange: 'FX',
        timeframe: 'M1',
        strategy: { ...request.strategy, parameters: { fast_window: 5 } },
      },
    })),
  };
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

export async function advancePreview() {
  await vi.advanceTimersByTimeAsync(170);
  await flushPromises();
}

export function creationSetup() {
  beforeEach(() => {
    vi.useFakeTimers();
    pinia = createPinia();
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
    vi.mocked(fetchStrategyCatalog).mockReset();
    vi.mocked(fetchStrategyCatalog).mockResolvedValue(catalog);
    vi.mocked(submitBacktest).mockReset();
    vi.mocked(previewBacktest).mockImplementation(async (request) =>
      previewFor(request, 1),
    );
    vi.mocked(submitBacktest).mockReset();
    vi.mocked(fetchBacktestCapabilities).mockReset();
    vi.mocked(fetchBacktestCapabilities).mockResolvedValue({
      max_backtest_candidate_count: 1000,
    });
  });
  afterEach(() => {
    document.body.innerHTML = '';
    vi.useRealTimers();
  });
}

export function selectionsSetup() {
  beforeEach(() => {
    vi.useFakeTimers();
    pinia = createPinia();
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
    useBacktestWorkspaceStore().creationSelections = {
      marketIds: [1],
      timeframes: ['M1'],
      allowedDirections: ['long_and_short'],
      parameters: {},
    };
    vi.mocked(fetchStrategyCatalog).mockReset();
    vi.mocked(fetchStrategyCatalog).mockResolvedValue(selectionsCatalog);
    vi.mocked(previewBacktest).mockReset();
    vi.mocked(fetchBacktestCapabilities).mockReset();
    vi.mocked(fetchBacktestCapabilities).mockResolvedValue({
      max_backtest_candidate_count: 1000,
    });
    vi.mocked(submitBacktest).mockReset();
    vi.mocked(submitBacktest).mockReset();
  });
  afterEach(() => {
    document.body.innerHTML = '';
    vi.useRealTimers();
  });
}
