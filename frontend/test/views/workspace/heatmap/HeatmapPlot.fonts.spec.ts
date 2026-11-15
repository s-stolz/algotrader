import { describe, expect, it, vi, onTestFinished } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import HeatmapPlot from '@/views/workspace/heatmap/HeatmapPlot.vue';
import * as chartFonts from '@/utils/chart/chartFonts';
import { designTokens } from '@/design/tokens';
vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div data-testid="canvas-chart" />',
  },
}));
function deferred() {
  let resolve!: () => void;
  let reject!: () => void;
  const promise = new Promise<void>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}
function fontWait() {
  const loaded = deferred(),
    ready = deferred();
  const fonts = {
    check: vi.fn(() => false),
    load: vi.fn(() => loaded.promise),
    ready: ready.promise,
  };
  const descriptor = Object.getOwnPropertyDescriptor(document, 'fonts');
  Object.defineProperty(document, 'fonts', {
    configurable: true,
    value: fonts,
  });
  onTestFinished(() => {
    if (descriptor) Object.defineProperty(document, 'fonts', descriptor);
    else Reflect.deleteProperty(document, 'fonts');
  });
  return { loaded, ready, fonts };
}
function plot() {
  const dimension = {
    key: 'x',
    label: 'X',
    numeric: true,
    options: [{ value: '1', label: '1' }],
  };
  const wrapper = mount(HeatmapPlot, {
    props: {
      cells: [],
      x: dimension,
      y: { ...dimension, key: 'y' },
      metric: 'return',
      bounds: [0, 1],
      pending: false,
      selectedIds: [],
      emptyReason: null,
    },
  });
  onTestFinished(() => wrapper.unmount());
  return wrapper;
}
describe('heatmap canvas font lifecycle', () => {
  it('waits for the requested face and readiness, then renders the latest options', async () => {
    const { loaded, ready, fonts } = fontWait();
    const wrapper = plot();
    expect(wrapper.find('[data-testid="canvas-chart"]').exists()).toBe(false);
    expect(fonts.load).toHaveBeenCalledWith(
      `${designTokens.text.secondary} ${designTokens.font.ui}`,
    );
    await wrapper.setProps({
      x: { key: 'x', label: 'Latest X', numeric: true, options: [] },
    });
    loaded.resolve();
    await flushPromises();
    expect(wrapper.find('[data-testid="canvas-chart"]').exists()).toBe(false);
    ready.resolve();
    await flushPromises();
    expect(
      wrapper.getComponent({ name: 'VChart' }).props('option').xAxis.name,
    ).toBe('Latest X');
  });
  it('renders the shared fallback stack if font loading fails', async () => {
    const { loaded } = fontWait();
    const wrapper = plot();
    loaded.reject();
    await flushPromises();
    expect(
      wrapper.getComponent({ name: 'VChart' }).props('option').textStyle
        .fontFamily,
    ).toBe(designTokens.font.ui);
  });
  it('cancels the shared pending readiness callback on disposal', async () => {
    const { loaded, ready } = fontWait();
    const original = chartFonts.whenChartFontReady;
    const cancel = vi.fn();
    const render = vi.fn();
    const spy = vi
      .spyOn(chartFonts, 'whenChartFontReady')
      .mockImplementation((callback) => {
        const stop = original(() => {
          render();
          callback();
        });
        return () => {
          cancel();
          stop();
        };
      });
    onTestFinished(() => spy.mockRestore());
    const wrapper = plot();
    wrapper.unmount();
    expect(cancel).toHaveBeenCalledOnce();
    loaded.resolve();
    ready.resolve();
    await flushPromises();
    expect(render).not.toHaveBeenCalled();
  });
});
