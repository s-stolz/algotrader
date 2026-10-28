import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, vi } from 'vitest';
import {
  fetchStrategyCatalog,
  fetchSweepCapabilities,
  previewParameterSweep,
  submitBacktestBatch,
  submitBacktestRun,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type {
  SweepPreview,
  SweepPreviewRequest,
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
  return mount(BacktestCreationDrawer, {
    props: { show: true },
    global: { plugins: [pinia] },
    attachTo: document.body,
  });
}

export const sweepCatalog = [
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
  request: SweepPreviewRequest,
  count: number,
): SweepPreview {
  const market = { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' };
  return {
    max_sweep_candidate_count: 1000,
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
      member_ordinal: candidate_ordinal,
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

export function standaloneSetup() {
  beforeEach(() => {
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
    vi.mocked(submitBacktestRun).mockReset();
    vi.mocked(submitBacktestBatch).mockReset();
    vi.mocked(fetchSweepCapabilities).mockReset();
    vi.mocked(fetchSweepCapabilities).mockResolvedValue({
      max_sweep_candidate_count: 1000,
      batch_acceptance_enabled: false,
    });
  });
  afterEach(() => {
    document.body.innerHTML = '';
  });
}

export function sweepSetup() {
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
    useBacktestWorkspaceStore().creationSweepDraft = {
      isSweep: true,
      marketIds: [1],
      timeframes: ['M1'],
      allowedDirections: ['long_and_short'],
      parameters: {},
    };
    vi.mocked(fetchStrategyCatalog).mockReset();
    vi.mocked(fetchStrategyCatalog).mockResolvedValue(sweepCatalog);
    vi.mocked(previewParameterSweep).mockReset();
    vi.mocked(fetchSweepCapabilities).mockReset();
    vi.mocked(fetchSweepCapabilities).mockResolvedValue({
      max_sweep_candidate_count: 1000,
      batch_acceptance_enabled: false,
    });
    vi.mocked(submitBacktestRun).mockReset();
    vi.mocked(submitBacktestBatch).mockReset();
  });
  afterEach(() => {
    document.body.innerHTML = '';
    vi.useRealTimers();
  });
}
