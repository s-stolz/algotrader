import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { submitBacktest } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';

import { reuseRun } from '@/views/backtestReuse';

import { openDrawer, creationSetup } from './creationFixtures';
vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktest: vi.fn(),
  previewBacktest: vi.fn(),
  fetchBacktestCapabilities: vi.fn(),
}));

describe('standalone reuse', () => {
  creationSetup();

  it('keeps a removed saved strategy inspectable and unavailable for reuse', async () => {
    const saved = {
      run_id: 'removed',
      request_schema_version: 2,
      request: {
        symbols: ['EURUSD'],
        exchange: 'FX',
        timeframe: 'M1',
        start_ms: 1_714_521_600_000,
        end_ms: 1_714_608_000_000,
        engine: 'vectorized',
        data_granularity: 'bar',
        initial_capital: 10_000,
        strategy: { strategy_id: 'retired', parameters: {} },
        execution: {
          signal_timing: 'close',
          fill_timing: 'next_open',
          price_source: 'open',
          allow_partial_fills: false,
          allowed_directions: 'long_and_short',
          trade_accounting_policy: 'average_cost',
          gap_policy: 'skip',
          intrabar_exit_policy: 'conservative',
          commission_bps: 0,
          slippage_bps: 0,
        },
        run_metadata: null,
      },
    } as Parameters<typeof reuseRun>[0];
    useBacktestWorkspaceStore().createFromSaved(
      reuseRun(saved, [{ symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }]),
    );
    const wrapper = openDrawer();
    await flushPromises();
    expect(
      document.querySelector('[data-testid="reuse-removed-strategy"]')
        ?.textContent,
    ).toContain('no longer registered');
    expect(
      (
        document.querySelector(
          '[data-testid="creation-submit"]',
        ) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(submitBacktest).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
