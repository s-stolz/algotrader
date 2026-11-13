import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { NTag } from 'naive-ui';
import EquityReplayCharts from '@/views/EquityReplayCharts.vue';
import { designTokens } from '@/design/tokens';

const {
  setData,
  remove,
  createChart,
  addSeries,
  fitContent,
  applyOptions,
  seriesOptions,
} = vi.hoisted(() => {
  const setData = vi.fn();
  const seriesOptions = vi.fn();
  const applyOptions = vi.fn();
  const addSeries = vi.fn((_kind: unknown, _options: { color: string }) => ({
    setData,
    applyOptions: seriesOptions,
  }));
  const fitContent = vi.fn();
  const remove = vi.fn();
  const createChart = vi.fn(() => ({
    addSeries,
    timeScale: () => ({ fitContent }),
    applyOptions,
    remove,
    removeSeries: vi.fn(),
  }));
  return {
    setData,
    addSeries,
    fitContent,
    remove,
    createChart,
    applyOptions,
    seriesOptions,
  };
});

vi.mock('lightweight-charts', () => ({
  createChart,
  LineSeries: 'LineSeries',
}));

describe('EquityReplayCharts', () => {
  const originalFonts = Object.getOwnPropertyDescriptor(document, 'fonts');
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => {
    if (originalFonts) Object.defineProperty(document, 'fonts', originalFonts);
    else Reflect.deleteProperty(document, 'fonts');
  });

  it('keeps headings outside separate chart panels', () => {
    const wrapper = mount(EquityReplayCharts, {
      props: { series: [], sampled: true },
    });
    const sections = wrapper.findAll('section');
    expect(sections.map((section) => section.get('h2').text())).toEqual([
      'Equity',
      'Drawdown',
    ]);
    for (const section of sections) {
      expect(section.get('.chart-panel').find('h2').exists()).toBe(false);
      expect(section.get('.chart-panel').findAll('.chart')).toHaveLength(1);
      expect(section.get('header').find('.series-legend').exists()).toBe(true);
    }
    expect(wrapper.text()).not.toContain('Sampled curve');
    wrapper.unmount();
  });

  it('shows Sampled tags only while displayed curves are sampled', async () => {
    const wrapper = mount(EquityReplayCharts, { props: { series: [] } });
    expect(wrapper.findAllComponents(NTag)).toHaveLength(0);
    await wrapper.setProps({ sampled: true });
    expect(wrapper.findAllComponents(NTag).map((tag) => tag.text())).toEqual([
      'Sampled',
      'Sampled',
    ]);
    for (const section of wrapper.findAll('section')) {
      expect(section.get('header').findComponent(NTag).exists()).toBe(true);
    }
    await wrapper.setProps({ sampled: false });
    expect(wrapper.findAllComponents(NTag)).toHaveLength(0);
    expect(createChart).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it('keeps both legends consistent with series labels, colors, and selection', async () => {
    const series = [
      { runId: 'first', name: 'First run', ordinal: 0, points: [] },
      { runId: 'legacy-run-id', name: 'Legacy run', points: [] },
    ];
    const wrapper = mount(EquityReplayCharts, { props: { series } });
    for (const legend of wrapper.findAll('.series-legend')) {
      expect(
        legend.findAll('li').map((item) => item.attributes('title')),
      ).toEqual(['First run', 'Legacy run']);
      expect(legend.findAll('li').map((item) => item.text())).toEqual([
        '#1',
        'legacy-r',
      ]);
      expect(legend.get('.series-id').text()).toBe('legacy-r');
      legend.findAll<HTMLElement>('.series-swatch').forEach((swatch, index) => {
        const expected = document.createElement('span');
        expected.style.background = addSeries.mock.calls[index * 2][1].color;
        expect(swatch.element.style.background).toBe(expected.style.background);
      });
    }
    await wrapper.setProps({ series: [series[1]] });
    for (const legend of wrapper.findAll('.series-legend')) {
      expect(legend.findAll('li')).toHaveLength(1);
      expect(legend.get('li').attributes('title')).toBe('Legacy run');
    }
    expect(createChart).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it('converts millisecond points at the chart boundary and keeps negative drawdown', () => {
    const wrapper = mount(EquityReplayCharts, {
      props: {
        series: [
          {
            runId: 'one',
            name: 'One',
            points: [
              { timestamp_ms: 1_700_000_000_123, equity: 100, drawdown_pct: 0 },
              { timestamp_ms: 1_700_000_060_123, equity: 95, drawdown_pct: -5 },
            ],
          },
        ],
      },
    });

    expect(createChart).toHaveBeenCalledTimes(2);
    for (const call of [1, 2]) {
      expect(createChart).toHaveBeenNthCalledWith(
        call,
        expect.any(HTMLElement),
        expect.objectContaining({
          layout: {
            background: { color: designTokens.color.inset },
            textColor: designTokens.color.muted,
            fontFamily: designTokens.font.ui,
            fontSize: Number.parseInt(designTokens.text.secondary),
          },
          crosshair: {
            vertLine: {
              color: designTokens.color.muted,
              labelBackgroundColor: designTokens.color.inset,
            },
            horzLine: {
              color: designTokens.color.muted,
              labelBackgroundColor: designTokens.color.inset,
            },
          },
        }),
      );
    }
    expect(setData).toHaveBeenNthCalledWith(1, [
      { time: 1_700_000_000, value: 100 },
      { time: 1_700_000_060, value: 95 },
    ]);
    expect(setData).toHaveBeenNthCalledWith(2, [
      { time: 1_700_000_000, value: 0 },
      { time: 1_700_000_060, value: -5 },
    ]);
    wrapper.unmount();
    expect(remove).toHaveBeenCalledTimes(2);
  });

  it('updates series without recreating chart canvases and fits the updated history', async () => {
    const run = {
      runId: 'one',
      name: 'One',
      points: [
        { timestamp_ms: 1_700_000_000_123, equity: 100, drawdown_pct: 0 },
      ],
    };
    const wrapper = mount(EquityReplayCharts, { props: { series: [run] } });
    await wrapper.setProps({ series: [{ ...run }] });
    expect(createChart).toHaveBeenCalledTimes(2);
    expect(remove).not.toHaveBeenCalled();
    expect(addSeries).toHaveBeenCalledTimes(2);
    await wrapper.setProps({ series: [] });
    expect(createChart).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it('refits dense histories after selection changes and container resizing', async () => {
    let resize = () => {};
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(callback: () => void) {
          resize = callback;
        }
        observe() {}
        disconnect() {}
      },
    );
    const points = Array.from({ length: 2000 }, (_, index) => ({
      timestamp_ms: 1_700_000_000_000 + index * 60_000,
      equity: 100 - index / 10000,
      drawdown_pct: -index / 10000,
    }));
    const wrapper = mount(EquityReplayCharts, {
      props: { series: [{ runId: 'one', name: 'One', points }] },
    });
    expect(fitContent).toHaveBeenCalledTimes(2);
    await wrapper.setProps({
      series: [
        { runId: 'one', name: 'One', points },
        {
          runId: 'two',
          name: 'Two',
          points: points.map((point) => ({
            ...point,
            timestamp_ms: point.timestamp_ms + 30_000,
          })),
        },
      ],
    });
    expect(fitContent).toHaveBeenCalledTimes(4);
    expect(applyOptions).toHaveBeenCalledWith({
      timeScale: { minBarSpacing: 1 / 4001 },
    });
    resize();
    expect(fitContent).toHaveBeenCalledTimes(6);
    expect(createChart).toHaveBeenCalledTimes(2);
    wrapper.unmount();
    vi.unstubAllGlobals();
  });

  it('gives tiny drawdowns enough percentage precision to remain visible', () => {
    const wrapper = mount(EquityReplayCharts, {
      props: {
        series: [
          {
            runId: 'one',
            name: 'One',
            points: [
              {
                timestamp_ms: 1_700_000_000_000,
                equity: 9999.97,
                drawdown_pct: -0.0003,
              },
            ],
          },
        ],
      },
    });
    const format = seriesOptions.mock.calls[0]![0].priceFormat;
    expect(format.formatter(-0.0003)).toBe('-0.000300%');
    expect(format.formatter(0)).toBe('0.000000%');
    expect(format.formatter(-0.00000001)).toBe('0.000000%');
    wrapper.unmount();
  });

  it('overlays stable run identities in both full-width charts', () => {
    const points = [
      { timestamp_ms: 1_700_000_000_123, equity: 100, drawdown_pct: -2 },
    ];
    const wrapper = mount(EquityReplayCharts, {
      props: {
        series: [
          { runId: 'one', name: 'First', ordinal: 0, points },
          { runId: 'two', name: 'Second', ordinal: 1, points },
        ],
      },
    });
    expect(wrapper.find('[aria-label="Equity chart"]').exists()).toBe(true);
    expect(wrapper.find('[aria-label="Drawdown chart"]').exists()).toBe(true);
    expect(wrapper.find('[aria-label="Compared runs"]').text()).toContain('#1');
    expect(wrapper.find('[aria-label="Compared runs"]').text()).toContain('#2');
    expect(wrapper.find('[aria-label="Compared runs"]').text()).not.toContain(
      'one',
    );
    expect(addSeries).toHaveBeenCalledTimes(4);
    expect(addSeries.mock.calls[0]?.[1].color).toBe(
      addSeries.mock.calls[1]?.[1].color,
    );
    expect(addSeries.mock.calls[2]?.[1].color).toBe(
      addSeries.mock.calls[3]?.[1].color,
    );
    expect(addSeries.mock.calls[0]?.[1].color).not.toBe(
      addSeries.mock.calls[2]?.[1].color,
    );
    wrapper.unmount();
  });

  it('waits for the font and renders the latest series received during loading', async () => {
    let finishLoad!: (faces: FontFace[]) => void;
    Object.defineProperty(document, 'fonts', {
      configurable: true,
      value: {
        check: () => false,
        load: () =>
          new Promise<FontFace[]>((resolve) => (finishLoad = resolve)),
        ready: Promise.resolve(),
      },
    });
    const wrapper = mount(EquityReplayCharts, {
      props: { series: [{ runId: 'old', name: 'Old', points: [] }] },
    });
    expect(createChart).not.toHaveBeenCalled();
    await wrapper.setProps({
      series: [
        {
          runId: 'latest',
          name: 'Latest',
          points: [
            { timestamp_ms: 1_700_000_060_123, equity: 95, drawdown_pct: -5 },
          ],
        },
      ],
    });
    expect(createChart).not.toHaveBeenCalled();
    finishLoad([]);
    await flushPromises();
    expect(createChart).toHaveBeenCalledTimes(2);
    expect(setData).toHaveBeenNthCalledWith(1, [
      { time: 1_700_000_060, value: 95 },
    ]);
    expect(setData).toHaveBeenNthCalledWith(2, [
      { time: 1_700_000_060, value: -5 },
    ]);
    wrapper.unmount();
    expect(remove).toHaveBeenCalledTimes(2);
  });

  it('cancels deferred canvas creation when unmounted before the font loads', async () => {
    let finishLoad!: (faces: FontFace[]) => void;
    Object.defineProperty(document, 'fonts', {
      configurable: true,
      value: {
        check: () => false,
        load: () =>
          new Promise<FontFace[]>((resolve) => (finishLoad = resolve)),
        ready: Promise.resolve(),
      },
    });
    const wrapper = mount(EquityReplayCharts, { props: { series: [] } });
    expect(createChart).not.toHaveBeenCalled();
    wrapper.unmount();
    finishLoad([]);
    await flushPromises();
    expect(createChart).not.toHaveBeenCalled();
    expect(remove).not.toHaveBeenCalled();
  });
});

describe('progressive replay presentation', () => {
  it('keeps the animation over partial charts without padding the time range', async () => {
    const wrapper = mount(EquityReplayCharts, {
      props: {
        loading: true,
        series: [
          {
            runId: 'a',
            name: 'A',
            points: [{ timestamp_ms: 2000, equity: 100, drawdown_pct: 0 }],
          },
        ],
      },
    });
    await flushPromises();
    expect(wrapper.findAll('.replay-loading.overlay')).toHaveLength(2);
    expect(setData).toHaveBeenCalledWith([{ time: 2, value: 100 }]);
    await wrapper.setProps({ loading: false });
    expect(wrapper.find('.replay-loading').exists()).toBe(false);
    wrapper.unmount();
  });
});
