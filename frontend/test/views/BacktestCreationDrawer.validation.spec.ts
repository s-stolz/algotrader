import { flushPromises } from '@vue/test-utils';

import { NDatePicker, NDataTable, NInputNumber, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchStrategyCatalog,
  submitBacktestRun,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';

import { catalog, openDrawer, standaloneSetup } from './creationFixtures';
vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktestRun: vi.fn(),
  submitBacktestBatch: vi.fn(),
  previewParameterSweep: vi.fn(),
  fetchSweepCapabilities: vi.fn(),
}));

describe('creation validation', () => {
  standaloneSetup();
  it('rejects non-finite dates at submission as well as step navigation', async () => {
    const wrapper = openDrawer();
    await flushPromises();
    wrapper
      .findAllComponents(NDatePicker)[0]
      .vm.$emit('update:formatted-value', 'invalid');
    await flushPromises();
    (
      document.querySelector('[data-testid="creation-submit"]') as HTMLElement
    ).click();
    await flushPromises();
    expect(submitBacktestRun).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain(
      'End date must be after start date.',
    );
    wrapper.unmount();
  });
  it('distinguishes omitted defaults from explicit null in standalone review', async () => {
    const wrapper = openDrawer();
    await flushPromises();
    const runType = wrapper
      .findAllComponents(NSelect)
      .find(
        (select) => select.attributes('data-testid') === 'creation-run-type',
      )!;
    runType.vm.$emit('update:value', 'sweep');
    await flushPromises();
    const mode = wrapper
      .findAllComponents(NSelect)
      .find(
        (select) =>
          select.attributes('data-testid') === 'sweep-mode-fast_window',
      )!;
    mode.vm.$emit('update:value', 'values');
    await flushPromises();
    mode.vm.$emit('update:value', 'constant');
    runType.vm.$emit('update:value', 'standalone');
    await flushPromises();
    [...document.body.querySelectorAll('button')]
      .find((button) => button.textContent?.trim() === 'Review')!
      .click();
    await flushPromises();
    const table = wrapper.findComponent(NDataTable);
    expect(table.text()).toContain('5 (default)');
    expect(table.text()).toContain('null');
    expect(
      useBacktestWorkspaceStore().creationDraft?.strategy.parameters,
    ).not.toHaveProperty('fast_window');
    wrapper.unmount();
  });
  it('clears nullable fixed inputs inline while preserving empty strings', async () => {
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([
      {
        ...catalog[0],
        parameters: [
          {
            name: 'threshold',
            type: 'float',
            required: false,
            nullable: true,
            default: 2,
          },
          {
            name: 'label',
            type: 'str',
            required: false,
            nullable: true,
            default: '',
          },
        ],
      },
    ]);
    vi.mocked(submitBacktestRun).mockResolvedValue('nullable-run');
    const wrapper = openDrawer();
    await flushPromises();
    const number = wrapper
      .findAllComponents(NInputNumber)
      .find(
        (input) =>
          input.attributes('data-testid') === 'creation-param-threshold',
      )!;
    expect(number.props('clearable')).toBe(true);
    number.vm.$emit('update:value', null);
    expect(document.body.textContent).not.toContain('Set null');
    const submit = document.querySelector(
      '[data-testid="creation-submit"]',
    ) as HTMLElement;
    submit.click();
    await flushPromises();
    expect(
      vi.mocked(submitBacktestRun).mock.lastCall?.[0].strategy.parameters,
    ).toEqual({ threshold: null, label: '' });
    (
      document.querySelector(
        '[aria-label="Clear label to null"]',
      ) as HTMLElement
    ).click();
    await flushPromises();
    submit.click();
    await flushPromises();
    expect(
      vi.mocked(submitBacktestRun).mock.lastCall?.[0].strategy.parameters,
    ).toEqual({ threshold: null, label: null });
    wrapper.unmount();
  });
});
