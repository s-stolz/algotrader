import { expect, it } from 'vitest';
import { init, use } from 'echarts/core';
import { HeatmapChart } from 'echarts/charts';
import {
  GridComponent,
  VisualMapComponent,
  TooltipComponent,
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
  VisualMapComponent,
  TooltipComponent,
  AriaComponent,
  SVGRenderer,
]);
it('keeps selected outlines above neighboring cells without hover', () => {
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
    for (const selectedIds of [
      [runs[0].run_id],
      [runs[0].run_id, runs[1].run_id],
      [runs[1].run_id],
      [],
    ]) {
      chart.setOption(
        heatmapChart(
          cells,
          snapshot.dimensions[0],
          snapshot.dimensions[1],
          'factor',
          [0, 0],
          false,
          selectedIds,
        ),
      );
      chart.renderToSVGString();
      const rectangles = chart
        .getZr()
        .storage.getDisplayList()
        .filter((element) => element.type === 'rect');
      const outlines = rectangles.filter(
        (element) =>
          element.style.stroke === designTokens.chart.heatmapSelection,
      );
      expect(outlines).toHaveLength(selectedIds.length);
      expect(outlines.every((element) => element.style.lineWidth === 2)).toBe(
        true,
      );
      // Later-painted neighboring fills must never cover selection strokes.
      if (outlines.length) {
        expect(rectangles.slice(-outlines.length)).toEqual(outlines);
      }
      const gutters = rectangles.filter(
        (element) => element.style.stroke === designTokens.color.panel,
      );
      expect(gutters.length).toBeGreaterThan(0);
      expect(gutters.every((element) => element.style.lineWidth >= 4)).toBe(
        true,
      );
    }
  } finally {
    chart.dispose();
  }
});
