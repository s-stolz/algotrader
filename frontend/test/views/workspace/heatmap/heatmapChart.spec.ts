import { describe, expect, it } from 'vitest';
import { init, use } from 'echarts/core';
import { HeatmapChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
  AriaComponent,
} from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';
import { heatmapChart } from '@/views/workspace/heatmap/heatmapChart';
import { heatmapGrid } from '@/views/workspace/heatmap/heatmapGrid';
import { adaptHeatmapSnapshot } from '@/types/backtest/heatmapSnapshot';
import { designTokens } from '@/design/tokens';
import { savedHeatmap } from './heatmapFixtures';
use([
  HeatmapChart,
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
  AriaComponent,
  SVGRenderer,
]);
describe('production ECharts options', () => {
  it('renders sparse cells, special states and multiple selections', () => {
    const { accepted, runs } = savedHeatmap();
    const snapshot = adaptHeatmapSnapshot(accepted, runs);
    const cells = heatmapGrid(
      snapshot,
      'parameter:fast',
      'parameter:slow',
      snapshot.members[0].inputs,
      'factor',
    );
    const chart = init(null, undefined, {
      renderer: 'svg',
      ssr: true,
      width: 800,
      height: 400,
    });
    try {
      const options = heatmapChart(
        cells,
        snapshot.dimensions[0],
        snapshot.dimensions[1],
        'factor',
        [0, 0],
        false,
        [runs[0].run_id, runs[1].run_id],
      );
      chart.setOption(options);
      const svg = chart.renderToSVGString();
      expect(svg).toContain('Tektur');
      expect(options.textStyle).toMatchObject({
        fontFamily: designTokens.font.ui,
      });
      expect(options.tooltip).toMatchObject({
        textStyle: { fontFamily: designTokens.font.ui },
      });
      expect(svg).toContain('#252a33');
      expect(svg).toContain('×');
      expect(svg).toContain('∞');
      expect(svg).toContain('stroke-width="2"');
      chart.setOption(
        heatmapChart(
          cells,
          snapshot.dimensions[0],
          snapshot.dimensions[1],
          'factor',
          [0, 0],
          true,
          [],
        ),
        { notMerge: true },
      );
      expect(chart.renderToSVGString()).toContain('#56616c');
      const missing = heatmapGrid(
        snapshot,
        'parameter:fast',
        'parameter:slow',
        snapshot.members[2].inputs,
        'factor',
      );
      chart.setOption(
        heatmapChart(
          missing,
          snapshot.dimensions[0],
          snapshot.dimensions[1],
          'factor',
          [0, 0],
          false,
          [],
        ),
        { notMerge: true },
      );
      expect(chart.renderToSVGString()).toContain('#79649b');
      expect(chart.renderToSVGString()).toContain('◇');
    } finally {
      chart.dispose();
    }
  });
});
