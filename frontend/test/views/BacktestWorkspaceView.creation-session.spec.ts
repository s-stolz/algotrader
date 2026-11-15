import { initialScheduleDraft } from '@/types/backtest/schedule';
import {
  setupWorkspaceTests,
  run,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import BaseStepModal from '@/components/Common/BaseStepModal.vue';
describe('Backtest creation session reset', () => {
  setupWorkspaceTests();
  it.each(['submitted'] as const)(
    'starts a fresh creation session after %s',
    async (event) => {
      const store = useBacktestWorkspaceStore();
      store.creationDraft = {
        ...run('draft').request,
        name: 'Previous experiment',
        initial_capital: 25000,
        strategy: {
          strategy_id: 'sma',
          strategy_version: 1,
          parameters: { fast: 42 },
        },
      };
      store.creationSelections = {
        dailySchedule: initialScheduleDraft(),
        marketIds: [1],
        timeframes: ['H1'],
        allowedDirections: ['short_only'],
        parameters: {},
      };
      store.reuseSource = {
        kind: 'run',
        id: 'copied-source',
        strategyId: 'sma',
        strategyVersion: 1,
        historicalMetadata: null,
      };
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper.get('[data-testid="workspace-create"]').trigger('click');
      await vi.dynamicImportSettled();
      await flushPromises();
      const previous = wrapper.getComponent(BacktestCreationDrawer);
      previous.getComponent(BaseStepModal).vm.$emit('update:step', 2);
      await flushPromises();
      expect(previous.getComponent(BaseStepModal).props('step')).toBe(2);
      previous.vm.$emit('update:show', false);
      await flushPromises();
      await wrapper.get('[data-testid="workspace-create"]').trigger('click');
      expect(
        wrapper
          .getComponent(BacktestCreationDrawer)
          .getComponent(BaseStepModal)
          .props('step'),
      ).toBe(2);
      expect(store.creationDraft?.name).toBe('Previous experiment');
      previous.vm.$emit(event, 'accepted-experiment');
      await flushPromises();
      expect(wrapper.findComponent(BacktestCreationDrawer).exists()).toBe(
        false,
      );
      await wrapper.get('[data-testid="workspace-create"]').trigger('click');
      await vi.dynamicImportSettled();
      await flushPromises();
      const fresh = wrapper.getComponent(BacktestCreationDrawer);
      expect(fresh.props('show')).toBe(true);
      expect(fresh.getComponent(BaseStepModal).props('step')).toBe(0);
      expect(store.creationDraft).toMatchObject({
        name: '',
        initial_capital: 10000,
        timeframe: 'M1',
        strategy: {
          strategy_id: 'sma',
          strategy_version: 1,
          parameters: { fast: 5 },
        },
        execution: {
          allowed_directions: 'long_and_short',
          commission_bps: 0,
          slippage_bps: 0,
        },
      });
      expect(store.creationSelections).toMatchObject({
        marketIds: [1],
        timeframes: ['M1'],
        parameters: {},
      });
      expect(store.reuseSource).toBeNull();
      wrapper.unmount();
    },
  );
});
