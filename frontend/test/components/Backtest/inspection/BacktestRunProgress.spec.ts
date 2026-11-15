import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import BacktestRunProgress from '@/components/Backtest/inspection/BacktestRunProgress.vue';

describe('run stage milestones', () => {
  it('places loading and saving at the endpoints and advances only completed stages', async () => {
    const wrapper = mount(BacktestRunProgress, {
      props: { ordinal: 4, stage: 'loading_data' },
    });
    const dots = wrapper.findAll('.milestone-dot');
    expect(dots).toHaveLength(5);
    expect(dots[0].attributes('style')).toContain('left: 0%');
    expect(dots[4].attributes('style')).toContain('left: 100%');
    expect(wrapper.findAll('li').map((label) => label.text())).toEqual([
      'Loading data',
      'Preparing indicators',
      'Simulating',
      'Calculating results',
      'Saving',
    ]);
    expect(wrapper.findAll('.milestone-dot.complete')).toHaveLength(0);
    await wrapper.setProps({ stage: 'simulating' });
    expect(wrapper.findAll('.milestone-dot.complete')).toHaveLength(2);
    expect(wrapper.get('[aria-current="step"]').text()).toBe('Simulating');
    expect(wrapper.get('.milestone-fill').attributes('style')).toContain(
      'width: 25%',
    );
    expect(
      wrapper.get('[role="progressbar"]').attributes('aria-valuenow'),
    ).toBe('2');
    await wrapper.setProps({ stage: 'saving' });
    expect(wrapper.findAll('.milestone-dot.complete')).toHaveLength(4);
    expect(wrapper.get('[aria-current="step"]').text()).toBe('Saving');
  });
});

describe('simulation candle counts', () => {
  it('interpolates only simulation and hides counts on early completion', async () => {
    const wrapper = mount(BacktestRunProgress, {
      props: {
        ordinal: 1,
        stage: 'simulating',
        processedCandles: 5000,
        totalCandles: 10000,
      },
    });
    expect(wrapper.get('.candle-count').text()).toBe('5,000 / 10,000');
    expect(wrapper.get('.milestone-fill').attributes('style')).toContain(
      'width: 62.5%',
    );
    expect(wrapper.get('[aria-current="step"]').text()).toContain('Simulating');
    await wrapper.setProps({ stage: 'calculating_results' });
    expect(wrapper.find('.candle-count').exists()).toBe(false);
    expect(wrapper.get('.milestone-fill').attributes('style')).toContain(
      'width: 75%',
    );
  });
});
