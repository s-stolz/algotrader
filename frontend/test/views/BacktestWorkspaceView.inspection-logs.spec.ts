import {
  setupWorkspaceTests,
  run,
  mountWorkspace,
  trade,
  fill,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { NSelect } from 'naive-ui';
import ExecutionLogDrawer from '@/components/Backtest/ExecutionLogDrawer.vue';
import { describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestClosedTrades,
  fetchBacktestFills,
  getBacktestRun,
  listBacktestRuns,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';

import type { BacktestClosedTrade } from '@/types/backtesterContracts';

describe('production Backtest Workspace: inspection-logs', () => {
  setupWorkspaceTests();
  it(
    'opens the accessible execution drawer without changing selection ' +
      'and filters trades while showing all fills',
    async () => {
      const first = run('first', { name: 'First run' });
      const second = run('second');
      vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
      vi.mocked(getBacktestRun).mockResolvedValue(first);
      vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([
        trade(0, 'long', 'take_profit'),
        trade(1, 'short', 'stop_loss'),
      ]);
      vi.mocked(fetchBacktestFills).mockResolvedValue([
        fill(0, 'buy'),
        fill(1, 'sell'),
      ]);
      const wrapper = mountWorkspace();
      await flushPromises();
      expect(
        wrapper
          .get('[data-testid="workspace-history"]')
          .find('[data-testid^="workspace-log-"]')
          .exists(),
      ).toBe(false);
      await wrapper
        .find('[data-testid="workspace-run-first"]')
        .trigger('click');
      await flushPromises();

      const icon = wrapper.find(
        '[data-testid="workspace-current-backtest"] [data-testid="workspace-log-first"]',
      );
      expect(icon.attributes('aria-label')).toBe(
        'View execution log for First run',
      );
      expect(icon.attributes('title')).toBeUndefined();
      await icon.trigger('click');
      await flushPromises();
      expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('first');
      expect(fetchBacktestFills).toHaveBeenCalledWith('first');
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
      expect(document.body.textContent).toContain('Closed Trades (2)');
      expect(document.body.textContent).toContain('Fills (2)');
      expect(document.body.textContent).toContain('01 May 2024, 01:00:00');
      expect(document.body.textContent).toContain('-3');
      expect(document.body.textContent).toContain('1.08');

      const log = wrapper.findComponent(ExecutionLogDrawer);
      log.findAllComponents(NSelect)[0].vm.$emit('update:value', 'short');
      await wrapper.vm.$nextTick();
      expect(
        document.body.querySelectorAll(
          '[data-testid="execution-trades-table"] tbody tr',
        ),
      ).toHaveLength(1);
      expect(document.body.textContent).toContain('stop loss');
      log.findAllComponents(NSelect)[1].vm.$emit('update:value', 'signal');
      await wrapper.vm.$nextTick();
      expect(document.body.textContent).toContain(
        'No Closed Trades match these filters.',
      );

      document.body
        .querySelector<HTMLButtonElement>(
          '[data-testid="execution-fills-tab"]',
        )!
        .click();
      await wrapper.vm.$nextTick();
      expect(
        document.body.querySelectorAll(
          '[data-testid="execution-fills-table"] tbody tr',
        ),
      ).toHaveLength(2);
      expect(document.body.textContent).toContain('sell');
      expect(
        document.body.querySelector(
          '[data-testid="execution-log-drawer"] input[type="search"]',
        ),
      ).toBeNull();
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
      document.body
        .querySelector<HTMLButtonElement>('.n-drawer-header__close')!
        .click();
      await wrapper.vm.$nextTick();
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
      expect(
        wrapper
          .find('[data-testid="workspace-current-backtest"] .run-identity span')
          .text(),
      ).toBe('First run');
      wrapper.unmount();
    },
  );

  it(
    'disables unavailable execution logs while distinguishing empty, ' +
      'filtered, and failed reads',

    async () => {
      const success = run('success');
      const failed = run('failed', { status: 'failed', metrics: null });
      const legacy = run('legacy', { result_schema_version: 2 });
      vi.mocked(listBacktestRuns).mockResolvedValue([success, failed, legacy]);
      const wrapper = mountWorkspace();
      await flushPromises();

      for (const id of ['legacy', 'failed']) {
        await wrapper
          .get(`[data-testid="workspace-run-${id}"]`)
          .trigger('click');
        await flushPromises();
        const button = wrapper.get(`[data-testid="workspace-log-${id}"]`);
        expect(button.attributes('disabled')).toBeDefined();
        expect(button.attributes('aria-label')).toContain(
          'Execution log unavailable',
        );
        expect(button.find('.unavailable-log-icon').exists()).toBe(true);
        await button.trigger('click');
      }
      expect(wrapper.findComponent(ExecutionLogDrawer).exists()).toBe(false);
      expect(fetchBacktestFills).not.toHaveBeenCalled();

      await wrapper
        .get('[data-testid="workspace-log-failed"]')
        .element.parentElement?.dispatchEvent(new MouseEvent('mouseenter'));
      await vi.waitFor(() =>
        expect(document.body.textContent).toContain(
          'failed run has no completed execution log',
        ),
      );

      await wrapper
        .get('[data-testid="workspace-run-success"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .find('[data-testid="workspace-log-success"]')
        .trigger('click');
      await flushPromises();
      expect(document.body.textContent).toContain(
        'This successful run has no executions.',
      );
      expect(fetchBacktestFills).toHaveBeenCalledTimes(1);

      vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([
        trade(0, 'long', 'signal'),
      ]);
      vi.mocked(fetchBacktestFills).mockResolvedValue([fill(0, 'buy')]);
      document.body
        .querySelector<HTMLButtonElement>('.n-drawer-header__close')!
        .click();
      await wrapper.vm.$nextTick();
      await wrapper
        .find('[data-testid="workspace-log-success"]')
        .trigger('click');
      await flushPromises();
      wrapper
        .findComponent(ExecutionLogDrawer)
        .findAllComponents(NSelect)[0]
        .vm.$emit('update:value', 'short');
      await wrapper.vm.$nextTick();
      expect(document.body.textContent).toContain(
        'No Closed Trades match these filters.',
      );

      vi.mocked(fetchBacktestClosedTrades).mockRejectedValue(
        new Error('Storage unavailable'),
      );
      document.body
        .querySelector<HTMLButtonElement>('.n-drawer-header__close')!
        .click();
      await wrapper.vm.$nextTick();
      await wrapper
        .find('[data-testid="workspace-log-success"]')
        .trigger('click');
      await flushPromises();
      expect(document.body.textContent).toContain(
        'Execution log unavailable. Storage unavailable',
      );
      wrapper.unmount();
    },
  );

  it('ignores execution-log responses from a previous run or a closed drawer', async () => {
    const first = run('first');
    const second = run('second');
    vi.mocked(listBacktestRuns).mockResolvedValue([first, second]);
    let resolveFirst!: (trades: BacktestClosedTrade[]) => void;
    vi.mocked(fetchBacktestClosedTrades).mockImplementation((id) =>
      id === 'first'
        ? new Promise((resolve) => {
            resolveFirst = resolve;
          })
        : Promise.resolve([trade(2, 'short', 'stop_loss')]),
    );
    vi.mocked(fetchBacktestFills).mockResolvedValue([fill(0, 'sell')]);
    const wrapper = mountWorkspace();
    await flushPromises();

    await wrapper.get('[data-testid="workspace-run-first"]').trigger('click');
    await flushPromises();
    const firstIcon = wrapper.find('[data-testid="workspace-log-first"]');
    expect(firstIcon.element.tagName).toBe('BUTTON');
    await firstIcon.trigger('keydown', { key: 'Enter' });
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
    await wrapper.find('[data-testid="workspace-log-first"]').trigger('click');
    await wrapper.get('[data-testid="workspace-run-second"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-log-second"]').trigger('click');
    await flushPromises();
    resolveFirst([trade(0, 'long', 'signal')]);
    await flushPromises();
    expect(document.body.textContent).toContain(
      'Execution log · Unnamed standalone run',
    );
    expect(document.body.textContent).toContain('short');
    expect(document.body.textContent).not.toContain('long');

    document.body
      .querySelector<HTMLButtonElement>('.n-drawer-header__close')!
      .click();
    await wrapper.vm.$nextTick();
    expect(
      document.body.querySelector('[data-testid="execution-log-drawer"]'),
    ).toBeNull();
    wrapper.unmount();
  });
});
