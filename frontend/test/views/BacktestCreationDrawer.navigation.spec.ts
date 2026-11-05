import { initialScheduleDraft } from '@/types/backtest/schedule';
import CreationReview from '@/views/creation/CreationReview.vue';
import { flushPromises } from '@vue/test-utils';

import { NDatePicker, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';

import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';

import { openDrawer, creationSetup } from './creationFixtures';
vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktest: vi.fn(),
  previewBacktest: vi.fn(),
  fetchBacktestCapabilities: vi.fn(),
}));

describe('creation navigation', () => {
  creationSetup();
  it(
    'synchronizes steps and footer, validates dates, and keeps drafts ' +
      'after closing',
    async () => {
      const wrapper = openDrawer();
      await flushPromises();
      const click = async (text: string) => {
        const button = [...document.body.querySelectorAll('button')].find(
          (button) => button.textContent?.trim() === text,
        )!;
        button.click();
        await flushPromises();
      };
      const activeStep = () =>
        document.querySelector('[aria-current="step"]')?.textContent;
      expect(activeStep()).toBe('Setup');
      expect(wrapper.getComponent(CreationReview).isVisible()).toBe(false);
      const dates = wrapper.findAllComponents(NDatePicker);
      dates[1].vm.$emit('update:formatted-value', '2000-01-01');
      await click('Review');
      expect(activeStep()).toBe('Setup');
      expect(wrapper.getComponent(CreationReview).isVisible()).toBe(false);
      expect(document.body.textContent).toContain(
        'End date must be after start date',
      );
      dates[1].vm.$emit('update:formatted-value', '2030-01-01');
      await click('Parameters →');
      expect(activeStep()).toBe('Parameters');
      expect(wrapper.getComponent(CreationReview).isVisible()).toBe(false);
      await click('Review candidates →');
      expect(activeStep()).toBe('Review');
      expect(wrapper.getComponent(CreationReview).isVisible()).toBe(true);
      await click('Back');
      expect(activeStep()).toBe('Parameters');
      expect(wrapper.getComponent(CreationReview).isVisible()).toBe(false);
      await wrapper.setProps({ show: false });
      await wrapper.setProps({ show: true });
      expect(useBacktestWorkspaceStore().creationDraft?.end_ms).toBe(
        Date.UTC(2030, 0, 1),
      );
      wrapper.unmount();
    },
  );
  it(
    'clears a numeric Fixed input after switching from Values without ' +
      'losing its selections list',
    async () => {
      const store = useBacktestWorkspaceStore();
      store.creationSelections = {
        dailySchedule: initialScheduleDraft(),
        marketIds: [1],
        timeframes: ['M1'],
        allowedDirections: ['short_only'],
        parameters: {},
      };
      const wrapper = openDrawer();
      await flushPromises();
      const mode = wrapper
        .findAllComponents(NSelect)
        .find(
          (select) =>
            select.attributes('data-testid') === 'selections-mode-fast_window',
        )!;
      mode.vm.$emit('update:value', 'values');
      await flushPromises();
      const { default: BaseNumberValues } = await import(
        '@/components/Common/BaseNumberValues.vue'
      );
      wrapper
        .findAllComponents(BaseNumberValues)[0]
        .vm.$emit('update:value', [2, 4]);
      await flushPromises();
      mode.vm.$emit('update:value', 'constant');
      await flushPromises();
      expect(
        store.creationDraft?.strategy.parameters.fast_window,
      ).toBeUndefined();
      expect(store.creationSelections?.parameters.fast_window.valuesText).toBe(
        '2\n4',
      );
      expect(store.creationSelections?.allowedDirections).toEqual([
        'short_only',
      ]);
      wrapper.unmount();
    },
  );
});
