import { flushPromises } from '@vue/test-utils';

import { NDatePicker, NInputNumber } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import { fetchStrategyCatalog, submitBacktest } from '@/api/backtesterClient';

import { catalog, openDrawer, creationSetup } from './creationFixtures';
import { advancePreview } from './creationFixtures';
vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktest: vi.fn(),
  previewBacktest: vi.fn(),
  fetchBacktestCapabilities: vi.fn(),
}));

describe('creation validation', () => {
  creationSetup();
  it('rejects non-finite dates at submission as well as step navigation', async () => {
    const wrapper = openDrawer();
    await flushPromises();
    await advancePreview();
    wrapper
      .findAllComponents(NDatePicker)[0]
      .vm.$emit('update:formatted-value', 'invalid');
    await flushPromises();
    await advancePreview();
    (
      document.querySelector('[data-testid="creation-submit"]') as HTMLElement
    ).click();
    await flushPromises();
    await advancePreview();
    expect(submitBacktest).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain(
      'Enter valid start and end dates.',
    );
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
    vi.mocked(submitBacktest).mockResolvedValue('nullable-run');
    const wrapper = openDrawer();
    await flushPromises();
    await advancePreview();
    const number = wrapper
      .findAllComponents(NInputNumber)
      .find(
        (input) =>
          input.attributes('data-testid') === 'creation-param-threshold',
      )!;
    expect(number.props('clearable')).toBe(true);
    number.vm.$emit('update:value', null);
    await advancePreview();
    const submit = document.querySelector(
      '[data-testid="creation-submit"]',
    ) as HTMLElement;
    submit.click();
    await flushPromises();
    await advancePreview();
    expect(vi.mocked(submitBacktest).mock.lastCall?.[0].parameter_axes).toEqual(
      {
        threshold: { mode: 'constant', value: null },
        label: { mode: 'constant', value: '' },
      },
    );
    (
      document.querySelector(
        '[aria-label="Clear label to null"]',
      ) as HTMLElement
    ).click();
    await flushPromises();
    await advancePreview();
    submit.click();
    await flushPromises();
    await advancePreview();
    expect(vi.mocked(submitBacktest).mock.lastCall?.[0].parameter_axes).toEqual(
      {
        threshold: { mode: 'constant', value: null },
        label: { mode: 'constant', value: null },
      },
    );
    wrapper.unmount();
  });
});
