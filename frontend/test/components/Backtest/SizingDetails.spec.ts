import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import SizingDetails from '@/components/Backtest/SizingDetails.vue';
import type { BacktestRun } from '@/types/backtesterContracts';
import { initialDraft } from '@/views/creation/creationRequest';

function runWithEvents(count: number): BacktestRun {
  return {
    run_id: 'large-log',
    request: initialDraft(),
    diagnostics: {
      order_events: Array.from({ length: count }, (_, index) => ({
        timestamp_ms: 60000 * index,
        order_id: `entry-${index}`,
        outcome: 'insufficient_margin',
      })),
    },
  } as unknown as BacktestRun;
}

describe('sizing detail rendering', () => {
  it('does not mount event rows while the detail section is collapsed', async () => {
    const wrapper = mount(SizingDetails, {
      props: { run: runWithEvents(500) },
    });
    await flushPromises();
    const count = wrapper.findAll('tbody tr').length;
    wrapper.unmount();
    expect(count).toBe(0);
  });

  it('bounds rendering for a full-sized log and keeps later events accessible', async () => {
    const wrapper = mount(SizingDetails, {
      props: { run: runWithEvents(47006) },
    });
    await flushPromises();
    expect(wrapper.findAll('tbody tr')).toHaveLength(0);
    const details = wrapper.get('details');
    (details.element as HTMLDetailsElement).open = true;
    await details.trigger('toggle');
    await flushPromises();
    expect(wrapper.findAll('tbody tr')).toHaveLength(50);
    expect(wrapper.text()).toContain('entry-0');
    const last = wrapper
      .findAll('.n-pagination-item')
      .find((item) => item.text() === '941');
    expect(last).toBeDefined();
    await last!.trigger('click');
    await flushPromises();
    expect(wrapper.findAll('tbody tr')).toHaveLength(6);
    expect(wrapper.text()).toContain('entry-47005');
    await wrapper.setProps({ run: { ...runWithEvents(2), run_id: 'another' } });
    await flushPromises();
    expect(wrapper.findAll('tbody tr')).toHaveLength(0);
    wrapper.unmount();
  });
});
