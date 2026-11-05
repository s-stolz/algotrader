import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { NTimePicker } from 'naive-ui';
import BacktestScheduleFields from '@/views/BacktestScheduleFields.vue';
import {
  initialScheduleDraft,
  scheduleDraftIssues,
} from '@/types/backtest/schedule';

describe('daily schedule alternatives', () => {
  it('edits UTC times, explains invalid rows, and retains values while disabled', async () => {
    const schedule = reactive(initialScheduleDraft());
    const wrapper = mount(BacktestScheduleFields, {
      props: { schedule, errors: {} },
    });
    expect(wrapper.findComponent(NTimePicker).exists()).toBe(false);
    await wrapper.get('[role="switch"]').trigger('click');
    const pickers = wrapper.findAllComponents(NTimePicker);
    expect(pickers.map((picker) => picker.props('formattedValue'))).toEqual([
      '00:00',
      '12:00',
      '17:00',
    ]);
    pickers[0].vm.$emit('update:formattedValue', '06:30');
    pickers[2].vm.$emit('update:formattedValue', '11:00');
    await wrapper.setProps({ errors: scheduleDraftIssues(schedule) });
    expect(schedule.candidates[0].entry_start_minute_utc).toBe(390);
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'exit must be at or after last entry',
    );
    expect(pickers[2].props('status')).toBe('error');
    await wrapper.get('[role="switch"]').trigger('click');
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(schedule.candidates[0].exit_minute_utc).toBe(660);
    await wrapper.get('[role="switch"]').trigger('click');
    expect(
      wrapper.findAllComponents(NTimePicker)[2].props('formattedValue'),
    ).toBe('11:00');
    wrapper.unmount();
  });

  it('adds incomplete rows and preserves the remaining values when removing a row', async () => {
    const schedule = reactive(
      initialScheduleDraft({
        entry_start_minute_utc: 60,
        last_entry_minute_utc: 120,
        exit_minute_utc: 180,
      }),
    );
    const wrapper = mount(BacktestScheduleFields, {
      props: { schedule, errors: {} },
    });
    expect(
      wrapper
        .findAllComponents(NTimePicker)
        .map((picker) => picker.props('formattedValue')),
    ).toEqual(['01:00', '02:00', '03:00']);
    const add = () =>
      wrapper
        .findAll('button')
        .find((button) => button.text().includes('Add schedule'))!
        .trigger('click');
    await add();
    expect(schedule.candidates[1].exit_minute_utc).toBeNull();
    const pickers = wrapper.findAllComponents(NTimePicker);
    for (const [index, time] of ['04:00', '05:00', '06:00'].entries()) {
      pickers[index + 3].vm.$emit('update:formattedValue', time);
    }
    await wrapper.vm.$nextTick();
    await wrapper.get('[aria-label="Remove schedule 1"]').trigger('click');
    expect(
      wrapper
        .findAllComponents(NTimePicker)
        .map((picker) => picker.props('formattedValue')),
    ).toEqual(['04:00', '05:00', '06:00']);
    expect(
      wrapper.get('[aria-label="Remove schedule 1"]').attributes('disabled'),
    ).toBeDefined();
    wrapper.unmount();
  });
});
