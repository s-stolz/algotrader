import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { NInputNumber } from 'naive-ui';
import { describe, expect, it } from 'vitest';
import BacktestEntryLimitField from '@/views/BacktestEntryLimitField.vue';
import { initialDraft } from '@/views/creation/creationRequest';

describe('daily entry limit control', () => {
  it('starts unlimited and saves or clears an independent limit', async () => {
    const execution = reactive(initialDraft().execution);
    const wrapper = mount(BacktestEntryLimitField, { props: { execution } });
    const input = wrapper.getComponent(NInputNumber);
    expect(input.props('value')).toBeNull();
    expect(input.props('placeholder')).toBe('Unlimited');
    input.vm.$emit('update:value', 1);
    await wrapper.vm.$nextTick();
    expect(execution.max_entries_per_day).toBe(1);
    expect(execution.daily_schedule).toBeUndefined();
    input.vm.$emit('update:value', null);
    await wrapper.vm.$nextTick();
    expect(execution.max_entries_per_day).toBeUndefined();
    wrapper.unmount();
  });
  it('shows reused values and reports invalid limits', async () => {
    const execution = reactive({
      ...initialDraft().execution,
      max_entries_per_day: 2,
    });
    const wrapper = mount(BacktestEntryLimitField, { props: { execution } });
    expect(wrapper.getComponent(NInputNumber).props('value')).toBe(2);
    execution.max_entries_per_day = 0;
    await wrapper.vm.$nextTick();
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'positive whole number',
    );
    wrapper.unmount();
  });
});
