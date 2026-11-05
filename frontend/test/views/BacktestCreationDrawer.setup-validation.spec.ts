import { flushPromises } from '@vue/test-utils';
import { NSelect, NInputNumber, NSwitch } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import { previewBacktest, submitBacktest } from '@/api/backtesterClient';
import BaseTimePicker from '@/components/Common/BaseTimePicker.vue';
import { openDrawer, creationSetup, advancePreview } from './creationFixtures';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktest: vi.fn(),
  previewBacktest: vi.fn(),
  fetchBacktestCapabilities: vi.fn(),
}));
async function click(text: string) {
  const button = [...document.body.querySelectorAll('button')].find(
    (item) => item.textContent?.trim() === text,
  );
  expect(button, text).toBeTruthy();
  button!.click();
  await flushPromises();
}
const activeStep = () =>
  document.querySelector('[aria-current="step"]')?.textContent;

describe('setup validation and schedule alternatives', () => {
  creationSetup();
  it.each([
    ['selections-markets', [1], 'Select an available Market.'],
    [
      'selections-timeframes',
      ['M1'],
      'Select at least one supported Timeframe.',
    ],
    [
      'creation-directions',
      ['long_only'],
      'Select at least one direction option.',
    ],
  ])(
    'blocks both forward paths when %s is empty',
    async (testId, values, error) => {
      const wrapper = openDrawer();
      await advancePreview();
      const select = wrapper
        .findAllComponents(NSelect)
        .find((item) => item.attributes('data-testid') === testId)!;
      select.vm.$emit('update:value', []);
      await advancePreview();
      const previews = vi.mocked(previewBacktest).mock.calls.length;
      for (const destination of ['Parameters →', 'Review']) {
        await click(destination);
        expect(activeStep()).toBe('Setup');
        expect(select.props('status')).toBe('error');
        expect(document.body.textContent).toContain(error);
      }
      await advancePreview();
      expect(previewBacktest).toHaveBeenCalledTimes(previews);
      expect(submitBacktest).not.toHaveBeenCalled();
      select.vm.$emit('update:value', values);
      await flushPromises();
      expect(select.props('status')).toBeUndefined();
      await click('Parameters →');
      expect(activeStep()).toBe('Parameters');
    },
  );

  it('blocks missing costs and times, omits disabled schedules, and retains rows', async () => {
    let wrapper = openDrawer();
    await advancePreview();
    const cost = wrapper
      .findAllComponents(NInputNumber)
      .find(
        (item) => item.props('inputProps')?.['aria-label'] === 'Slippage (bps)',
      )!;
    expect(cost).toBeTruthy();
    cost.vm.$emit('update:value', null);
    await click('Parameters →');
    expect(activeStep()).toBe('Setup');
    expect(cost.props('status')).toBe('error');
    cost.vm.$emit('update:value', 0);
    wrapper.getComponent(NSwitch).vm.$emit('update:value', true);
    await flushPromises();
    await click('＋ Add schedule alternative');
    const focus = vi.spyOn(HTMLElement.prototype, 'focus');
    await click('Review');
    expect(activeStep()).toBe('Setup');
    expect(document.body.textContent).toContain('Enter all three times.');
    const times = wrapper.findAllComponents(BaseTimePicker);
    expect(focus.mock.contexts).toContain(times[3].get('input').element);
    focus.mockRestore();
    expect(times[3].attributes('aria-invalid')).toBe('true');
    expect(times[3].attributes('aria-describedby')).toBe('schedule-1-error');
    ['06:00', '10:00', '16:00'].forEach((time, index) => {
      times[index + 3].vm.$emit('update:formatted-value', time);
    });
    await advancePreview();
    const request = vi.mocked(previewBacktest).mock.lastCall![0];
    expect(request.daily_schedules).toHaveLength(2);
    expect(request.execution).not.toHaveProperty('daily_schedule');
    wrapper.getComponent(NSwitch).vm.$emit('update:value', false);
    await advancePreview();
    expect(vi.mocked(previewBacktest).mock.lastCall![0]).not.toHaveProperty(
      'daily_schedules',
    );
    wrapper.unmount();
    wrapper = openDrawer();
    await advancePreview();
    wrapper.getComponent(NSwitch).vm.$emit('update:value', true);
    await flushPromises();
    expect(
      wrapper
        .findAllComponents(BaseTimePicker)
        .map((time) => time.props('formattedValue')),
    ).toEqual(['00:00', '12:00', '17:00', '06:00', '10:00', '16:00']);
    await click('Parameters →');
    expect(activeStep()).toBe('Parameters');
    await advancePreview();
    await click('Review candidates →');
    vi.mocked(submitBacktest).mockResolvedValue('scheduled-backtest');
    await click('Create Backtest');
    expect(vi.mocked(submitBacktest).mock.lastCall![0].daily_schedules).toEqual(
      request.daily_schedules,
    );
  });
});
