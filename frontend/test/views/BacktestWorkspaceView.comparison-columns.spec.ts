import {
  setupWorkspaceTests,
  run,
  mountWorkspace,
  toggleAnalysisColumns,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';
import { nextTick } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestEquityCurve,
  getBacktestRun,
  listBacktestRuns,
} from '@/api/backtesterClient';

import type { EquityReplayResponse } from '@/types/backtesterContracts';

describe('production Backtest Workspace: comparison-columns', () => {
  setupWorkspaceTests();
  it(
    'shows mixed selection and enables and disables whole column ' +
      'groups without changing other groups or run selection',
    async () => {
      const saved = run('groups');
      vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
      vi.mocked(getBacktestRun).mockResolvedValue(saved);
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-run-groups"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .find('[data-testid="comparison-select-groups"]')
        .setValue(true);
      await flushPromises();
      await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
      await flushPromises();
      const group = (title: string) =>
        document.querySelector<HTMLElement>(`[aria-label="${title}"]`)!;
      expect(
        group('Run settings')
          .querySelector('[data-testid="comparison-group-Run settings"]')
          ?.getAttribute('aria-checked'),
      ).toBe('mixed');
      expect(
        group('Performance')
          .querySelector('[data-testid="comparison-group-Performance"]')
          ?.getAttribute('aria-checked'),
      ).toBe('true');
      expect(
        group('Long / short')
          .querySelector('[data-testid="comparison-group-Long / short"]')
          ?.getAttribute('aria-checked'),
      ).toBe('false');
      for (const title of ['Run settings', 'Performance', 'Long / short']) {
        const checkbox = group(title).querySelector<HTMLElement>(
          `[data-testid="comparison-group-${title}"]`,
        )!;
        if (checkbox.getAttribute('aria-checked') !== 'true') {
          checkbox.click();
          await flushPromises();
        }
        expect(
          [...group(title).querySelectorAll<HTMLInputElement>('input')].every(
            (input) => input.checked,
          ),
        ).toBe(true);
        expect(checkbox.getAttribute('aria-checked')).toBe('true');
        checkbox.click();
        await flushPromises();
        expect(
          [...group(title).querySelectorAll<HTMLInputElement>('input')].every(
            (input) => !input.checked,
          ),
        ).toBe(true);
        expect(checkbox.getAttribute('aria-checked')).toBe('false');
        if (title !== 'Performance') {
          expect(
            group('Performance').querySelector<HTMLInputElement>('input')!
              .checked,
          ).toBe(true);
        }
        checkbox.click();
        await flushPromises();
      }
      expect(
        wrapper.get<HTMLInputElement>(
          '[data-testid="comparison-select-groups"]',
        ).element.checked,
      ).toBe(true);
      expect(
        wrapper.find('[data-testid="workspace-current-backtest"]').text(),
      ).toContain('Parameter: fast');
      await wrapper.find('[data-testid="comparison-columns"]').trigger('click');
      wrapper.unmount();
    },
  );

  it('updates column settings during pending replay without rebuilding the table', async () => {
    const saved = run('column-loading');
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    vi.mocked(getBacktestRun).mockResolvedValue(saved);
    vi.mocked(fetchBacktestEquityCurve).mockReturnValue(new Promise(() => {}));
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-run-column-loading"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .get('[data-testid="comparison-select-column-loading"]')
      .setValue(true);
    await flushPromises();
    const table = wrapper.get(
      '[data-testid="workspace-current-backtest"]',
    ).element;
    const detailCalls = vi.mocked(getBacktestRun).mock.calls.length;
    const replayCalls = vi.mocked(fetchBacktestEquityCurve).mock.calls.length;
    await wrapper.get('[data-testid="comparison-columns"]').trigger('click');
    await flushPromises();
    const checkbox = document.querySelector<HTMLInputElement>(
      '[data-testid="comparison-column-long-win"]',
    )!;
    try {
      checkbox.click();
      await nextTick();
      expect(checkbox.checked).toBe(true);
      expect(checkbox.disabled).toBe(false);
      expect(
        wrapper.get('[data-testid="workspace-current-backtest"]').text(),
      ).toContain('Long win rate');
      expect(getBacktestRun).toHaveBeenCalledTimes(detailCalls);
      expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(replayCalls);
      expect(
        wrapper.get('[data-testid="workspace-current-backtest"]').element,
      ).toBe(table);
      expect(
        wrapper.find('[data-testid="ending-loading-column-loading"]').exists(),
      ).toBe(true);
      checkbox.click();
      checkbox.click();
      await nextTick();
      expect(checkbox.checked).toBe(true);
    } finally {
      wrapper.unmount();
    }
  });

  it.each(['exact', 'unavailable', 'error'] as const)(
    'settles the ending-equity skeleton after %s replay without changing column settings',
    async (outcome) => {
      const saved = run('skeleton');
      vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
      vi.mocked(getBacktestRun).mockResolvedValue(saved);
      let resolveReplay!: (response: EquityReplayResponse) => void;
      let rejectReplay!: (error: Error) => void;
      vi.mocked(fetchBacktestEquityCurve).mockReturnValue(
        new Promise((resolve, reject) => {
          resolveReplay = resolve;
          rejectReplay = reject;
        }),
      );
      const wrapper = mountWorkspace();
      try {
        await flushPromises();
        await wrapper
          .get('[data-testid="workspace-run-skeleton"]')
          .trigger('click');
        await flushPromises();
        expect(
          wrapper.find('[data-testid="ending-loading-skeleton"]').exists(),
        ).toBe(true);
        await toggleAnalysisColumns(wrapper, ['ending']);
        expect(
          wrapper.find('[data-testid="ending-loading-skeleton"]').exists(),
        ).toBe(false);
        if (outcome === 'error') rejectReplay(new Error('Replay offline'));
        else
          resolveReplay({
            availability: outcome,
            reason:
              outcome === 'unavailable' ? 'replay_metadata_missing' : null,
            source_point_count: 1,
            returned_point_count: outcome === 'exact' ? 1 : 0,
            sampled: false,
            equity_curve:
              outcome === 'exact'
                ? [{ timestamp_ms: 1000, equity: 10123, drawdown_pct: 0 }]
                : [],
          });
        await flushPromises();
        expect(
          wrapper.get('[data-testid="workspace-current-backtest"]').text(),
        ).not.toContain('Ending equity');
        await toggleAnalysisColumns(wrapper, ['ending']);
        expect(
          wrapper.find('[data-testid="ending-loading-skeleton"]').exists(),
        ).toBe(false);
        const ending = wrapper.get('td[data-col-key="ending"]');
        expect(ending.text()).toBe(outcome === 'exact' ? '10123' : '—');
        if (outcome === 'error')
          expect(wrapper.text()).toContain('Replay offline');
      } finally {
        wrapper.unmount();
      }
    },
  );
});
