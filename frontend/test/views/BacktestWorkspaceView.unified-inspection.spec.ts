import { flushPromises } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import {
  setupWorkspaceTests,
  seedBacktest,
  run,
  mountWorkspace,
} from './backtestWorkspaceFixtures';

describe('Backtest inspection', () => {
  setupWorkspaceTests();

  it.each([1, 3])(
    'inspects and copies Runs from a Backtest containing %i Runs',
    async (count) => {
      const members = Array.from({ length: count }, (_, ordinal) =>
        run(`run-${ordinal}`),
      );
      seedBacktest(members);
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-backtest-run-0"]')
        .trigger('click');
      await flushPromises();
      expect(
        wrapper.get('[data-testid="workspace-current-backtest"]').isVisible(),
      ).toBe(true);
      expect(wrapper.find('[data-testid="comparison-columns"]').exists()).toBe(
        true,
      );
      await wrapper
        .get('[data-testid="workspace-member-run-0"]')
        .trigger('click');
      await flushPromises();
      expect(wrapper.text()).not.toContain(
        'Saved request and execution settings',
      );
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('run-0');
      await wrapper
        .get('[data-testid="workspace-create-from-run-run-0"]')
        .trigger('click');
      await flushPromises();
      const store = useBacktestWorkspaceStore();
      expect(store.creationDraft?.strategy.parameters).toEqual(
        members[0].request.strategy.parameters,
      );
      expect(store.creationSelections).toMatchObject({
        marketIds: [1],
        timeframes: ['M15'],
        allowedDirections: ['long_and_short'],
      });
      expect(store.reuseSource).toMatchObject({ kind: 'run', id: 'run-0' });
    },
  );
});
