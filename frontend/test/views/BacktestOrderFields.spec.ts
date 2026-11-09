import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import BacktestOrderFields from '@/views/BacktestOrderFields.vue';
import { initialDraft } from '@/views/creation/creationRequest';

const stubs = {
  BaseSelect: {
    props: ['value', 'options'],
    emits: ['update:value'],
    template: `
      <select :value="value" @change="$emit('update:value', $event.target.value)">
        <option v-for="option in options" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>`,
  },
  NInputNumber: { props: ['value'], template: '<input :value="value" />' },
};
describe('order execution controls', () => {
  it('reveals order controls and requires an explicit quote when enabling orders', async () => {
    const execution = initialDraft().execution;
    const wrapper = mount(BacktestOrderFields, {
      props: { execution, errors: {} },
      global: { stubs },
    });
    expect(wrapper.text()).not.toContain('Spread (price units)');
    execution.execution_mode = 'orders';
    execution.spread = 0;
    await wrapper.setProps({ execution: { ...execution } });
    expect(wrapper.text()).toContain('Spread (price units)');
    expect(wrapper.find('[aria-label="Execution mode"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Ask minus bid');
    expect(execution.candle_quote).toBeUndefined();
  });
  it('displays and edits saved order settings and policy', async () => {
    const execution = initialDraft().execution;
    Object.assign(execution, {
      execution_mode: 'orders',
      candle_quote: 'ask',
      spread: 0.0002,
      max_position_quantity: 4,
      intrabar_execution_policy: 'optimistic',
    });
    const wrapper = mount(BacktestOrderFields, {
      props: { execution, errors: {} },
      global: { stubs },
    });
    expect(wrapper.get('[aria-label="Candle quote"]').element).toHaveProperty(
      'value',
      'ask',
    );
    expect(
      wrapper.findAll('input').map((input) => input.element.value),
    ).toEqual(['0.0002', '4']);
    const policy = wrapper.get('[aria-label="Intrabar execution policy"]');
    expect(policy.element).toHaveProperty('value', 'optimistic');
    await policy.setValue('conservative');
    expect(execution.intrabar_execution_policy).toBe('conservative');
  });
});
