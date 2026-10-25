import { mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import BaseDateRange from '@/components/Common/BaseDateRange.vue';

afterEach(() => vi.useRealTimers());
describe('calendar period shortcuts', () => {
  it.each([
    ['2024-03-31T23:30:00Z', 'Past month', '2024-02-29', '2024-03-31'],
    ['2024-02-29T12:00:00Z', 'Past year', '2023-02-28', '2024-02-29'],
    ['2026-01-01T12:00:00Z', 'Year to date', '2026-01-01', '2026-01-01'],
  ])('clamps %s using %s to UTC calendar boundaries', async (now, label, start, end) => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(now));
    const wrapper = mount(BaseDateRange, { props: { start: '', end: '' } });
    await wrapper.findAll('button').find(button => button.text() === label)!.trigger('click');
    expect(wrapper.emitted('update:start')?.[0]).toEqual([start]);
    expect(wrapper.emitted('update:end')?.[0]).toEqual([end]);
    wrapper.unmount();
  });
});
