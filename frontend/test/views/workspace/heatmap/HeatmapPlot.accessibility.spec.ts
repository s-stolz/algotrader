import { describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import HeatmapPlot from '@/views/workspace/heatmap/HeatmapPlot.vue';
vi.mock('@/utils/chart/chartFonts', () => ({
  whenChartFontReady: (ready: () => void) => {
    ready();
    return () => {};
  },
}));
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div />' },
}));
describe('heatmap hover accessibility', () => {
  it('announces exact tooltip content and clears stale descriptions', async () => {
    const dimension = { key: 'x', label: 'X', numeric: true, options: [] };
    const wrapper = mount(HeatmapPlot, {
      props: {
        cells: [],
        x: dimension,
        y: { ...dimension, key: 'y' },
        metric: 'return',
        bounds: null,
        pending: false,
        selectedIds: [],
        emptyReason: null,
      },
    });
    try {
      await flushPromises();
      const chart = wrapper.getComponent({ name: 'VChart' });
      const description = 'Run #1 · member-0\nfast: 10\nReturn %: -10.12345%';
      chart.vm.$emit('mouseover', { data: { cell: { description } } });
      await flushPromises();
      expect(wrapper.get('[role="status"]').text()).toBe(description);
      chart.vm.$emit('globalout');
      await flushPromises();
      expect(wrapper.get('[role="status"]').text()).toBe('');
      chart.vm.$emit('mouseover', { data: { cell: { description } } });
      await wrapper.setProps({ cells: [] });
      expect(wrapper.get('[role="status"]').text()).toBe('');
    } finally {
      wrapper.unmount();
    }
  });
});
