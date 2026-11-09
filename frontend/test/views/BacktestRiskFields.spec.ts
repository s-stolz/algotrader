import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BacktestRiskFields from '@/views/BacktestRiskFields.vue';
import { initialDraft } from '@/views/creation/creationRequest';

describe('Backtest risk settings', () => {
  it('keeps exposure, risk, and exit sources independent', async () => {
    const execution = initialDraft().execution;
    const wrapper = mount(BacktestRiskFields, {
      props: { modelValue: execution },
    });
    const selects = wrapper.findAllComponents(BaseSelect);
    selects[0].vm.$emit('update:value', 'equity_risk');
    await wrapper.vm.$nextTick();
    expect(execution.sizing).toEqual({
      mode: 'equity_risk',
      value: 1,
      leverage: 1,
    });
    selects[1].vm.$emit('update:value', 'ticks');
    await wrapper.vm.$nextTick();
    expect(execution.stop_loss).toEqual({ mode: 'ticks', value: 1 });
    expect(execution.take_profit?.mode).toBe('strategy');
    expect(wrapper.text()).toContain('Each entry has its own budget');
    wrapper.unmount();
  });
});
