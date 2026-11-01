import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { NTimePicker } from 'naive-ui';
import BacktestScheduleFields from '@/views/BacktestScheduleFields.vue';
import { initialDraft } from '@/views/creation/creationRequest';

describe('daily execution schedule controls', () => {
  it('edits UTC times and removes disabled settings', async () => {
    const execution = reactive(initialDraft().execution);
    const wrapper = mount(BacktestScheduleFields, { props: { execution } });
    expect(execution.daily_schedule).toBeUndefined();
    expect(wrapper.findComponent(NTimePicker).exists()).toBe(false);
    await wrapper.get('input[type="checkbox"]').setValue(true);
    const pickers = wrapper.findAllComponents(NTimePicker);
    expect(pickers.map((picker) => picker.props('formattedValue'))).toEqual([
      '00:00',
      '12:00',
      '17:00',
    ]);
    pickers[0].vm.$emit('update:formattedValue', '06:30');
    await wrapper.vm.$nextTick();
    expect(execution.daily_schedule?.entry_start_minute_utc).toBe(390);
    pickers[2].vm.$emit('update:formattedValue', '11:00');
    await wrapper.vm.$nextTick();
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'exit must be at or after last entry',
    );
    await wrapper.get('input[type="checkbox"]').setValue(false);
    expect(execution.daily_schedule).toBeUndefined();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it('shows saved values without applying the enable defaults', () => {
    const execution = {
      ...initialDraft().execution,
      daily_schedule: {
        entry_start_minute_utc: 60,
        last_entry_minute_utc: 120,
        exit_minute_utc: 180,
      },
    };
    const wrapper = mount(BacktestScheduleFields, { props: { execution } });
    expect(
      wrapper
        .findAllComponents(NTimePicker)
        .map((picker) => picker.props('formattedValue')),
    ).toEqual(['01:00', '02:00', '03:00']);
    wrapper.unmount();
  });
});
